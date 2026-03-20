"""Shared response schemas."""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str


class TaskResponse(BaseModel):
    task_id: str
    status: str


class SSEEvent(BaseModel):
    event: str
    data: dict
