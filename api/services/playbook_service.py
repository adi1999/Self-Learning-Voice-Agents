"""Service layer for playbook data."""

from core.models import FailedApproach, StrategyTactic
from core.playbook import (
    get_playbook_stats,
    get_tactics_for_persona,
    list_all_failures,
    list_all_tactics,
)


def get_all_tactics() -> list[StrategyTactic]:
    return list_all_tactics()


def get_all_failures() -> list[FailedApproach]:
    return list_all_failures()


def get_persona_tactics(persona_type: str) -> list[StrategyTactic]:
    return get_tactics_for_persona(persona_type, limit=20)


def get_stats() -> dict:
    return get_playbook_stats()
