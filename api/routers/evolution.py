"""Evolution run endpoints: list, start, stream, cancel."""

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.dependencies import get_task_manager
from api.exceptions import ConflictError, NotFoundError
from api.schemas.common import TaskResponse
from api.schemas.evolution import StartEvolutionRequest
from api.services.evolution_service import get_run_detail, list_runs, start_evolution
from api.tasks import BackgroundTaskManager, format_sse

router = APIRouter(prefix="/api/evolution/runs", tags=["evolution"])


@router.get("/")
def get_runs():
    return list_runs()


@router.get("/{run_id}")
def get_run(run_id: str):
    detail = get_run_detail(run_id)
    if not detail:
        raise NotFoundError("Evolution run", run_id)
    return detail


@router.post("/", response_model=TaskResponse)
async def create_run(
    req: StartEvolutionRequest,
    tm: BackgroundTaskManager = Depends(get_task_manager),
):
    if tm.has_running_evolution():
        raise ConflictError("An evolution run is already in progress")

    import uuid
    task_id = f"evo_{uuid.uuid4().hex[:8]}"

    await start_evolution(
        task_manager=tm,
        task_id=task_id,
        max_generations=req.max_generations,
        threshold=req.threshold,
        conversations_per_persona=req.conversations_per_persona,
        start_from_champion=req.start_from_champion,
        resume_run_id=req.resume_run_id,
    )

    return TaskResponse(task_id=task_id, status="running")


@router.delete("/{task_id}")
async def cancel_run(
    task_id: str,
    tm: BackgroundTaskManager = Depends(get_task_manager),
):
    if tm.cancel_task(task_id):
        return {"status": "cancelled", "task_id": task_id}
    raise NotFoundError("Running task", task_id)


@router.get("/{task_id}/stream")
async def stream_run(
    task_id: str,
    tm: BackgroundTaskManager = Depends(get_task_manager),
):
    queue = tm.subscribe(task_id)

    async def event_generator():
        while True:
            msg = await queue.get()
            if msg is None:
                yield format_sse("done", {"status": "stream_ended"})
                break
            yield format_sse(msg.get("event", "message"), msg.get("data", {}))

    return StreamingResponse(event_generator(), media_type="text/event-stream")
