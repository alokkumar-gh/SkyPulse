"""
WebSocket API Endpoint — SkyPulse Phase 6
=========================================
WS /ws/events

Authentication:
  - JWT token via ?token= query param (standard for WS; Bearer header not supported in WS handshake)
  - Token validated server-side; role extracted from payload
  - Invalid/expired tokens → immediate close with 4001
  - Do NOT log JWT values

Protocol messages (client → server):
  { "type": "ping" }
  { "type": "subscribe", "filters": {...} }
  { "type": "unsubscribe" }
  { "type": "disconnect" }

Protocol messages (server → client):
  { "version": "1", "type": "connection.established", "event_id": ..., "timestamp": ..., "data": {...} }
  { "version": "1", "type": "weather_event.updated", ... }
  { "version": "1", "type": "weather_event.verified", ... }
  { "version": "1", "type": "weather_event.anomaly", ... }
  { "type": "pong", "timestamp": ... }
  { "type": "ack", "action": "subscribed" | "unsubscribed" }
  { "type": "error", "code": ..., "message": ... }
  { "type": "ping", "timestamp": ... }   (server heartbeat)
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.security import decode_token
from app.core.websocket_manager import ws_manager

logger = logging.getLogger("skypulse.ws_endpoint")

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/events")
async def websocket_events(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None, description="JWT access token"),
):
    """
    Main WebSocket endpoint for real-time weather event delivery.

    Authentication:
      Pass `?token=<JWT>` in the query string.
      Unauthenticated connections are accepted as PUBLIC role (limited events).

    Subscribe to events:
      Send: { "type": "subscribe", "filters": { "states": ["Odisha"], "categories": ["FLOODING"] } }

    Heartbeat:
      Server sends { "type": "ping" } every 25 seconds.
      Client should respond with { "type": "ping" } (treated as pong).
    """
    await websocket.accept()

    # -----------------------------------------------------------------------
    # Authenticate
    # -----------------------------------------------------------------------
    user_id: Optional[str] = None
    role: str = "PUBLIC"

    if token:
        payload = decode_token(token)
        if payload is None:
            # Invalid / expired token — reject
            await websocket.send_json({
                "type": "error",
                "code": "AUTH_FAILED",
                "message": "Invalid or expired token. Connection closed.",
            })
            await websocket.close(code=4001)
            return

        user_id = payload.get("sub")
        role = payload.get("role", "PUBLIC")
        # Validate role is a known value
        if role not in ("PUBLIC", "CITIZEN", "ANALYST", "ADMIN", "GOVERNMENT"):
            role = "PUBLIC"
    # (No token → PUBLIC role — limited access enforced in filter engine)

    # -----------------------------------------------------------------------
    # Register with WebSocket Manager
    # -----------------------------------------------------------------------
    client_id = await ws_manager.connect(websocket, user_id=user_id, role=role)
    if client_id is None:
        # Connection was rejected (limit reached)
        return

    # -----------------------------------------------------------------------
    # Message receive loop
    # -----------------------------------------------------------------------
    try:
        while True:
            raw = await websocket.receive_text()
            await ws_manager.handle_message(client_id, raw)
    except WebSocketDisconnect:
        logger.debug("WS client %s disconnected normally", client_id)
    except Exception as exc:
        logger.warning("WS receive error for client %s: %s", client_id, exc)
    finally:
        await ws_manager.disconnect(client_id)
