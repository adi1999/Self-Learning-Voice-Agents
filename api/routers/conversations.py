"""Conversation query endpoints."""

from fastapi import APIRouter, Query

from api.schemas.conversations import ConversationSummary
from api.services.conversation_service import get_conversation_detail, list_conversations

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("/", response_model=list[ConversationSummary])
def get_conversations(
    version_id: str | None = Query(None),
    persona_type: str | None = Query(None),
    source: str | None = Query(None),
    outcome: str | None = Query(None),
):
    return list_conversations(version_id, persona_type, source, outcome)


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str):
    c = get_conversation_detail(conversation_id)
    return c.model_dump(mode="json")
