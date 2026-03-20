"""Background task manager with SSE subscriber support."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manages async background tasks with SSE fan-out to subscribers."""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._results: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def start_task(self, task_id: str, coro) -> None:
        async with self._lock:
            if task_id in self._tasks and not self._tasks[task_id].done():
                raise RuntimeError(f"Task {task_id} is already running")
            self._subscribers[task_id] = []
            self._results[task_id] = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}

            async def _wrapper():
                try:
                    result = await coro
                    self._results[task_id]["status"] = "completed"
                    self._results[task_id]["result"] = str(result) if result else None
                    await self.broadcast(task_id, {"event": "complete", "data": {"status": "completed"}})
                except asyncio.CancelledError:
                    self._results[task_id]["status"] = "cancelled"
                    await self.broadcast(task_id, {"event": "cancelled", "data": {"status": "cancelled"}})
                except Exception as e:
                    logger.error(f"Task {task_id} failed: {e}", exc_info=True)
                    self._results[task_id]["status"] = "failed"
                    self._results[task_id]["error"] = str(e)
                    await self.broadcast(task_id, {"event": "error", "data": {"error": str(e)}})
                finally:
                    # Close all subscriber queues
                    for q in self._subscribers.get(task_id, []):
                        await q.put(None)

            self._tasks[task_id] = asyncio.create_task(_wrapper())

    async def broadcast(self, task_id: str, message: dict) -> None:
        for q in self._subscribers.get(task_id, []):
            await q.put(message)

    def subscribe(self, task_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(task_id, []).append(q)
        return q

    def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def get_status(self, task_id: str) -> dict | None:
        return self._results.get(task_id)

    def is_running(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        return task is not None and not task.done()

    def has_running_evolution(self) -> bool:
        for tid, task in self._tasks.items():
            if tid.startswith("evo_") and not task.done():
                return True
        return False

    async def shutdown(self) -> None:
        for task_id, task in self._tasks.items():
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)


def format_sse(event: str, data: Any) -> str:
    """Format a message as an SSE string."""
    json_data = json.dumps(data) if not isinstance(data, str) else data
    return f"event: {event}\ndata: {json_data}\n\n"
