"""
Wires all nodes into the compiled LangGraph agent.

Flow summary:

  START -> intent
    -> unsupported -> END
    -> conversation -> END
    -> failure -> END
    -> schema -> generate_sql -> validate_sql
         -> [invalid] -> failure -> END
         -> [valid]   -> execute_sql
              -> [error, retries left] -> repair_sql -> validate_sql (loop)
              -> [error, no retries]   -> failure -> END
              -> [success] -> analyze_results
                   -> [investigation question] -> investigation
                        -> [needs more data] -> generate_sql (loop)
                        -> [done] -> final_answer -> END
                   -> [chart requested] -> chart_planner -> final_answer -> END
                   -> [normal question] -> final_answer -> END
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from src.agent.state import AnalystState
from src.agent.nodes import (
    intent_node,
    schema_node,
    generate_sql_node,
    validate_sql_node,
    execute_sql_node,
    repair_sql_node,
    analyze_results_node,
    investigation_node,
    chart_planner_node,
    conversation_node,
    final_answer_node,
    unsupported_node,
    failure_node,
)
from src.agent.routing import (
    route_after_intent,
    route_after_validation,
    route_after_execution,
    route_after_analysis,
    route_after_investigation,
    
)


def build_graph():
    builder = StateGraph(AnalystState)

    builder.add_node("intent", intent_node)
    builder.add_node("schema", schema_node)
    builder.add_node("generate_sql", generate_sql_node)
    builder.add_node("validate_sql", validate_sql_node)
    builder.add_node("execute_sql", execute_sql_node)
    builder.add_node("repair_sql", repair_sql_node)
    builder.add_node("analyze_results", analyze_results_node)
    builder.add_node("investigation", investigation_node)
    builder.add_node("chart_planner", chart_planner_node)
    builder.add_node("conversation", conversation_node)
    builder.add_node("final_answer", final_answer_node)
    builder.add_node("unsupported", unsupported_node)
    builder.add_node("failure", failure_node)

    builder.add_edge(START, "intent")

    builder.add_conditional_edges(
        "intent",
        route_after_intent,
        {
            "schema": "schema",
            "unsupported": "unsupported",
            "conversation": "conversation",
            "failure": "failure",
        },
    )

    builder.add_edge("schema", "generate_sql")
    builder.add_edge("generate_sql", "validate_sql")

    builder.add_conditional_edges(
        "validate_sql",
        route_after_validation,
        {
            "execute_sql": "execute_sql",
            "sql_validation_failed": "failure",
        },
    )

    builder.add_conditional_edges(
        "execute_sql",
        route_after_execution,
        {
            "analyze_results": "analyze_results",
            "repair_sql": "repair_sql",
            "execution_failed": "failure",
        },
    )

    builder.add_edge("repair_sql", "validate_sql")

    builder.add_conditional_edges(
    "analyze_results",
    route_after_analysis,
    {
        "investigation": "investigation",
        "chart_planner": "chart_planner",
        "final_answer": "final_answer",
    },
)

    builder.add_conditional_edges(
        "investigation",
        route_after_investigation,
        {
            "investigate_more": "generate_sql",
            "final_answer": "final_answer",
        },
    )

    builder.add_edge("chart_planner", "final_answer")
    builder.add_edge("final_answer", END)
    builder.add_edge("conversation", END)
    builder.add_edge("unsupported", END)
    builder.add_edge("failure", END)

    return builder


# Development checkpointer. Swap for a PostgreSQL-backed checkpointer
# (langgraph-checkpoint-postgres) before deploying multi-instance.
checkpointer = InMemorySaver()

graph = build_graph().compile(checkpointer=checkpointer)
