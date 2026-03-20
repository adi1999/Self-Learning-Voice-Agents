"""Service wrapping evaluation judges + save."""

from api.exceptions import NotFoundError
from api.services.conversation_service import get_conversation_detail
from core.archive import save_conversation
from core.models import Conversation, EvalResult
from evaluation.scorer import evaluate_conversation


async def evaluate_conversation_by_id(conversation_id: str) -> Conversation:
    conversation = get_conversation_detail(conversation_id)
    await evaluate_conversation(conversation)
    save_conversation(conversation)
    return conversation
