"""WebSocket handler for real-time collaborative draft editing using Yjs protocol."""

import asyncio
import json
from typing import Dict, Set
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from starlette.websockets import WebSocketState
from bson import ObjectId

from app.database import get_db
from app.utils.helpers import utc_now

router = APIRouter()

# Active rooms: draft_id -> set of connected clients
active_rooms: Dict[str, Dict[str, dict]] = {}
# Document awareness (cursors, selections, user info)
awareness_states: Dict[str, Dict[str, dict]] = {}
# Debounced save timers
save_timers: Dict[str, asyncio.Task] = {}


class CollaborationManager:
    """Manages WebSocket connections for collaborative editing."""

    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = {}
        self.user_info: Dict[str, Dict[str, dict]] = {}  # draft_id -> {conn_id: user_info}

    async def connect(self, draft_id: str, websocket: WebSocket, user: dict):
        """Add a user to the collaboration room."""
        await websocket.accept()

        if draft_id not in self.rooms:
            self.rooms[draft_id] = set()
            self.user_info[draft_id] = {}

        self.rooms[draft_id].add(websocket)
        conn_id = str(id(websocket))
        self.user_info[draft_id][conn_id] = {
            "user_id": user.get("id", ""),
            "full_name": user.get("full_name", "Anonymous"),
            "email": user.get("email", ""),
            "color": self._assign_color(draft_id),
            "cursor": None,
            "selection": None,
        }

        # Notify others about new user
        await self.broadcast(draft_id, {
            "type": "user_join",
            "user": self.user_info[draft_id][conn_id],
            "active_users": list(self.user_info[draft_id].values()),
        }, exclude=websocket)

        # Send current state to new user
        await websocket.send_json({
            "type": "init",
            "active_users": list(self.user_info[draft_id].values()),
        })

        return conn_id

    def disconnect(self, draft_id: str, websocket: WebSocket, conn_id: str):
        """Remove a user from the collaboration room."""
        if draft_id in self.rooms:
            self.rooms[draft_id].discard(websocket)
            user_info = self.user_info.get(draft_id, {}).pop(conn_id, None)

            if not self.rooms[draft_id]:
                del self.rooms[draft_id]
                if draft_id in self.user_info:
                    del self.user_info[draft_id]

            return user_info
        return None

    async def broadcast(self, draft_id: str, message: dict, exclude: WebSocket = None):
        """Broadcast a message to all connected clients in a room."""
        if draft_id not in self.rooms:
            return

        dead_connections = []
        for ws in self.rooms[draft_id]:
            if ws == exclude:
                continue
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)

        for ws in dead_connections:
            self.rooms[draft_id].discard(ws)

    def _assign_color(self, draft_id: str) -> str:
        """Assign a unique color to a user."""
        colors = [
            "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4",
            "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F",
            "#BB8FCE", "#85C1E9", "#F0B27A", "#82E0AA",
        ]
        used = len(self.user_info.get(draft_id, {}))
        return colors[used % len(colors)]

    def get_active_users(self, draft_id: str) -> list:
        """Get list of active users in a room."""
        return list(self.user_info.get(draft_id, {}).values())


manager = CollaborationManager()


async def _debounced_save(draft_id: str, content: str, delay: float = 2.0):
    """Save draft content with debouncing."""
    await asyncio.sleep(delay)
    db = get_db()
    try:
        await db.drafts.update_one(
            {"_id": ObjectId(draft_id)},
            {"$set": {
                "content_markdown": content,
                "updated_at": utc_now(),
            }},
        )
    except Exception as e:
        print(f"Auto-save failed for draft {draft_id}: {e}")


def schedule_save(draft_id: str, content: str):
    """Schedule a debounced save, cancelling any existing timer."""
    if draft_id in save_timers:
        save_timers[draft_id].cancel()
    save_timers[draft_id] = asyncio.create_task(_debounced_save(draft_id, content))


@router.websocket("/ws/drafts/{draft_id}")
async def draft_collaboration(websocket: WebSocket, draft_id: str):
    """WebSocket endpoint for real-time draft collaboration."""
    # Simple auth via query param (token)
    token = websocket.query_params.get("token", "")
    user = None

    if token:
        try:
            from app.auth.dependencies import decode_token
            user = decode_token(token)
        except Exception:
            pass

    if not user:
        await websocket.close(code=4001, reason="Authentication required")
        return

    conn_id = await manager.connect(draft_id, websocket, user)

    # Send the current document content
    db = get_db()
    try:
        draft = await db.drafts.find_one({"_id": ObjectId(draft_id)})
        if draft:
            await websocket.send_json({
                "type": "document",
                "content": draft.get("content_markdown", ""),
                "title": draft.get("title", ""),
                "version": draft.get("version", 1),
            })
    except Exception as e:
        print(f"Failed to load draft {draft_id}: {e}")

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "operation":
                # Client sent a text operation (insert/delete)
                content = data.get("content", "")
                # Auto-save with debouncing
                schedule_save(draft_id, content)
                # Broadcast to all other clients
                await manager.broadcast(draft_id, {
                    "type": "operation",
                    "content": content,
                    "user_id": user.get("id", ""),
                    "version": data.get("version", 0),
                }, exclude=websocket)

            elif msg_type == "cursor":
                # Client sent cursor position update
                conn_info = manager.user_info.get(draft_id, {}).get(conn_id, {})
                if conn_info:
                    conn_info["cursor"] = data.get("position")
                    conn_info["selection"] = data.get("selection")

                await manager.broadcast(draft_id, {
                    "type": "cursor",
                    "user_id": user.get("id", ""),
                    "full_name": user.get("full_name", ""),
                    "color": conn_info.get("color", "#FF6B6B") if conn_info else "#FF6B6B",
                    "position": data.get("position"),
                    "selection": data.get("selection"),
                }, exclude=websocket)

            elif msg_type == "title_update":
                # Client updated the title
                title = data.get("title", "")
                try:
                    await db.drafts.update_one(
                        {"_id": ObjectId(draft_id)},
                        {"$set": {"title": title, "updated_at": utc_now()}},
                    )
                except Exception:
                    pass
                await manager.broadcast(draft_id, {
                    "type": "title_update",
                    "title": title,
                    "user_id": user.get("id", ""),
                }, exclude=websocket)

            elif msg_type == "save":
                # Force save
                content = data.get("content", "")
                try:
                    await db.drafts.update_one(
                        {"_id": ObjectId(draft_id)},
                        {"$set": {
                            "content_markdown": content,
                            "updated_at": utc_now(),
                        }},
                    )
                    await websocket.send_json({"type": "saved", "timestamp": utc_now()})
                except Exception as e:
                    await websocket.send_json({"type": "save_error", "error": str(e)})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error for draft {draft_id}: {e}")
    finally:
        user_info = manager.disconnect(draft_id, websocket, conn_id)
        if user_info:
            await manager.broadcast(draft_id, {
                "type": "user_leave",
                "user": user_info,
                "active_users": manager.get_active_users(draft_id),
            })
