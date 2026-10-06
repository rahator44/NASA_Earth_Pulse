"""
Live Auto-Reload & Server Heartbeat System.
Provides a modern SSE (Server-Sent Events) stream for development,
allowing frontend clients to automatically reconnect and hot-refresh when
backend code changes or when the server restarts.
"""
import asyncio
import json
import os
import time
from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(prefix="/api/system", tags=["system"])

# Unique session identifier generated once per Python process lifetime.
# When Uvicorn restarts, a new process starts with a new SESSION_ID.
PROCESS_START_TIME = time.time()
SESSION_ID = f"srv_{os.getpid()}_{int(PROCESS_START_TIME * 1000)}"


@router.get("/live-reload")
async def live_reload_sse(once: bool = False):
    """
    Server-Sent Events stream for hot reloading and server health monitoring.
    Clients connect to receive server session events. When Uvicorn restarts,
    the connection drops and on reconnect, the client detects a new SESSION_ID
    and smoothly reloads the page.
    """
    async def event_generator():
        try:
            # Initial handshake with process session ID
            init_payload = {
                "action": "connected",
                "sessionId": SESSION_ID,
                "serverTime": time.time(),
                "pid": os.getpid(),
            }
            yield f"data: {json.dumps(init_payload)}\n\n"

            if once:
                return

            # Periodic heartbeat to maintain connection
            while True:
                await asyncio.sleep(8)
                heartbeat_payload = {
                    "action": "heartbeat",
                    "sessionId": SESSION_ID,
                    "uptime": round(time.time() - PROCESS_START_TIME, 1),
                }
                yield f"data: {json.dumps(heartbeat_payload)}\n\n"
        except asyncio.CancelledError:
            # Client disconnected cleanly
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status-heartbeat")
async def status_heartbeat():
    """Lightweight JSON check for client reconnection detection."""
    return JSONResponse({
        "sessionId": SESSION_ID,
        "pid": os.getpid(),
        "uptime": round(time.time() - PROCESS_START_TIME, 1),
        "status": "online",
    })
