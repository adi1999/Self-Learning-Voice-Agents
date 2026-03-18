"""Pydantic data models for the evolution system."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class PersonaConfig(BaseModel):
    archetype: str
    name: str
    loan_amount: float
    months_overdue: int
    backstory: str


class TurnAnnotation(BaseModel):
    turn_index: int
    issue_type: str
    description: str


class Turn(BaseModel):
    index: int
    role: Literal["agent", "borrower"]
    content: str
    timestamp: datetime | None = None
    annotations: list[TurnAnnotation] = Field(default_factory=list)


class ConversationMetadata(BaseModel):
    model_used: str
    total_tokens: int | None = None
    duration_seconds: float | None = None
    cost_estimate_usd: float | None = None


class EvalResult(BaseModel):
    goal_completion: float
    conversational_quality: float
    compliance: float
    response_consistency: float = 1.0
    sentiment_shift: float = 0.0
    weighted_total: float
    turn_annotations: list[TurnAnnotation] = Field(default_factory=list)
    hallucinations_found: list[str] = Field(default_factory=list)
    tone_assessment: str = "appropriate"
    consistency_issues: list[str] = Field(default_factory=list)


class Conversation(BaseModel):
    id: str
    agent_version_id: str
    persona_type: str | None = None
    persona_config: PersonaConfig | None = None
    source: Literal["simulation", "voice_live"] = "simulation"
    turns: list[Turn]
    outcome: Literal["success", "rejection", "hallucination", "timeout", "ended_by_user"]
    duration_turns: int
    eval_result: EvalResult | None = None
    metadata: ConversationMetadata | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricScores(BaseModel):
    goal_completion: float
    conversational_quality: float
    compliance: float
    response_consistency: float = 1.0
    sentiment_shift: float = 0.0
    weighted_total: float


class PersonaScores(BaseModel):
    per_persona: dict[str, MetricScores]
    aggregate: float


class TurnReference(BaseModel):
    conversation_id: str
    turn_index: int
    content: str


class FailurePattern(BaseModel):
    description: str
    target_section: str
    example_turns: list[TurnReference]
    suggested_direction: str


class AgentVersion(BaseModel):
    id: str
    run_id: str | None = None
    parent_id: str | None = None
    generation: int
    prompt_sections: dict[str, str]
    mutation_target: str | None = None
    rationale: str | None = None
    failure_patterns: list[str] = Field(default_factory=list)
    scores: PersonaScores | None = None
    status: Literal["base", "promoted", "archived"] = "base"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
