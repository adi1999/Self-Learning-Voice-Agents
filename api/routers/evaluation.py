"""Evaluation endpoint."""

from fastapi import APIRouter

from api.schemas.evaluation import EvaluateRequest
from api.services.evaluation_service import evaluate_conversation_by_id

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.post("/")
async def evaluate(req: EvaluateRequest):
    conversation = await evaluate_conversation_by_id(req.conversation_id)
    return conversation.model_dump(mode="json")
