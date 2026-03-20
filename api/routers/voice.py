"""Voice agent management endpoints, including WebRTC offer proxy."""

import asyncio

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.services.voice_service import VOICE_PORT, get_voice_status, start_voice, stop_voice

router = APIRouter(prefix="/api/voice", tags=["voice"])


class StartVoiceRequest(BaseModel):
    version_id: str


class OfferRequest(BaseModel):
    sdp: str
    type: str = "offer"


@router.get("/status")
def voice_status():
    return get_voice_status()


@router.post("/start")
async def voice_start(req: StartVoiceRequest):
    return await start_voice(req.version_id)


@router.post("/stop")
def voice_stop():
    return stop_voice()


@router.post("/offer")
async def voice_offer(req: OfferRequest):
    """Proxy WebRTC SDP offer to the pipecat voice subprocess, retrying until it's ready."""
    url = f"http://localhost:{VOICE_PORT}/api/offer"
    payload = {"sdp": req.sdp, "type": req.type}

    async with httpx.AsyncClient() as client:
        for attempt in range(20):
            try:
                resp = await client.post(url, json=payload, timeout=10.0)
                return resp.json()
            except httpx.ConnectError:
                if attempt == 19:
                    return JSONResponse(
                        status_code=503,
                        content={"error": "Voice server not ready. Wait a few seconds and try again."},
                    )
                await asyncio.sleep(1)
