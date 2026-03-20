"""MongoDB CRUD for strategy tactics and failed approaches."""

from core.db import failed_approaches_collection, strategy_tactics_collection
from core.models import FailedApproach, StrategyTactic


def _strip_id(doc: dict) -> dict:
    if doc and "_id" in doc:
        del doc["_id"]
    return doc


# --- Tactics ---

def save_tactic(tactic: StrategyTactic) -> None:
    """Save a strategy tactic to MongoDB."""
    doc = tactic.model_dump(mode="json")
    strategy_tactics_collection.update_one(
        {"id": tactic.id}, {"$set": doc}, upsert=True
    )


def get_tactics_for_persona(persona_type: str, limit: int = 5) -> list[StrategyTactic]:
    """Get top tactics for a persona, ordered by score impact descending."""
    docs = (
        strategy_tactics_collection
        .find({"persona_type": persona_type})
        .sort("score_impact", -1)
        .limit(limit)
    )
    return [StrategyTactic.model_validate(_strip_id(d)) for d in docs]


def get_tactics_for_section(section: str, limit: int = 5) -> list[StrategyTactic]:
    """Get top tactics related to a prompt section."""
    docs = (
        strategy_tactics_collection
        .find({"prompt_section": section})
        .sort("score_impact", -1)
        .limit(limit)
    )
    return [StrategyTactic.model_validate(_strip_id(d)) for d in docs]


def get_top_tactics(limit: int = 5) -> list[StrategyTactic]:
    """Get top tactics across all personas, ordered by score impact."""
    docs = (
        strategy_tactics_collection
        .find()
        .sort("score_impact", -1)
        .limit(limit)
    )
    return [StrategyTactic.model_validate(_strip_id(d)) for d in docs]


def list_all_tactics() -> list[StrategyTactic]:
    """List all tactics, newest first."""
    docs = strategy_tactics_collection.find().sort("created_at", -1)
    return [StrategyTactic.model_validate(_strip_id(d)) for d in docs]


# --- Failed Approaches ---

def save_failed_approach(failure: FailedApproach) -> None:
    """Save a failed approach to MongoDB."""
    doc = failure.model_dump(mode="json")
    failed_approaches_collection.update_one(
        {"id": failure.id}, {"$set": doc}, upsert=True
    )


def get_failures_for_section(section: str, limit: int = 5) -> list[FailedApproach]:
    """Get recent failures for a prompt section."""
    docs = (
        failed_approaches_collection
        .find({"target_section": section})
        .sort("created_at", -1)
        .limit(limit)
    )
    return [FailedApproach.model_validate(_strip_id(d)) for d in docs]


def list_all_failures() -> list[FailedApproach]:
    """List all failed approaches, newest first."""
    docs = failed_approaches_collection.find().sort("created_at", -1)
    return [FailedApproach.model_validate(_strip_id(d)) for d in docs]


def get_playbook_stats() -> dict:
    """Get summary stats for the playbook."""
    total_tactics = strategy_tactics_collection.count_documents({})
    total_failures = failed_approaches_collection.count_documents({})

    # Count by persona
    tactics_by_persona: dict[str, int] = {}
    for doc in strategy_tactics_collection.aggregate([
        {"$group": {"_id": "$persona_type", "count": {"$sum": 1}}}
    ]):
        tactics_by_persona[doc["_id"]] = doc["count"]

    # Count by section
    tactics_by_section: dict[str, int] = {}
    for doc in strategy_tactics_collection.aggregate([
        {"$group": {"_id": "$prompt_section", "count": {"$sum": 1}}}
    ]):
        tactics_by_section[doc["_id"]] = doc["count"]

    failures_by_section: dict[str, int] = {}
    for doc in failed_approaches_collection.aggregate([
        {"$group": {"_id": "$target_section", "count": {"$sum": 1}}}
    ]):
        failures_by_section[doc["_id"]] = doc["count"]

    return {
        "total_tactics": total_tactics,
        "total_failures": total_failures,
        "tactics_by_persona": tactics_by_persona,
        "tactics_by_section": tactics_by_section,
        "failures_by_section": failures_by_section,
    }
