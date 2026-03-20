"""Conversation-related response schemas."""

from pydantic import BaseModel


class ConversationSummary(BaseModel):
    id: str
    agent_version_id: str
    persona_type: str | None
    source: str
    outcome: str
    duration_turns: int
    weighted_total: float | None
    created_at: str


class ConversationFilters(BaseModel):
    version_id: str | None = None
    persona_type: str | None = None
    source: str | None = None
    outcome: str | None = None
