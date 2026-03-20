"""FastAPI dependency injection functions."""

from fastapi import Request

from api.tasks import BackgroundTaskManager


def get_task_manager(request: Request) -> BackgroundTaskManager:
    return request.app.state.task_manager
