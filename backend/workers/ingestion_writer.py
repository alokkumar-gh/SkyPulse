import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from geoalchemy2.elements import WKTElement

from app.models.weather_report import WeatherReport
from app.models.source import Source
from app.models.enums import ReportStatus
from connectors.schema import CanonicalRawEvent
from connectors.normalizer import normalize_raw_event
from connectors.kafka_bus import (
    KafkaBusConsumer,
    kafka_producer,
    TOPIC_RAW,
    TOPIC_PENDING_AI,
    TOPIC_FAILED,
)

logger = logging.getLogger("skypulse.workers.ingestion_writer")


async def persist_normalized_event(
    db: AsyncSession,
    raw_payload: Dict[str, Any],
) -> Optional[WeatherReport]:
    """
    Core normalization and database persistence handler.
    Called by the Kafka consumer or directly during batch processing.
    """
    raw_event = CanonicalRawEvent(**raw_payload)
    norm = await normalize_raw_event(raw_event)

    # Convert source_id string to UUID
    try:
        s_uuid = uuid.UUID(norm.source_id)
    except ValueError:
        # Fallback to or create default demo/external source
        s_res = await db.execute(select(Source).where(Source.is_demo == norm.is_demo))
        default_src = s_res.scalars().first()
        if not default_src:
            default_src = Source(
                name="External Stream" if not norm.is_demo else "Demo Stream",
                source_type="DEMO" if norm.is_demo else "WEATHER_API",
                connector_class="DemoConnector" if norm.is_demo else "ExternalConnector",
                trust_score=0.5,
                is_active=True,
                is_demo=norm.is_demo,
            )
            db.add(default_src)
            await db.flush()
        s_uuid = default_src.id

    point_geom = None
    if norm.latitude is not None and norm.longitude is not None:
        point_geom = WKTElement(f"POINT({norm.longitude} {norm.latitude})", srid=4326)

    # Build WeatherReport entity
    report = WeatherReport(
        id=uuid.UUID(norm.ingestion_id),
        ingested_at=norm.ingested_at,
        source_id=s_uuid,
        raw_content=norm.text,
        normalized_text=norm.text,
        primary_category=norm.primary_category,
        severity=norm.severity,
        classification_confidence=0.5 if norm.primary_category == "UNKNOWN" else 0.8,
        classification_method="CONNECTOR_RULE",
        location_point=point_geom,
        location_lat=norm.latitude,
        location_lon=norm.longitude,
        location_city=norm.city,
        location_district=norm.district,
        location_state=norm.state,
        location_confidence=norm.location_confidence,
        event_time=norm.observed_at,
        is_duplicate=norm.is_duplicate,
        status=ReportStatus.PENDING.value,
        is_demo=norm.is_demo,
        metadata_={
            "tracking_id": norm.tracking_id,
            "idempotency_key": norm.idempotency_key,
            "external_id": norm.external_id,
            "raw_payload": norm.metadata.get("raw_payload", {}),
        },
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    # Publish notification to downstream AI topic
    ai_event = {
        "report_id": str(report.id),
        "ingested_at": report.ingested_at.isoformat(),
        "tracking_id": norm.tracking_id,
        "category": report.primary_category,
        "is_duplicate": report.is_duplicate,
    }
    await kafka_producer.publish(TOPIC_PENDING_AI, ai_event, key=str(report.id))

    return report


class IngestionWriterWorker:
    """
    Subscribes to skypulse.raw and writes records to PostgreSQL.
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.consumer = KafkaBusConsumer(
            topic=TOPIC_RAW,
            group_id="skypulse-ingestion-writers",
            dead_letter_topic=TOPIC_FAILED,
        )

    async def start(self) -> None:
        await self.consumer.start()
        logger.info("IngestionWriterWorker started on topic '%s'", TOPIC_RAW)

    async def stop(self) -> None:
        await self.consumer.stop()
        logger.info("IngestionWriterWorker stopped")

    async def process_one(self, timeout_seconds: float = 1.0) -> bool:
        async def handler(payload: Dict[str, Any]):
            async with self.session_factory() as session:
                await persist_normalized_event(session, payload)

        return await self.consumer.consume_one(handler, timeout_seconds=timeout_seconds)
