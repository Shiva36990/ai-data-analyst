"""
Structured outputs for every LLM call in the agent.

Every node that calls an LLM asks for one of these shapes via
`llm.with_structured_output(Model)` rather than parsing free text --
this is what keeps the graph's routing logic deterministic.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class IntentResult(BaseModel):
    intent: Literal["analytics", "conversation", "unsupported"]
    requires_sql: bool
    reasoning_summary: str


class SQLGenerationResult(BaseModel):
    sql: str
    explanation: str
    tables_used: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    valid: bool
    reason: str


class AnalysisResult(BaseModel):
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    observed_facts: list[str] = Field(default_factory=list)
    possible_explanations: list[str] = Field(default_factory=list)
    follow_up_suggestions: list[str] = Field(default_factory=list)


class ChartPlan(BaseModel):
    chart_needed: bool
    chart_type: Literal["bar", "line", "scatter", "pie", "area", "none"]
    x_column: Optional[str] = None
    y_column: Optional[str] = None
    color_column: Optional[str] = None
    title: str = ""


class InvestigationDecision(BaseModel):
    needs_more_data: bool
    reason: str
    follow_up_question: str = ""


class ConversationReply(BaseModel):
    reply: str


class FinalResponse(BaseModel):
    answer: str
    important_points: list[str] = Field(default_factory=list)
