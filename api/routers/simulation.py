"""Simulation endpoints: trigger + stream."""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.dependencies import get_task_manager
from api.schemas.common import TaskResponse
from api.schemas.simulation import SimulateRequest
from api.services.simulation_service import start_simulation
from api.tasks import BackgroundTaskManager, format_sse

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


@router.post("/", response_model=TaskResponse)
async def simulate(
    req: SimulateRequest,
    tm: BackgroundTaskManager = Depends(get_task_manager),
):
    task_id = f"sim_{uuid.uuid4().hex[:8]}"

    await start_simulation(
        task_manager=tm,
        task_id=task_id,
        version_id=req.version_id,
        persona=req.persona,
        evaluate=req.evaluate,
    )

    return TaskResponse(task_id=task_id, status="running")


@router.get("/{task_id}/stream")
async def stream_simulation(
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
