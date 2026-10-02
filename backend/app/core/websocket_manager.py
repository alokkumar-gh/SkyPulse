"""
SkyPulse WebSocket Manager
==========================
Production-quality WebSocket connection manager.

Features:
- Per-client connection registry with unique client IDs
- JWT authentication at connect time (decoded server-side)
- RBAC role-based event access enforcement
- Subscription filter engine (category/state/district/city/severity/confidence/bbox)
- Redis Pub/Sub fan-out with in-memory broadcast fallback
- Heartbeat / PING-PONG with idle-timeout disconnect
- Backpressure: per-client message queue with drop-oldest on overflow
- Event coalescing window for high-frequency updates
- Rate limiting per client
- Observability counters
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("skypulse.ws_manager")

# ---------------------------------------------------------------------------
# Message protocol version
# ---------------------------------------------------------------------------
PROTOCOL_VERSION = "1"

# ---------------------------------------------------------------------------
# Roles that can receive various event categories
# ---------------------------------------------------------------------------
PUBLIC_ROLES: Set[str] = {"PUBLIC", "CITIZEN", "ANALYST", "ADMIN", "GOVERNMENT"}
ANALYST_ROLES: Set[str] = {"ANALYST", "ADMIN", "GOVERNMENT"}
ADMIN_ROLES: Set[str] = {"ADMIN"}

# ---------------------------------------------------------------------------
# Observable counters (in-process; Phase 12 will wire Prometheus)
# ---------------------------------------------------------------------------
_metrics: Dict[str, int] = {
    "active_connections": 0,
    "connections_rejected": 0,
    "messages_sent": 0,
    "messages_dropped": 0,
    "subscription_count": 0,
    "reconnects": 0,
    "slow_clients": 0,
}


def get_metrics() -> Dict[str, int]:
    return dict(_metrics)


# ---------------------------------------------------------------------------
# Subscription filter
# ---------------------------------------------------------------------------
@dataclass
class SubscriptionFilter:
    categories: Optional[List[str]] = None
    states: Optional[List[str]] = None
    districts: Optional[List[str]] = None
    cities: Optional[List[str]] = None
    min_severity: int = 1
    max_severity: int = 4
    min_confidence: float = 0.0
    verification_statuses: Optional[List[str]] = None
    source_types: Optional[List[str]] = None
    # Bounding box [west, south, east, north]
    bbox: Optional[Tuple[float, float, float, float]] = None

    def matches(self, event: Dict[str, Any], role: str) -> bool:
        """Return True if the event passes all filters for this subscription."""
        data = event.get("data", {})
        loc = data.get("location", {})

        # Category filter
        if self.categories:
            cat = data.get("category", "")
            if cat not in self.categories:
                return False

        # State filter
        if self.states:
            state = loc.get("state", "")
            if state not in self.states:
                return False

        # District filter
        if self.districts:
            district = loc.get("district", "")
            if district not in self.districts:
                return False

        # City filter
        if self.cities:
            city = loc.get("city", "")
            if city not in self.cities:
                return False

        # Severity filter
        sev = data.get("severity", 1)
        if not (self.min_severity <= sev <= self.max_severity):
            return False

        # Confidence filter
        conf = data.get("confidence", 0.0)
        if conf < self.min_confidence:
            return False

        # Verification status filter
        if self.verification_statuses:
            vs = data.get("verification_status", "UNVERIFIED")
            if vs not in self.verification_statuses:
                return False

        # RBAC: non-public sensitive fields stripped (done at send side, not filter)
        # Analyst-only event types
        event_type = event.get("type", "")
        if event_type in ("weather_event.anomaly",) and role not in ANALYST_ROLES:
            return False

        # Admin-only system events
        if event_type.startswith("system.") and role not in ADMIN_ROLES:
            return False

        # Bounding box filter
        if self.bbox:
            lat = loc.get("latitude")
            lon = loc.get("longitude")
            if lat is not None and lon is not None:
                west, south, east, north = self.bbox
                if not (south <= lat <= north and west <= lon <= east):
                    return False

        return True


# ---------------------------------------------------------------------------
# Connected client record
# ---------------------------------------------------------------------------
@dataclass
class ConnectedClient:
    client_id: str
    websocket: WebSocket
    user_id: Optional[str]
    role: str
    filters: SubscriptionFilter = field(default_factory=SubscriptionFilter)
    connected_at: float = field(default_factory=time.monotonic)
    last_ping_at: float = field(default_factory=time.monotonic)
    last_message_sent_at: float = field(default_factory=time.monotonic)
    # Per-client outbound queue — backpressure
    _queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=200))
    # Per-client rate: messages per 10 s window
    _rate_window_start: float = field(default_factory=time.monotonic)
    _rate_count: int = 0
    _rate_limit: int = 500  # max messages per 10 s window
    # Coalescing: pending cluster_updated events keyed by event_id
    _coalesce_buffer: Dict[str, Tuple[Dict, float]] = field(default_factory=dict)
    COALESCE_WINDOW: float = 2.0  # seconds

    def is_rate_limited(self) -> bool:
        now = time.monotonic()
        if now - self._rate_window_start > 10.0:
            self._rate_window_start = now
            self._rate_count = 0
        self._rate_count += 1
        return self._rate_count > self._rate_limit

    def enqueue(self, message: Dict[str, Any]) -> bool:
        """
        Enqueue message for delivery. Drop oldest if queue is full (backpressure).
        Critical alerts bypass coalescing.
        Returns True if enqueued, False if dropped.
        """
        event_type = message.get("type", "")
        priority = message.get("data", {}).get("priority", "")

        # Coalesce non-critical rapid updates for the same event_id
        if event_type in ("weather_event.updated", "weather_event.cluster_updated"):
            if priority not in ("HIGH", "CRITICAL"):
                event_id = message.get("event_id", "")
                if event_id:
                    self._coalesce_buffer[event_id] = (message, time.monotonic())
                    return True  # deferred

        # Flush coalesced events where window has passed
        self._flush_coalesced()

        if self._queue.full():
            try:
                self._queue.get_nowait()  # drop oldest
                _metrics["messages_dropped"] += 1
            except asyncio.QueueEmpty:
                pass
        try:
            self._queue.put_nowait(message)
            return True
        except asyncio.QueueFull:
            _metrics["messages_dropped"] += 1
            return False

    def _flush_coalesced(self) -> None:
        now = time.monotonic()
        ready = [eid for eid, (_, ts) in self._coalesce_buffer.items()
                 if now - ts >= self.COALESCE_WINDOW]
        for eid in ready:
            msg, _ = self._coalesce_buffer.pop(eid)
            # Upgrade type to cluster_updated to signal batching
            msg = dict(msg)
            msg["type"] = "weather_event.cluster_updated"
            try:
                self._queue.put_nowait(msg)
            except asyncio.QueueFull:
                _metrics["messages_dropped"] += 1

    def flush_all_coalesced(self) -> None:
        """Force-flush all buffered coalesced events (called at heartbeat)."""
        now = time.monotonic()
        ready = list(self._coalesce_buffer.keys())
        for eid in ready:
            msg, _ = self._coalesce_buffer.pop(eid)
            msg = dict(msg)
            msg["type"] = "weather_event.cluster_updated"
            try:
                self._queue.put_nowait(msg)
            except asyncio.QueueFull:
                _metrics["messages_dropped"] += 1


# ---------------------------------------------------------------------------
# Redis Pub/Sub helper (with in-process fallback)
# ---------------------------------------------------------------------------
class RedisFanout:
    """
    Thin wrapper around aioredis pub/sub.
    Falls back to a local asyncio.Queue when Redis is unavailable.
    Redis is ONLY a fan-out mechanism — Kafka remains the durable stream.
    """

    CHANNEL = "skypulse:realtime"

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._publisher = None
        self._subscriber = None
        self._local_queue: asyncio.Queue = asyncio.Queue(maxsize=10_000)
        self._is_live = False

    async def start(self) -> None:
        try:
            import redis.asyncio as aioredis
            self._publisher = aioredis.from_url(
                self._redis_url,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
            await asyncio.wait_for(self._publisher.ping(), timeout=1.0)
            self._subscriber = aioredis.from_url(
                self._redis_url,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
            self._is_live = True
            logger.info("Redis fanout connected to %s", self._redis_url)
        except Exception as exc:
            logger.info("Redis unavailable (%s). Using in-memory broadcast fallback.", exc)
            self._publisher = None
            self._subscriber = None
            self._is_live = False

    async def publish(self, message: Dict[str, Any]) -> None:
        raw = json.dumps(message, default=str)
        if self._is_live and self._publisher:
            try:
                await self._publisher.publish(self.CHANNEL, raw)
                return
            except Exception as exc:
                logger.warning("Redis publish failed: %s. Using local queue.", exc)
        # Local fallback
        if self._local_queue.full():
            self._local_queue.get_nowait()
        await self._local_queue.put(message)

    async def subscribe(self):
        """
        Async generator yielding messages from Redis or local queue.
        """
        if self._is_live and self._subscriber:
            try:
                pubsub = self._subscriber.pubsub()
                await pubsub.subscribe(self.CHANNEL)
                while True:
                    msg = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=0.5
                    )
                    if msg and msg.get("data"):
                        try:
                            yield json.loads(msg["data"])
                        except (json.JSONDecodeError, TypeError):
                            pass
                    else:
                        await asyncio.sleep(0.01)
                return
            except Exception as exc:
                logger.warning("Redis subscriber error: %s. Switching to local queue.", exc)

        # Local fallback
        while True:
            try:
                msg = await asyncio.wait_for(self._local_queue.get(), timeout=0.5)
                yield msg
            except asyncio.TimeoutError:
                yield None  # heartbeat tick

    async def stop(self) -> None:
        try:
            if self._publisher:
                await self._publisher.aclose()
            if self._subscriber:
                await self._subscriber.aclose()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers: event envelope builder
# ---------------------------------------------------------------------------
def build_event_envelope(
    event_type: str,
    event_id: str,
    data: Dict[str, Any],
    *,
    version: str = PROTOCOL_VERSION,
) -> Dict[str, Any]:
    return {
        "version": version,
        "type": event_type,
        "event_id": event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


def strip_sensitive_fields(event: Dict[str, Any], role: str) -> Dict[str, Any]:
    """Remove sensitive intelligence fields for non-analyst roles."""
    if role in ANALYST_ROLES:
        return event
    data = dict(event.get("data", {}))
    # Remove raw source detail and internal AI scores for PUBLIC/CITIZEN
    for key in ("source_type", "source_id", "raw_text", "ai_scores", "anomaly_details"):
        data.pop(key, None)
    return {**event, "data": data}


# ---------------------------------------------------------------------------
# Main WebSocket Manager
# ---------------------------------------------------------------------------

# Maximum connections per process
MAX_CONNECTIONS = 1000
HEARTBEAT_INTERVAL = 25.0   # seconds — match nginx keepalive
IDLE_TIMEOUT = 120.0         # seconds of inactivity before disconnect


class WebSocketManager:
    """
    Central connection registry and event dispatcher for SkyPulse real-time updates.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._clients: Dict[str, ConnectedClient] = {}
        self._fanout = RedisFanout(redis_url)
        self._started = False

    async def startup(self) -> None:
        if self._started:
            return
        await self._fanout.start()
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._dispatch_loop())
        self._started = True
        logger.info("WebSocketManager started (Redis live=%s)", self._fanout._is_live)

    async def shutdown(self) -> None:
        for client_id in list(self._clients.keys()):
            await self._disconnect(client_id, "server_shutdown")
        await self._fanout.stop()

    # -----------------------------------------------------------------------
    # Connection lifecycle
    # -----------------------------------------------------------------------

    async def connect(
        self,
        websocket: WebSocket,
        user_id: Optional[str],
        role: str,
    ) -> Optional[str]:
        """
        Accept the WebSocket and register the client.
        Returns client_id on success, None if rejected.
        """
        if len(self._clients) >= MAX_CONNECTIONS:
            await websocket.close(code=1008, reason="Connection limit reached")
            _metrics["connections_rejected"] += 1
            logger.warning("WS rejected: connection limit %d reached", MAX_CONNECTIONS)
            return None

        client_id = str(uuid.uuid4())
        client = ConnectedClient(
            client_id=client_id,
            websocket=websocket,
            user_id=user_id,
            role=role or "PUBLIC",
        )
        self._clients[client_id] = client
        _metrics["active_connections"] += 1
        logger.info("WS connected: client=%s user=%s role=%s", client_id, user_id, role)

        # Send welcome
        await self._send_to_client(client, build_event_envelope(
            "connection.established",
            client_id,
            {"client_id": client_id, "role": role, "protocol_version": PROTOCOL_VERSION},
        ))
        return client_id

    async def disconnect(self, client_id: str) -> None:
        await self._disconnect(client_id, "client_disconnect")

    async def _disconnect(self, client_id: str, reason: str = "") -> None:
        client = self._clients.pop(client_id, None)
        if client is None:
            return
        _metrics["active_connections"] -= 1
        try:
            await client.websocket.close()
        except Exception:
            pass
        logger.info("WS disconnected: client=%s reason=%s", client_id, reason)

    # -----------------------------------------------------------------------
    # Message handling from client
    # -----------------------------------------------------------------------

    async def handle_message(self, client_id: str, raw: str) -> None:
        """Process an incoming client message."""
        if len(raw) > 8192:
            await self._send_error(client_id, "MESSAGE_TOO_LARGE", "Message exceeds 8 KB limit")
            return

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_error(client_id, "INVALID_JSON", "Message is not valid JSON")
            return

        msg_type = msg.get("type", "")
        client = self._clients.get(client_id)
        if not client:
            return

        if msg_type == "ping":
            client.last_ping_at = time.monotonic()
            await self._send_to_client(client, {"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})

        elif msg_type == "subscribe":
            await self._handle_subscribe(client, msg)

        elif msg_type == "unsubscribe":
            client.filters = SubscriptionFilter()
            _metrics["subscription_count"] = max(0, _metrics["subscription_count"] - 1)
            await self._send_ack(client, "unsubscribed")

        elif msg_type == "disconnect":
            await self._disconnect(client_id, "client_requested")

        else:
            await self._send_error(client_id, "UNKNOWN_MESSAGE_TYPE", f"Unknown type: {msg_type}")

    async def _handle_subscribe(self, client: ConnectedClient, msg: Dict) -> None:
        """Parse subscription filters and update client state."""
        filters_raw = msg.get("filters", {})

        # Validate and parse filter fields
        try:
            bbox = None
            if "bbox" in filters_raw:
                b = filters_raw["bbox"]
                if isinstance(b, (list, tuple)) and len(b) == 4:
                    bbox = tuple(float(x) for x in b)

            new_filter = SubscriptionFilter(
                categories=self._safe_list(filters_raw.get("categories")),
                states=self._safe_list(filters_raw.get("states")),
                districts=self._safe_list(filters_raw.get("districts")),
                cities=self._safe_list(filters_raw.get("cities")),
                min_severity=max(1, int(filters_raw.get("min_severity", 1))),
                max_severity=min(4, int(filters_raw.get("max_severity", 4))),
                min_confidence=max(0.0, float(filters_raw.get("min_confidence", 0.0))),
                verification_statuses=self._safe_list(filters_raw.get("verification_statuses")),
                source_types=self._safe_list(filters_raw.get("source_types")),
                bbox=bbox,
            )
        except (ValueError, TypeError) as exc:
            await self._send_error(client.client_id, "INVALID_FILTER", str(exc))
            return

        client.filters = new_filter
        _metrics["subscription_count"] += 1
        await self._send_ack(client, "subscribed", {"filters_active": True})

    @staticmethod
    def _safe_list(v: Any) -> Optional[List[str]]:
        if v is None:
            return None
        if isinstance(v, list):
            return [str(x) for x in v] or None
        return None

    # -----------------------------------------------------------------------
    # Outbound broadcasting
    # -----------------------------------------------------------------------

    async def broadcast(self, event: Dict[str, Any]) -> None:
        """
        Publish an event to Redis (or local queue) for fan-out.
        All WebSocket instances in the process will pick it up via _dispatch_loop.
        """
        await self._fanout.publish(event)

    async def _dispatch_loop(self) -> None:
        """Continuously pull events from Redis/local and dispatch to matching clients."""
        async for event in self._fanout.subscribe():
            if event is None:
                continue  # heartbeat tick from local-queue generator
            await self._fan_out_event(event)

    async def _fan_out_event(self, event: Dict[str, Any]) -> None:
        """Dispatch an event to all subscribed matching clients."""
        for client in list(self._clients.values()):
            if client.is_rate_limited():
                _metrics["messages_dropped"] += 1
                continue
            if not client.filters.matches(event, client.role):
                continue
            safe_event = strip_sensitive_fields(event, client.role)
            client.enqueue(safe_event)
            asyncio.create_task(self._drain_client_queue(client))

    async def _drain_client_queue(self, client: ConnectedClient) -> None:
        """Drain the client's outbound queue, detecting slow clients."""
        try:
            while not client._queue.empty():
                msg = client._queue.get_nowait()
                await asyncio.wait_for(self._send_to_client(client, msg), timeout=2.0)
                client.last_message_sent_at = time.monotonic()
                _metrics["messages_sent"] += 1
        except asyncio.TimeoutError:
            _metrics["slow_clients"] += 1
            logger.warning("Slow client detected: %s", client.client_id)
        except (WebSocketDisconnect, RuntimeError):
            await self._disconnect(client.client_id, "send_error")
        except Exception as exc:
            logger.warning("WS send error for %s: %s", client.client_id, exc)

    # -----------------------------------------------------------------------
    # Heartbeat loop
    # -----------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            now = time.monotonic()
            for client_id, client in list(self._clients.items()):
                # Flush coalesced events
                client.flush_all_coalesced()
                asyncio.create_task(self._drain_client_queue(client))

                # Idle timeout
                idle = now - client.last_message_sent_at
                if idle > IDLE_TIMEOUT:
                    logger.info("WS idle timeout: client=%s idle=%.0fs", client_id, idle)
                    await self._disconnect(client_id, "idle_timeout")
                    continue

                # Send server ping
                try:
                    await self._send_to_client(client, {
                        "type": "ping",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception:
                    await self._disconnect(client_id, "heartbeat_failed")

    # -----------------------------------------------------------------------
    # Direct user notifications
    # -----------------------------------------------------------------------

    async def send_to_user(self, user_id: str, event: Dict[str, Any]) -> int:
        """Send an event to all connections for a specific user. Returns sent count."""
        sent = 0
        for client in list(self._clients.values()):
            if client.user_id == user_id:
                safe_event = strip_sensitive_fields(event, client.role)
                client.enqueue(safe_event)
                asyncio.create_task(self._drain_client_queue(client))
                sent += 1
        return sent

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    async def _send_to_client(self, client: ConnectedClient, message: Dict[str, Any]) -> None:
        await client.websocket.send_text(json.dumps(message, default=str))

    async def _send_error(self, client_id: str, code: str, message: str) -> None:
        client = self._clients.get(client_id)
        if client:
            await self._send_to_client(client, {
                "type": "error",
                "code": code,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    async def _send_ack(
        self,
        client: ConnectedClient,
        action: str,
        extra: Optional[Dict] = None,
    ) -> None:
        payload = {"type": "ack", "action": action}
        if extra:
            payload.update(extra)
        await self._send_to_client(client, payload)

    # -----------------------------------------------------------------------
    # Status / observability
    # -----------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        return {
            **get_metrics(),
            "redis_live": self._fanout._is_live,
            "connected_clients": len(self._clients),
        }


# ---------------------------------------------------------------------------
# Singleton instance — imported by FastAPI lifespan and WS endpoint
# ---------------------------------------------------------------------------
from app.core.config import settings

ws_manager = WebSocketManager(redis_url=settings.REDIS_URL)
