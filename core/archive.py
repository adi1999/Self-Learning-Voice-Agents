"""Archive CRUD: save/load/query agent versions and conversations via MongoDB."""

from core.db import agent_versions_collection, conversations_collection, evolution_runs_collection
from core.models import AgentVersion, Conversation


def _strip_id(doc: dict) -> dict:
    """Remove MongoDB _id before passing to Pydantic."""
    if doc and "_id" in doc:
        del doc["_id"]
    return doc


def save_version(version: AgentVersion) -> None:
    """Save an agent version to MongoDB."""
    doc = version.model_dump(mode="json")
    agent_versions_collection.update_one(
        {"id": version.id}, {"$set": doc}, upsert=True
    )


def load_version(version_id: str) -> AgentVersion:
    """Load an agent version from MongoDB."""
    doc = agent_versions_collection.find_one({"id": version_id})
    if not doc:
        raise ValueError(f"Version {version_id} not found")
    return AgentVersion.model_validate(_strip_id(doc))


def list_versions() -> list[AgentVersion]:
    """List all agent versions, sorted by generation."""
    docs = agent_versions_collection.find().sort("generation", 1)
    return [AgentVersion.model_validate(_strip_id(d)) for d in docs]


def get_champion() -> AgentVersion | None:
    """Get the current champion (highest-scoring promoted or base version)."""
    versions = list_versions()
    promoted = [v for v in versions if v.status in ("promoted", "base")]
    if not promoted:
        return None
    return max(promoted, key=lambda v: v.scores.aggregate if v.scores else -1)


def save_conversation(conversation: Conversation) -> None:
    """Save a conversation to MongoDB."""
    doc = conversation.model_dump(mode="json")
    conversations_collection.update_one(
        {"id": conversation.id}, {"$set": doc}, upsert=True
    )


def load_conversations(version_id: str) -> list[Conversation]:
    """Load all conversations for a given agent version."""
    docs = conversations_collection.find({"agent_version_id": version_id})
    return [Conversation.model_validate(_strip_id(d)) for d in docs]


def get_conversations_filtered(
    version_id: str | None = None,
    persona_type: str | None = None,
    source: str | None = None,
    outcome: str | None = None,
) -> list[Conversation]:
    """Query conversations with optional filters."""
    query: dict = {}
    if version_id:
        query["agent_version_id"] = version_id
    if persona_type:
        query["persona_type"] = persona_type
    if source:
        query["source"] = source
    if outcome:
        query["outcome"] = outcome
    docs = conversations_collection.find(query).sort("created_at", -1)
    return [Conversation.model_validate(_strip_id(d)) for d in docs]


def save_evolution_run(run_data: dict) -> None:
    """Save evolution run metadata."""
    evolution_runs_collection.update_one(
        {"id": run_data["id"]}, {"$set": run_data}, upsert=True
    )


def get_evolution_runs() -> list[dict]:
    """Get all evolution runs."""
    docs = evolution_runs_collection.find().sort("start_time", -1)
    return [_strip_id(d) for d in docs]


def get_versions_by_run(run_id: str) -> list[AgentVersion]:
    """Get all versions created in a specific evolution run."""
    docs = agent_versions_collection.find({"run_id": run_id}).sort("generation", 1)
    return [AgentVersion.model_validate(_strip_id(d)) for d in docs]
