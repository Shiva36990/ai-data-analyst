"""
Shared state passed between every node in the agent graph.

total=False means every key is optional -- each node only needs to
return the keys it actually updates; LangGraph merges the rest.
"""

from typing import TypedDict, Any


class AnalystState(TypedDict, total=False):
    question: str
    conversation_context: list[dict]

    intent: str
    requires_sql: bool

    schema_text: str

    generated_sql: str
    sql_explanation: str

    sql_valid: bool
    validation_error: str

    execution_error: str
    retry_count: int

    query_result: dict
    numeric_summary: dict

    analysis: dict

    needs_more_analysis: bool
    additional_question: str
    investigation_count: int

    chart_plan: dict

    final_answer: str
    important_points: list[str]
