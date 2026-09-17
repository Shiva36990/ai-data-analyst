"""
LangGraph node implementations.

Each node is a plain function: (state) -> partial state update dict.
Every LLM call asks for a structured Pydantic output so control flow
never depends on parsing free text.
"""

import time

from src.llm import get_llm
from src.config import settings
from src.database import execute_read_query
from src.schema_service import get_database_schema, schema_to_text
from src.sql_guard import validate_sql
from src.local_query_router import local_sql_for_question
from src.business_metadata import metrics_to_text
from src.analytics import (
    rows_to_dataframe,
    basic_numeric_summary,
    numeric_summary_to_text,
)
from src.models import (
    IntentResult,
    SQLGenerationResult,
    AnalysisResult,
    ChartPlan,
    InvestigationDecision,
    ConversationReply,
)
from src.prompts import (
    INTENT_PROMPT,
    SQL_GENERATION_PROMPT,
    SQL_REPAIR_PROMPT,
    INSIGHT_PROMPT,
    INVESTIGATION_PROMPT,
    CHART_PROMPT,
    CONVERSATION_PROMPT,
)


def _context_to_text(context: list[dict] | None) -> str:
    if not context:
        return "(no prior conversation)"

    lines = []
    for turn in context[-3:]:  # only the last few turns to bound token usage
        lines.append(f"Q: {turn.get('question', '')}")
        if turn.get("sql"):
            lines.append(f"SQL: {turn.get('sql')}")
        if turn.get("summary"):
            lines.append(f"Summary: {turn.get('summary')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------
# Intent
# ---------------------------------------------------------------------

def intent_node(state):
    question = state["question"]

    print("\n========== INTENT NODE ==========")
    print(f"QUESTION: {question}")

    # First try the local deterministic router.
    local_sql = local_sql_for_question(question)

    if local_sql:
        print("Using local deterministic intent path")
        print("LOCAL SQL:", local_sql)
        print("================================")

        return {
            "intent": "data_analysis",
            "requires_sql": True,
            "original_question": question,
            "local_sql": local_sql.strip().rstrip(";"),

            # Reset stale values from previous questions.
            "additional_question": None,
            "generated_sql": "",
            "query_result": {},
            "analysis": {},
            "final_answer": "",
            "important_points": [],
            "execution_error": "",
            "validation_error": "",
            "analysis_error": None,

            "retry_count": 0,
            "investigation_count": 0,
        }

    # If local routing cannot understand the question,
    # use Gemini as the fallback.
    try:
        llm = get_llm(temperature=0)
        structured_llm = llm.with_structured_output(IntentResult)

        prompt = INTENT_PROMPT.format(
            question=question,
            context=_context_to_text(
                state.get("conversation_history", [])
            ),
        )

        intent_result = structured_llm.invoke(prompt)

        print(f"INTENT: {intent_result.intent}")
        print(f"REQUIRES SQL: {intent_result.requires_sql}")
        print("================================")

        return {
            "intent": intent_result.intent,
            "requires_sql": intent_result.requires_sql,
            "original_question": question,
            "local_sql": None,
            "additional_question": None,
            "retry_count": 0,
            "investigation_count": 0,
        }

    except Exception as exc:
        print("\n========== INTENT ERROR ==========")
        print(type(exc).__name__)
        print(str(exc))
        print("==================================")

        if _is_gemini_quota_error(exc):
            return {
                "intent": "failure",
                "requires_sql": False,
                "original_question": question,
                "final_answer": (
                    "Gemini API quota has been exceeded. "
                    "Please wait for the quota to reset or enable billing."
                ),
                "error_type": "gemini_quota",
            }

        return {
            "intent": "failure",
            "requires_sql": False,
            "original_question": question,
            "final_answer": (
                "The request could not be processed because the AI service "
                "returned an error."
            ),
            "error_type": "intent_error",
        }

# ---------------------------------------------------------------------
# Schema discovery (cheap to recompute; cache at the app layer if needed)
# ---------------------------------------------------------------------

def schema_node(state):
    schema = get_database_schema()
    schema_text = schema_to_text(schema)
    return {"schema_text": schema_text}


# ---------------------------------------------------------------------
# SQL generation
# ---------------------------------------------------------------------

DETERMINISTIC_QUERIES = {
    "how many customers are there": """
        SELECT COUNT(*) AS total_customers
        FROM customers
    """,
    "how many orders are there": """
        SELECT COUNT(*) AS total_orders
        FROM orders
    """,
}


def get_deterministic_sql(question: str):
    normalized = " ".join(question.lower().strip().split())

    print("NORMALIZED QUESTION:", normalized)

    for phrase, sql in DETERMINISTIC_QUERIES.items():
        if phrase in normalized:
            print("MATCHED DETERMINISTIC PHRASE:", phrase)
            return sql.strip()

    print("NO DETERMINISTIC MATCH")
    return None

def generate_sql_node(state):
    print("\n========== GENERATING SQL ==========")

    print("QUESTION:", state.get("question"))
    print("LOCAL SQL RECEIVED:", repr(state.get("local_sql")))
    print(
        "ADDITIONAL QUESTION:",
        repr(state.get("additional_question"))
    )

    # Use locally generated SQL when available.
    local_sql = state.get("local_sql")

    if local_sql:
        print("Using local deterministic SQL path")
        print("GENERATED SQL:", local_sql)
        print("===================================\n")

        return {
            "generated_sql": local_sql.strip().rstrip(";"),
            "sql_explanation": (
                "SQL generated using the local deterministic query router."
            ),
            "execution_error": "",
        }

    # Otherwise use Gemini.
    try:
        print("Using Gemini SQL generation path")

        llm = get_llm(temperature=0)

        structured_llm = llm.with_structured_output(
            SQLGenerationResult
        )

        # Always use the current user question.
        active_question = state["question"]

        print(
            "ACTIVE QUESTION SENT TO SQL PROMPT:",
            active_question
        )

        prompt = SQL_GENERATION_PROMPT.format(
            schema=state["schema_text"],
            metrics=metrics_to_text(),
            context=_context_to_text(
                state.get("conversation_context")
            ),
            question=active_question,
        )

        result = structured_llm.invoke(prompt)

        print("GENERATED SQL:", result.sql)
        print("===================================\n")

        return {
            "generated_sql": result.sql.strip().rstrip(";"),
            "sql_explanation": result.explanation,
            "execution_error": "",
        }

    except Exception as exc:
        print("\n❌ SQL GENERATION ERROR:")
        print(repr(exc))
        print("===================================\n")

        error_text = str(exc)

        if (
            "429" in error_text
            or "RESOURCE_EXHAUSTED" in error_text
            or "quota" in error_text.lower()
            or "free_tier_requests" in error_text
        ):
            friendly_error = (
                "Daily Gemini API quota has been exhausted. "
                "Please try again later or check your Gemini API "
                "usage and billing settings."
            )
        else:
            friendly_error = f"SQL generation failed: {error_text}"

        return {
            "generated_sql": "",
            "sql_explanation": "",
            "execution_error": friendly_error,
        }      
        
# ---------------------------------------------------------------------
# SQL validation
# ---------------------------------------------------------------------

def validate_sql_node(state):
    # Stop validation if an earlier node failed.
    if state.get("execution_error"):
        print(
            "Skipping SQL validation because an earlier error occurred."
        )

        return {
            "sql_valid": False,
            "validation_error": state["execution_error"],
        }

    generated_sql = state.get("generated_sql", "").strip()

    print("\n========== SQL VALIDATION ==========")
    print("SQL RECEIVED:", repr(generated_sql))

    if not generated_sql:
        print("SQL VALIDATION FAILED: No SQL generated")
        print("===================================\n")

        return {
            "sql_valid": False,
            "validation_error": "No SQL was generated.",
        }

    valid, reason = validate_sql(generated_sql)

    print("SQL VALID:", valid)
    print("VALIDATION REASON:", reason)
    print("===================================\n")

    return {
        "sql_valid": valid,
        "validation_error": "" if valid else reason,
    }

# ---------------------------------------------------------------------
# SQL execution
# ---------------------------------------------------------------------

def execute_sql_node(state):
    try:
        print("\n========== EXECUTING SQL ==========")
        print(state.get("generated_sql"))

        result = execute_read_query(state["generated_sql"])

        print("QUERY RESULT:", result)

        df = rows_to_dataframe(result)
        numeric_summary = basic_numeric_summary(df)

        print("SQL EXECUTION SUCCESS")
        print("===================================\n")

        return {
            "query_result": result,
            "numeric_summary": numeric_summary,
            "execution_error": "",
        }

    except Exception as exc:
        print("\n❌ SQL EXECUTION ERROR:")
        print(repr(exc))
        print("===================================\n")

        return {
            "execution_error": str(exc)
        }
# ---------------------------------------------------------------------
# SQL repair
# ---------------------------------------------------------------------

def repair_sql_node(state):
    llm = get_llm(temperature=0)
    structured_llm = llm.with_structured_output(SQLGenerationResult)

    prompt = SQL_REPAIR_PROMPT.format(
        schema=state["schema_text"],
        question=state.get("additional_question") or state["question"],
        sql=state["generated_sql"],
        error=state["execution_error"],
    )

    result = structured_llm.invoke(prompt)

    return {
        "generated_sql": result.sql.strip().rstrip(";"),
        "sql_explanation": result.explanation,
        "retry_count": state.get("retry_count", 0) + 1,
        "execution_error": "",
    }


# ---------------------------------------------------------------------
# Result analysis
# ---------------------------------------------------------------------

def _simple_result_analysis(state):
    """
    Creates a direct answer for a single-row, single-value result
    without making another Gemini API call.
    """

    result = state["query_result"]
    rows = result.get("rows", [])
    columns = result.get("columns", [])

    if len(rows) != 1 or len(columns) != 1:
        return None

    column = columns[0]
    value = rows[0].get(column)

    if value is None:
        summary = "No matching data was found for that question."
    else:
        formatted_column = column.replace("_", " ").capitalize()

        if hasattr(value, "quantize"):
            formatted_value = f"{float(value):,.2f}"
        else:
            formatted_value = str(value)

        summary = f"{formatted_column}: {formatted_value}"

    return {
        "summary": summary,
        "key_findings": [summary],
        "observed_facts": [summary],
        "possible_explanations": [],
        "follow_up_suggestions": [],
    }

def _deterministic_analysis(state):
    result = state.get("query_result", {})
    rows = result.get("rows", [])

    if not rows:
        return {
            "summary": "No matching data was found.",
            "key_findings": [],
            "observed_facts": [],
            "possible_explanations": [],
            "follow_up_suggestions": [],
        }

    row = rows[0]

    if "decline_amount" in row and "month" in row:
        month = row["month"]

        if hasattr(month, "strftime"):
            month_text = month.strftime("%B %Y")
        else:
            month_text = str(month)

        decline = row.get("decline_amount")
        revenue = row.get("revenue")
        previous_revenue = row.get("prev_month_revenue")

        decline_text = f"{float(decline):,.2f}" if decline is not None else "N/A"
        revenue_text = f"{float(revenue):,.2f}" if revenue is not None else "N/A"
        previous_text = (
            f"{float(previous_revenue):,.2f}"
            if previous_revenue is not None
            else "N/A"
        )

        summary = (
            f"The biggest month-over-month revenue decline occurred in "
            f"{month_text}, with a decline of {decline_text}."
        )

        findings = [
            f"Month: {month_text}",
            f"Current revenue: {revenue_text}",
            f"Previous month revenue: {previous_text}",
            f"Revenue decline: {decline_text}",
        ]

        return {
            "summary": summary,
            "key_findings": findings,
            "observed_facts": findings,
            "possible_explanations": [],
            "follow_up_suggestions": [
                "Investigate the product categories and regions contributing to the decline."
            ],
        }

    return None

def analyze_results_node(state):
    print("\n========== RESULT ANALYSIS ==========")

    query_result = state.get("query_result", {})
    rows = query_result.get("rows", [])

    if not rows:
        return {
            "analysis": {
                "summary": "No matching data was found.",
                "key_findings": [],
                "observed_facts": [],
                "possible_explanations": [],
                "follow_up_suggestions": [],
            },
            "analysis_error": None,
            "needs_more_analysis": False,
        }

    # Deterministic analysis for simple one-row, one-column results
    simple_analysis = _simple_result_analysis(state)

    if simple_analysis is not None:
        print("Using deterministic result analysis path")
        print("ANALYSIS:", simple_analysis)
        print("=====================================\n")

        return {
            "analysis": simple_analysis,
            "analysis_error": None,
            "needs_more_analysis": False,
        }

    # Existing deterministic analysis logic
    deterministic_result = _deterministic_analysis(state)

    if deterministic_result is not None:
        print("Using deterministic analysis path")
        print("=====================================\n")

        return {
            "analysis": deterministic_result,
            "analysis_error": None,
            "needs_more_analysis": False,
        }

    print("Using Gemini analysis path")

    try:
        result = query_result

        numeric_summary = state.get("numeric_summary", {})

        llm = get_llm(temperature=0)

        structured_llm = llm.with_structured_output(
            AnalysisResult
        )

        prompt = INSIGHT_PROMPT.format(
            question=(
                state.get("additional_question")
                or state["question"]
            ),
            result=result,
            numeric_summary=numeric_summary_to_text(
                numeric_summary
            ),
        )

        analysis = structured_llm.invoke(prompt)

        print("Gemini analysis completed")
        print("=====================================\n")

        return {
            "analysis": analysis.model_dump(),
            "analysis_error": None,
            "needs_more_analysis": False,
        }

    except Exception as exc:
        print("\n========== ANALYSIS ERROR ==========")
        print(type(exc).__name__)
        print(str(exc))
        print("=====================================\n")

        return {
            "analysis": {
                "summary": "The query completed, but result analysis failed.",
                "key_findings": [
                    "The SQL query executed successfully.",
                    "The analysis model could not format the result.",
                ],
                "observed_facts": [],
                "possible_explanations": [],
                "follow_up_suggestions": [],
            },
            "analysis_error": str(exc),
            "needs_more_analysis": False,
        }

# ---------------------------------------------------------------------
# Investigation (bounded autonomous follow-up queries)
# ---------------------------------------------------------------------

def investigation_node(state):
    investigation_count = state.get("investigation_count", 0)

    print("\n========== INVESTIGATION ==========")
    print("STEP:", investigation_count)
    print("ORIGINAL QUESTION:", state["question"])

    if investigation_count >= settings.max_investigation_steps:
        print("Maximum investigation steps reached")
        print("===================================\n")
        return {"needs_more_analysis": False}

    llm = get_llm(temperature=0)
    structured_llm = llm.with_structured_output(InvestigationDecision)

    prompt = INVESTIGATION_PROMPT.format(
        question=state["question"],
        analysis=state.get("analysis", {}),
    )

    decision = structured_llm.invoke(prompt)

    print("NEEDS MORE DATA:", decision.needs_more_data)
    print("FOLLOW-UP QUESTION:", decision.follow_up_question)
    print("===================================\n")

    if not decision.needs_more_data:
        return {"needs_more_analysis": False}

    return {
        "needs_more_analysis": True,
        "additional_question": decision.follow_up_question,
        "investigation_count": investigation_count + 1,
    }

# ---------------------------------------------------------------------
# Chart planning + rendering plan
# ---------------------------------------------------------------------


def chart_planner_node(state):
    result = state["query_result"]
    rows = result.get("rows", [])

    # Don't create a chart for a single value / single row
    if len(rows) <= 1:
        print("\n========== CHART PLANNER ==========")
        print("Skipping chart: not enough data points")
        print("===================================\n")

        return {
            "chart_plan": {
                "chart_type": "none"
            }
        }

    print("\n========== CHART PLANNER ==========")
    print("Rows available:", len(rows))

    llm = get_llm(temperature=0)
    structured_llm = llm.with_structured_output(ChartPlan)

    prompt = CHART_PROMPT.format(
        question=state["question"],
        columns=result.get("columns"),
        sample_rows=rows[:10],
    )

    plan = structured_llm.invoke(prompt)

    print("CHART TYPE:", plan.chart_type)
    print("===================================\n")

    return {"chart_plan": plan.model_dump()}

# ---------------------------------------------------------------------
# Conversation (non-SQL) replies
# ---------------------------------------------------------------------

def conversation_node(state):
    llm = get_llm(temperature=0.2)
    structured_llm = llm.with_structured_output(ConversationReply)

    prompt = CONVERSATION_PROMPT.format(
        context=_context_to_text(state.get("conversation_context")),
        question=state["question"],
    )

    reply = structured_llm.invoke(prompt)

    return {"final_answer": reply.reply, "important_points": []}


def unsupported_node(state):
    return {
        "final_answer": (
            "I can analyze your business data, but I can't perform "
            "operations that modify the database."
        ),
        "important_points": [],
    }


def failure_node(state):
    error_type = state.get("error_type")

    if error_type == "gemini_quota":
        message = (
            "Gemini API quota has been exceeded for this project. "
            "Please wait for the quota reset or enable billing in Google AI Studio."
        )

    elif state.get("execution_error"):
        message = (
            "The SQL query could not be executed. "
            "Please try rephrasing the question."
        )

    elif state.get("analysis_error"):
        message = (
            "The SQL query completed, but AI analysis failed. "
            "The raw result may still be available."
        )

    else:
        message = "Unable to complete analysis."

    return {
        "final_answer": message,
        "important_points": [],
    }
# ---------------------------------------------------------------------
# Final answer
# ---------------------------------------------------------------------

def final_answer_node(state):
    # Show execution errors instead of a misleading success message.
    if state.get("execution_error"):
        return {
            "final_answer": (
                "### Error\n"
                + state["execution_error"]
            ),
            "important_points": [],
        }
    if state.get("validation_error"):
        return {
            "final_answer": (
                "### SQL Validation Error\n\n"
                + state["validation_error"]
            ),
            "important_points": [],
        }

    analysis = state.get("analysis", {})

    summary = analysis.get(
        "summary",
        "Analysis completed successfully."
    )

    findings = analysis.get("key_findings", [])
    observed_facts = analysis.get("observed_facts", [])
    explanations = analysis.get("possible_explanations", [])
    suggestions = analysis.get("follow_up_suggestions", [])

    sections = []

    sections.append("### Executive Summary\n" + summary)

    if findings:
        sections.append(
            "### Key Findings\n"
            + "\n".join(f"- {item}" for item in findings)
        )

    if observed_facts and observed_facts != findings:
        sections.append(
            "### Supporting Facts\n"
            + "\n".join(f"- {item}" for item in observed_facts)
        )

    if explanations:
        sections.append(
            "### Possible Explanations\n"
            + "\n".join(f"- {item}" for item in explanations)
        )

    if suggestions:
        sections.append(
            "### Suggested Follow-ups\n"
            + "\n".join(f"- {item}" for item in suggestions)
        )

    return {
        "final_answer": "\n\n".join(sections),
        "important_points": findings,
    }

def _is_gemini_quota_error(exc: Exception) -> bool:
    error_text = str(exc).lower()

    quota_terms = [
        "resource_exhausted",
        "quota exceeded",
        "rate limit",
        "429",
        "generate_content_free_tier_requests",
    ]

    return any(term in error_text for term in quota_terms)