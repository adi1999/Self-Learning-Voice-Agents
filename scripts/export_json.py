"""Dump all MongoDB collections to data/ as JSON files for GitHub submission."""

import json
from pathlib import Path

from config.settings import ARCHIVE_DIR, CONVERSATIONS_DIR, PROJECT_ROOT
from core.db import agent_versions_collection, conversations_collection, evolution_runs_collection


def export_all() -> None:
    """Export all MongoDB data to JSON files."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)

    versions = list(agent_versions_collection.find({}, {"_id": 0}))
    conversations = list(conversations_collection.find({}, {"_id": 0}))
    runs = list(evolution_runs_collection.find({}, {"_id": 0}))

    (ARCHIVE_DIR / "versions.json").write_text(
        json.dumps(versions, indent=2, default=str)
    )
    (CONVERSATIONS_DIR / "all_conversations.json").write_text(
        json.dumps(conversations, indent=2, default=str)
    )
    (PROJECT_ROOT / "data" / "evolution_runs.json").write_text(
        json.dumps(runs, indent=2, default=str)
    )

    print(f"Exported {len(versions)} versions, {len(conversations)} conversations, {len(runs)} runs")


if __name__ == "__main__":
    export_all()
