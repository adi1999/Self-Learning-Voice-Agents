"""Service bridging evolution/loop.py to BackgroundTaskManager + SSE."""

import logging

from api.tasks import BackgroundTaskManager
from core.archive import get_champion, get_evolution_runs, get_versions_by_run

logger = logging.getLogger(__name__)


def list_runs() -> list[dict]:
    return get_evolution_runs()


def get_run_detail(run_id: str) -> dict | None:
    runs = get_evolution_runs()
    for r in runs:
        if r["id"] == run_id:
            r["versions"] = [
                v.model_dump(mode="json") for v in get_versions_by_run(run_id)
            ]
            return r
    return None


async def start_evolution(
    task_manager: BackgroundTaskManager,
    task_id: str,
    max_generations: int,
    threshold: float,
    conversations_per_persona: int,
    start_from_champion: bool,
    resume_run_id: str | None,
) -> None:
    from evolution.loop import run_evolution

    start_sections = None
    if start_from_champion and not resume_run_id:
        champion = get_champion()
        if champion and champion.scores:
            start_sections = champion.prompt_sections

    def on_progress(data: dict) -> None:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(task_manager.broadcast(task_id, {"event": "progress", "data": data}))
        except RuntimeError:
            pass

    coro = run_evolution(
        max_generations=max_generations,
        threshold=threshold,
        conversations_per_persona=conversations_per_persona,
        on_progress=on_progress,
        resume_run_id=resume_run_id,
        start_sections=start_sections,
    )

    await task_manager.start_task(task_id, coro)
