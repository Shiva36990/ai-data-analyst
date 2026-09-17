"""
Conditional edge functions.

Each function returns a string key that must match one of the
keys in the corresponding add_conditional_edges(...) mapping.
"""

from src.config import settings


def route_after_intent(state):
    """
    Route based on the result of the intent node.
    """

    if state.get("error_type") == "gemini_quota":
        return "failure"

    if state.get("intent") == "failure":
        return "failure"

    if state.get("intent") == "conversation":
        return "conversation"

    if state.get("intent") == "unsupported":
        return "unsupported"

    return "schema"


def route_after_validation(state):
    # Handle errors from SQL generation or validation.
    if state.get("execution_error"):
        return "final_answer"

    # Continue only when SQL validation succeeds.
    if state.get("sql_valid"):
        return "execute_sql"

    return "sql_validation_failed"


def route_after_execution(state):
    if not state.get("execution_error"):
        return "analyze_results"

    retries = state.get("retry_count", 0)

    if retries < settings.max_sql_retries:
        return "repair_sql"

    return "execution_failed"


def _is_investigation_question(question: str) -> bool:
    question = question.lower()

    investigation_terms = [
        "why",
        "reason",
        "cause",
        "explain why",
        "what caused",
        "what is causing",
        "root cause",
    ]

    return any(term in question for term in investigation_terms)


def _is_chart_requested(question: str) -> bool:
    question = question.lower()

    chart_terms = [
        "chart",
        "graph",
        "plot",
        "visualize",
        "visualization",
    ]

    return any(term in question for term in chart_terms)


def route_after_analysis(state):
    question = state.get("question", "")

    if _is_investigation_question(question):
        return "investigation"

    if _is_chart_requested(question):
        return "chart_planner"

    return "final_answer"


def route_after_investigation(state):
    """
    Continue investigation only when the investigation node
    explicitly requests more data.
    """

    if state.get("needs_more_analysis"):
        return "investigate_more"

    return "final_answer"