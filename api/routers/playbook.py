"""Playbook endpoints: accumulated tactics and failed approaches."""

from fastapi import APIRouter

from api.services.playbook_service import (
    get_all_failures,
    get_all_tactics,
    get_persona_tactics,
    get_stats,
)

router = APIRouter(prefix="/api/playbook", tags=["playbook"])


@router.get("/tactics")
def list_tactics():
    tactics = get_all_tactics()
    return [t.model_dump(mode="json") for t in tactics]


@router.get("/tactics/{persona_type}")
def tactics_by_persona(persona_type: str):
    tactics = get_persona_tactics(persona_type)
    return [t.model_dump(mode="json") for t in tactics]


@router.get("/failures")
def list_failures():
    failures = get_all_failures()
    return [f.model_dump(mode="json") for f in failures]


@router.get("/stats")
def playbook_stats():
    return get_stats()
