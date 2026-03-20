"""Service layer wrapping core/archive.py version functions."""

from api.exceptions import NotFoundError
from api.schemas.versions import AgentVersionSummary
from core.archive import get_champion, list_versions, load_version
from core.models import AgentVersion


def get_all_versions() -> list[AgentVersionSummary]:
    versions = list_versions()
    return [
        AgentVersionSummary(
            id=v.id,
            generation=v.generation,
            status=v.status,
            aggregate_score=v.scores.aggregate if v.scores else None,
            mutation_target=v.mutation_target,
            parent_id=v.parent_id,
            run_id=v.run_id,
        )
        for v in versions
    ]


def get_version_detail(version_id: str) -> AgentVersion:
    try:
        return load_version(version_id)
    except ValueError:
        raise NotFoundError("Version", version_id)


def get_champion_version() -> AgentVersion:
    champion = get_champion()
    if not champion:
        raise NotFoundError("Version", "champion")
    return champion
