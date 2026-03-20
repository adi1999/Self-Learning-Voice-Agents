"""Manages pipecat voice subprocess lifecycle."""

import asyncio
import logging
import subprocess
import signal
import sys

import httpx

logger = logging.getLogger(__name__)

_voice_process: subprocess.Popen | None = None
VOICE_PORT = 8001


def get_voice_status() -> dict:
    global _voice_process
    if _voice_process and _voice_process.poll() is None:
        return {"running": True, "pid": _voice_process.pid, "port": VOICE_PORT}
    return {"running": False, "pid": None, "port": VOICE_PORT}


async def start_voice(version_id: str) -> dict:
    global _voice_process
    if _voice_process and _voice_process.poll() is None:
        return {"running": True, "pid": _voice_process.pid, "message": "Already running", "port": VOICE_PORT, "ready": True}

    _voice_process = subprocess.Popen(
        [sys.executable, "scripts/run_voice.py", "--version", version_id, "--port", str(VOICE_PORT)],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    logger.info(f"Started voice agent (PID {_voice_process.pid}) on port {VOICE_PORT}")

    # Poll /health until the subprocess is accepting connections
    ready = False
    async with httpx.AsyncClient() as client:
        for _ in range(30):
            await asyncio.sleep(1)
            if _voice_process.poll() is not None:
                logger.error("Voice subprocess exited during startup")
                break
            try:
                resp = await client.get(f"http://localhost:{VOICE_PORT}/health", timeout=2.0)
                if resp.status_code == 200:
                    ready = True
                    break
            except httpx.ConnectError:
                continue

    if ready:
        logger.info("Voice server is ready")
    else:
        logger.warning("Voice server did not become ready within 30s")

    return {"running": True, "pid": _voice_process.pid, "message": "Started", "port": VOICE_PORT, "ready": ready}


def stop_voice() -> dict:
    global _voice_process
    if _voice_process and _voice_process.poll() is None:
        pid = _voice_process.pid
        try:
            _voice_process.send_signal(signal.SIGTERM)
            _voice_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning(f"Voice agent (PID {pid}) did not exit after SIGTERM, sending SIGKILL")
            _voice_process.kill()
            _voice_process.wait(timeout=3)
        finally:
            _voice_process = None
        logger.info(f"Stopped voice agent (PID {pid})")
        return {"running": False, "message": "Stopped"}
    _voice_process = None
    return {"running": False, "message": "Was not running"}
