"""Simulation-related request/response schemas."""

from pydantic import BaseModel


class SimulateRequest(BaseModel):
    version_id: str
    persona: str
    evaluate: bool = True


class SimulationProgress(BaseModel):
    turn_index: int
    role: str
    content: str
