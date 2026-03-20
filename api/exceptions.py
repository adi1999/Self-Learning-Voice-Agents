"""Custom exceptions and global error handlers for the API."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class NotFoundError(Exception):
    def __init__(self, resource: str, identifier: str):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} '{identifier}' not found")


class ConflictError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class TaskNotRunningError(Exception):
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Task '{task_id}' is not running")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": str(exc), "resource": exc.resource, "identifier": exc.identifier},
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError):
        return JSONResponse(
            status_code=409,
            content={"error": exc.message},
        )

    @app.exception_handler(TaskNotRunningError)
    async def task_not_running_handler(request: Request, exc: TaskNotRunningError):
        return JSONResponse(
            status_code=404,
            content={"error": str(exc), "task_id": exc.task_id},
        )
