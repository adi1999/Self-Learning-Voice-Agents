"""Version-related response schemas."""

from pydantic import BaseModel


class AgentVersionSummary(BaseModel):
    id: str
    generation: int
    status: str
    aggregate_score: float | None
    mutation_target: str | None
    parent_id: str | None
    run_id: str | None
