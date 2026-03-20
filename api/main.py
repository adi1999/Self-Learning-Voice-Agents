"""FastAPI app factory: lifespan, CORS, router registration."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.exceptions import register_exception_handlers
from api.routers import config, conversations, evaluation, evolution, playbook, simulation, story, versions, voice
from api.tasks import BackgroundTaskManager
from config.settings import BASE_PROMPT_PATH, PROJECT_ROOT
from core.archive import list_versions, save_version
from core.models import AgentVersion
from core.prompt_builder import load_base_prompt

logger = logging.getLogger(__name__)


def _ensure_v0() -> None:
    """Seed v0 into MongoDB from base_v0.yaml if no versions exist."""
    if list_versions():
        return
    sections = load_base_prompt(BASE_PROMPT_PATH)
    v0 = AgentVersion(id="v0", generation=0, prompt_sections=sections, status="base")
    save_version(v0)
    logger.info("Seeded v0 from base prompt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.task_manager = BackgroundTaskManager()
    _ensure_v0()
    logger.info("API server started")
    yield
    await app.state.task_manager.shutdown()
    logger.info("API server stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Darwin-Godel API", lifespan=lifespan)

    # CORS for React dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register exception handlers
    register_exception_handlers(app)

    # Register routers
    app.include_router(versions.router)
    app.include_router(conversations.router)
    app.include_router(evolution.router)
    app.include_router(simulation.router)
    app.include_router(evaluation.router)
    app.include_router(voice.router)
    app.include_router(playbook.router)
    app.include_router(story.router)
    app.include_router(config.router)

    # Serve React production build if it exists
    frontend_dist = PROJECT_ROOT / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app
