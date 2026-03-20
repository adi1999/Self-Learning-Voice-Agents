"""Evaluation-related request schemas."""

from pydantic import BaseModel


class EvaluateRequest(BaseModel):
    conversation_id: str
