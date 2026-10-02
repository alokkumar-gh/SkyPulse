"""
Real-Time Event Gateway — SkyPulse Phase 6
==========================================
Consumes Kafka topics:
  - skypulse.ai_processed
  - skypulse.verification_updates
  - skypulse.anomalies

Maps them to WebSocket event envelopes and broadcasts via the WebSocketManager
(which handles Redis pub/sub fan-out internally).

Mapping:
  ai_processed          → weather_event.updated
  verification_updates  → weather_event.verified | weather_event.updated
  anomalies             → weather_event.anomaly
  propagation events    → weather_event.propagation_detected
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.websocket_manager import build_event_envelope, ws_manager
from connectors.kafka_bus import (
    KafkaBusConsumer,
    TOPIC_AI_PROCESSED,
    TOPIC_VERIFICATION_UPDATES,
    TOPIC_ANOMALIES,
    kafka_producer,
)

logger = logging.getLogger("skypulse.realtime_gateway")


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------

def _extract_location(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "city": data.get("primary_city") or data.get("location_city"),
        "district": data.get("primary_district") or data.get("location_district"),
        "state": data.get("primary_state") or data.get("location_state"),
        "latitude": data.get("centroid_lat") or data.get("location_lat"),
        "longitude": data.get("centroid_lon") or data.get("location_lon"),
    }


def map_ai_processed(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map skypulse.ai_processed → weather_event.updated"""
    event_id = str(payload.get("event_id") or payload.get("report_id") or "")
    if not event_id:
        return None

    return build_event_envelope(
        event_type="weather_event.updated",
        event_id=event_id,
        data={
            "report_id": str(payload.get("report_id", "")),
            "event_id": event_id,
            "category": payload.get("category", "UNKNOWN"),
            "severity": payload.get("severity", 1),
            "confidence": payload.get("confidence", 0.0),
            "verification_status": payload.get("verification_status", "UNVERIFIED"),
            "source_type": payload.get("source_type"),
            "is_anomalous": payload.get("is_anomalous", False),
            "duplicate_type": payload.get("duplicate_type"),
            "evidence_count": payload.get("evidence_count", 1),
            "location": _extract_location(payload),
            "is_demo": payload.get("is_demo", False),
        },
    )


def map_verification_update(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map skypulse.verification_updates → weather_event.verified | weather_event.updated"""
    event_id = str(payload.get("event_id", ""))
    if not event_id:
        return None

    status = payload.get("verification_status", "UNVERIFIED")
    event_type = "weather_event.verified" if status == "VERIFIED" else (
        "weather_event.rejected" if status == "CONTRADICTED" else "weather_event.updated"
    )

    return build_event_envelope(
        event_type=event_type,
        event_id=event_id,
        data={
            "event_id": event_id,
            "verification_status": status,
            "confidence": payload.get("confidence_score", 0.0),
            "explanation": payload.get("explanation", ""),
            "category": payload.get("category"),
            "severity": payload.get("severity", 1),
            "location": _extract_location(payload),
            "verified_at": payload.get("verified_at") or datetime.now(timezone.utc).isoformat(),
        },
    )


def map_anomaly(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map skypulse.anomalies → weather_event.anomaly"""
    event_id = str(payload.get("event_id") or payload.get("report_id") or "")
    if not event_id:
        return None

    return build_event_envelope(
        event_type="weather_event.anomaly",
        event_id=event_id,
        data={
            "event_id": event_id,
            "report_id": str(payload.get("report_id", "")),
            "anomaly_type": payload.get("anomaly_type", "UNKNOWN"),
            "anomaly_score": payload.get("anomaly_score", 0.0),
            "category": payload.get("category", "UNKNOWN"),
            "severity": payload.get("severity", 1),
            "confidence": payload.get("confidence", 0.0),
            "location": _extract_location(payload),
            "description": payload.get("description", "Anomalous weather activity detected"),
            "priority": "HIGH",
        },
    )


# ---------------------------------------------------------------------------
# Gateway Worker
# ---------------------------------------------------------------------------
class RealtimeGateway:
    """
    Subscribes to AI/verification/anomaly Kafka topics and broadcasts
    to the WebSocket manager.
    """

    def __init__(self):
        self._running = False
        self._consumers = []
        self._tasks = []

    async def start(self) -> None:
        """Start all topic consumers as background tasks."""
        self._running = True
        await ws_manager.startup()

        self._consumers = [
            (KafkaBusConsumer(
                topic=TOPIC_AI_PROCESSED,
                group_id="skypulse.realtime.ai",
                producer=kafka_producer,
            ), map_ai_processed),
            (KafkaBusConsumer(
                topic=TOPIC_VERIFICATION_UPDATES,
                group_id="skypulse.realtime.verification",
                producer=kafka_producer,
            ), map_verification_update),
            (KafkaBusConsumer(
                topic=TOPIC_ANOMALIES,
                group_id="skypulse.realtime.anomalies",
                producer=kafka_producer,
            ), map_anomaly),
        ]

        for consumer, mapper in self._consumers:
            await consumer.start()

        self._tasks = [
            asyncio.create_task(self._consume_loop(consumer, mapper))
            for consumer, mapper in self._consumers
        ]

        logger.info("RealtimeGateway started: %d topic consumers active", len(self._tasks))

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        for consumer, _ in self._consumers:
            await consumer.stop()
        await ws_manager.shutdown()
        logger.info("RealtimeGateway stopped")

    async def _consume_loop(self, consumer, mapper) -> None:
        """Continuous consume/map/broadcast loop for a single topic."""
        while self._running:
            try:
                await consumer.consume_one(
                    handler=self._make_handler(mapper),
                    timeout_seconds=0.5,
                )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Gateway consumer loop error on %s: %s", consumer.topic, exc)
                await asyncio.sleep(1.0)

    def _make_handler(self, mapper):
        async def _handler(payload: Dict[str, Any]) -> None:
            ws_event = mapper(payload)
            if ws_event:
                await ws_manager.broadcast(ws_event)
                logger.debug("Gateway broadcast: type=%s event_id=%s",
                             ws_event.get("type"), ws_event.get("event_id"))
        return _handler

    # -----------------------------------------------------------------------
    # Utility: publish to gateway from within the AI worker
    # -----------------------------------------------------------------------
    async def publish_propagation_alert(
        self,
        event_id: str,
        from_location: str,
        to_location: str,
        category: str,
        confidence: float,
    ) -> None:
        """Publish a storm propagation WebSocket event."""
        ws_event = build_event_envelope(
            event_type="weather_event.propagation_detected",
            event_id=event_id,
            data={
                "event_id": event_id,
                "category": category,
                "confidence": confidence,
                "from_location": from_location,
                "to_location": to_location,
                "priority": "HIGH",
            },
        )
        await ws_manager.broadcast(ws_event)

    async def publish_system_event(
        self,
        event_id: str,
        message: str,
        level: str = "INFO",
    ) -> None:
        """Publish a system-level WebSocket event (ADMIN only, handled by RBAC filter)."""
        ws_event = build_event_envelope(
            event_type="system.notification",
            event_id=event_id,
            data={"message": message, "level": level},
        )
        await ws_manager.broadcast(ws_event)


realtime_gateway = RealtimeGateway()
