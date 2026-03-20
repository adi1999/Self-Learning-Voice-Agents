"""Evolution-related request/response schemas."""

from pydantic import BaseModel, Field

from config.settings import CONVERSATIONS_PER_PERSONA, MAX_GENERATIONS, SCORE_THRESHOLD


class StartEvolutionRequest(BaseModel):
    max_generations: int = Field(default=MAX_GENERATIONS, ge=1, le=20)
    threshold: float = Field(default=SCORE_THRESHOLD, ge=1.0, le=5.0)
    conversations_per_persona: int = Field(default=CONVERSATIONS_PER_PERSONA, ge=1, le=10)
    start_from_champion: bool = True
    resume_run_id: str | None = None


class EvolutionProgress(BaseModel):
    generation: int
    phase: str
    message: str | None = None
    score: float | None = None
