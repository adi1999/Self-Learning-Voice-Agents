"""Service layer wrapping core/archive.py conversation functions."""

from api.exceptions import NotFoundError
from api.schemas.conversations import ConversationSummary
from core.archive import get_conversations_filtered
from core.models import Conversation


def list_conversations(
    version_id: str | None = None,
    persona_type: str | None = None,
    source: str | None = None,
    outcome: str | None = None,
) -> list[ConversationSummary]:
    convos = get_conversations_filtered(version_id, persona_type, source, outcome)
    return [
        ConversationSummary(
            id=c.id,
            agent_version_id=c.agent_version_id,
            persona_type=c.persona_type,
            source=c.source,
            outcome=c.outcome,
            duration_turns=c.duration_turns,
            weighted_total=c.eval_result.weighted_total if c.eval_result else None,
            created_at=c.created_at.isoformat(),
        )
        for c in convos
    ]


def get_conversation_detail(conversation_id: str) -> Conversation:
    convos = get_conversations_filtered()
    for c in convos:
        if c.id == conversation_id:
            return c
    raise NotFoundError("Conversation", conversation_id)
