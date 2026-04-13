"""WebSocket endpoint for real-time vehicle updates.

Receives notify pings from tesla-poller via UNIX domain socket,
then broadcasts to connected WebSocket clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger(__name__)

_clients: set[WebSocket] = set()


async def broadcast(data: dict[str, Any]) -> None:
    """Send data to all connected WebSocket clients."""
    if not _clients:
        return
    msg = json.dumps(data)
    disconnected = set()
    for ws in _clients:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.add(ws)
    _clients -= disconnected


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _clients.add(websocket)
    logger.debug("WebSocket client connected (%d total)", len(_clients))
    try:
        while True:
            # Keep connection alive; client can send ping/pong
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)
        logger.debug("WebSocket client disconnected (%d remaining)", len(_clients))
