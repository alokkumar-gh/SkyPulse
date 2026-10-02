"""
SkyPulse DWEG Worker — Phase 10
================================
Consumes event messages from Kafka / Redpanda (topic: skypulse.events & skypulse.ai_processed),
rebuilds/updates the Dynamic Weather Evidence Graph in Neo4j, detects spatio-temporal
propagation trajectories across district boundaries, and fires propagation alerts via
the Notification Service and WebSocket Manager.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.session import async_session_factory
from app.services.dweg_service import dweg_service
from app.models.notification import Notification
from app.models.enums import NotificationType
from app.core.websocket_manager import ws_manager, build_event_envelope
from connectors.kafka_bus import (
    KafkaBusConsumer,
    TOPIC_EVENTS,
    TOPIC_AI_PROCESSED,
    TOPIC_PROPAGATION,
    kafka_producer,
)

logger = logging.getLogger("skypulse.dweg_worker")


class DWEGWorker:
    """
    Background worker for asynchronous graph synchronization and propagation alert dispatch.
    """

    def __init__(self):
        self._consumer: Optional[KafkaBusConsumer] = None
        self._is_running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the DWEG worker consumer."""
        if self._is_running:
            return
        self._is_running = True
        logger.info("Starting DWEG Worker...")
        await dweg_service.initialize()

        self._consumer = KafkaBusConsumer(
            topics=[TOPIC_EVENTS, TOPIC_AI_PROCESSED],
            group_id="skypulse-dweg-group",
        )
        await self._consumer.start()
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("DWEG Worker started listening on %s and %s", TOPIC_EVENTS, TOPIC_AI_PROCESSED)

    async def stop(self) -> None:
        """Gracefully stop the DWEG worker."""
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._consumer:
            await self._consumer.stop()
        await dweg_service.close()
        logger.info("DWEG Worker stopped.")

    async def _consume_loop(self) -> None:
        """Continuous consumer loop."""
        while self._is_running:
            try:
                if self._consumer:
                    msg = await self._consumer.get_message(timeout=1.0)
                    if msg:
                        await self.process_event_message(msg)
                await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in DWEG worker consume loop: %s", exc, exc_info=True)
                await asyncio.sleep(1.0)

    async def process_event_message(
        self,
        message: Dict[str, Any],
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Processes an event or report message:
        1. Identifies event_id
        2. Rebuilds DWEG subgraph
        3. Analyzes spatial propagation
        4. Dispatches alert if propagation is detected
        """
        event_id = message.get("canonical_event_id") or message.get("event_id")
        if not event_id:
            logger.debug("DWEG worker skipped message without event_id: %s", message)
            return {"status": "SKIPPED", "reason": "NO_EVENT_ID"}

        if db is not None:
            return await self._process_with_session(str(event_id), db)

        async with async_session_factory() as session:
            return await self._process_with_session(str(event_id), session)

    async def _process_with_session(self, event_id: str, db: AsyncSession) -> Dict[str, Any]:
        try:
            # 1. Update/build event graph
            graph_res = await dweg_service.build_event_graph(str(event_id), db)

            # 2. Run propagation detection
            prop_res = await dweg_service.detect_propagation(str(event_id), db)

            alert_dispatched = False
            alert_data = None

            if prop_res.is_propagation:
                logger.info(
                    "DWEG detected propagation for event %s from %s (%s, %.1f km)",
                    event_id,
                    prop_res.parent_event_id,
                    prop_res.direction_name,
                    prop_res.distance_km,
                )

                alert_id = str(uuid.uuid4())
                now_iso = datetime.now(timezone.utc).isoformat()
                alert_payload = {
                    "alert_id": alert_id,
                    "event_id": str(event_id),
                    "parent_event_id": prop_res.parent_event_id,
                    "direction": prop_res.direction_name,
                    "bearing_deg": prop_res.direction_deg,
                    "distance_km": prop_res.distance_km,
                    "time_delta_minutes": prop_res.time_delta_minutes,
                    "confidence": prop_res.confidence,
                    "detected_at": now_iso,
                }

                # A. Publish to Kafka propagation topic
                try:
                    await kafka_producer.send(
                        TOPIC_PROPAGATION,
                        key=str(event_id),
                        value=alert_payload,
                    )
                except Exception as k_err:
                    logger.debug("Failed publishing propagation to Kafka (fallback): %s", k_err)

                # B. Broadcast real-time WebSocket event
                ws_envelope = build_event_envelope(
                    event_type="DWEG_PROPAGATION_ALERT",
                    event_id=str(event_id),
                    data=alert_payload,
                )
                await ws_manager.broadcast_event(ws_envelope)

                # Secondary envelope for generic listeners
                alt_envelope = build_event_envelope(
                    event_type="weather_event.propagation_detected",
                    event_id=str(event_id),
                    data=alert_payload,
                )
                await ws_manager.broadcast_event(alt_envelope)

                alert_dispatched = True
                alert_data = alert_payload

            return {
                "status": "PROCESSED",
                "event_id": str(event_id),
                "node_count": len(graph_res.nodes),
                "edge_count": len(graph_res.edges),
                "is_propagation": prop_res.is_propagation,
                "alert_dispatched": alert_dispatched,
                "alert": alert_data,
            }

        except Exception as exc:
            logger.error("Error processing event in DWEG worker for event %s: %s", event_id, exc, exc_info=True)
            return {"status": "ERROR", "event_id": str(event_id), "error": str(exc)}


# Global worker instance
dweg_worker = DWEGWorker()
