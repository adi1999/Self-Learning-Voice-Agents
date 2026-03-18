"""FastAPI server with WebRTC signaling for the voice agent."""

import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)
from pipecat.transports.base_transport import TransportParams
from pipecat.audio.vad.silero import SileroVADAnalyzer

from config.settings import PROJECT_ROOT
from core.archive import get_champion, load_version
from voice.pipeline import create_and_run_pipeline

logger = logging.getLogger(__name__)

_version_id: str | None = None


def create_app(version_id: str | None = None) -> FastAPI:
    """Create the FastAPI app for the voice agent."""
    global _version_id
    _version_id = version_id

    app = FastAPI(title="Darwin-Gödel Voice Agent")
    request_handler = SmallWebRTCRequestHandler()

    @app.post("/api/offer")
    async def offer(request: Request):
        """Handle WebRTC offer from the browser client."""
        body = await request.json()

        webrtc_request = SmallWebRTCRequest(
            sdp=body["sdp"],
            type=body.get("type", "offer"),
            pc_id=body.get("pc_id"),
        )

        # Load agent version
        if _version_id:
            agent_version = load_version(_version_id)
        else:
            agent_version = get_champion()
            if not agent_version:
                return JSONResponse(
                    {"error": "No champion version found. Run evolution first."},
                    status_code=404,
                )

        logger.info(f"Starting voice session with {agent_version.id}")

        async def on_connection(webrtc_connection):
            transport = SmallWebRTCTransport(
                webrtc_connection=webrtc_connection,
                params=TransportParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    vad_enabled=True,
                    vad_analyzer=SileroVADAnalyzer(),
                ),
            )
            await create_and_run_pipeline(agent_version, transport, version_id=agent_version.id)

        answer = await request_handler.handle_web_request(webrtc_request, on_connection)
        return JSONResponse(answer)

    # Mount static files for the browser client
    static_dir = PROJECT_ROOT / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
