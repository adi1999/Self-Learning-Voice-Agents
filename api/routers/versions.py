"""Agent version endpoints."""

from fastapi import APIRouter

from api.schemas.versions import AgentVersionSummary
from api.services.version_service import get_all_versions, get_champion_version, get_version_detail

router = APIRouter(prefix="/api/versions", tags=["versions"])


@router.get("/", response_model=list[AgentVersionSummary])
def list_versions():
    return get_all_versions()


@router.get("/champion")
def champion():
    v = get_champion_version()
    return v.model_dump(mode="json")


@router.get("/{version_id}")
def get_version(version_id: str):
    v = get_version_detail(version_id)
    return v.model_dump(mode="json")
