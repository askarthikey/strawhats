"""WebSocket endpoint for real-time paper processing status updates."""

import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from starlette.websockets import WebSocketState

router = APIRouter()

# workspace_id -> set of WebSocket connections
_status_connections: Dict[str, Set[WebSocket]] = {}


class PaperStatusBroadcaster:
    """Manages WebSocket connections for paper processing status."""

    @staticmethod
    async def connect(workspace_id: str, websocket: WebSocket):
        await websocket.accept()
        if workspace_id not in _status_connections:
            _status_connections[workspace_id] = set()
        _status_connections[workspace_id].add(websocket)

    @staticmethod
    def disconnect(workspace_id: str, websocket: WebSocket):
        if workspace_id in _status_connections:
            _status_connections[workspace_id].discard(websocket)
            if not _status_connections[workspace_id]:
                del _status_connections[workspace_id]

    @staticmethod
    async def broadcast(workspace_id: str, message: dict):
        """Broadcast a status update to all connected clients in a workspace."""
        if workspace_id not in _status_connections:
            return
        dead = []
        for ws in _status_connections[workspace_id]:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _status_connections[workspace_id].discard(ws)


broadcaster = PaperStatusBroadcaster()


async def notify_paper_status(
    workspace_id: str,
    paper_id: str,
    status: str,
    message: str = "",
    chunk_count: int = 0,
    title: str = "",
):
    """Convenience function to broadcast paper status updates."""
    await broadcaster.broadcast(workspace_id, {
        "type": "paper_status",
        "paper_id": paper_id,
        "status": status,
        "message": message,
        "chunk_count": chunk_count,
        "title": title,
    })


@router.websocket("/ws/papers/status/{workspace_id}")
async def paper_status_ws(websocket: WebSocket, workspace_id: str):
    """WebSocket endpoint for paper processing status updates."""
    await broadcaster.connect(workspace_id, websocket)
    try:
        while True:
            # Keep connection alive, client doesn't send much
            data = await websocket.receive_text()
            # Optional: handle ping/pong
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        broadcaster.disconnect(workspace_id, websocket)
