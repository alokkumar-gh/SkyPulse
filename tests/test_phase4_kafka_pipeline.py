"""
SkyPulse Phase 4 Pipeline & Integration Tests
Tests KafkaBusProducer, KafkaBusConsumer, Retry, Dead-letter handling,
IngestionWriterWorker persistence into WeatherReport, and Citizen API streaming.
"""

import pytest
import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from connectors.schema import (
    CanonicalRawEvent,
    NormalizedEvent,
    MediaItem,
    ConnectorStatusEnum,
)
from connectors.normalizer import normalize_raw_event
from connectors.kafka_bus import (
    KafkaBusProducer,
    KafkaBusConsumer,
    TOPIC_RAW,
    TOPIC_NORMALIZED,
    TOPIC_PENDING_AI,
    TOPIC_FAILED,
    TOPIC_DEAD_LETTER,
)
from workers.ingestion_writer import persist_normalized_event, IngestionWriterWorker
from app.models.weather_report import WeatherReport
from app.models.enums import WeatherCategory, ReportStatus, SourceType
from app.models.user import User


@pytest.mark.asyncio
async def test_kafka_bus_producer_publish_and_fallback():
    """Verify that KafkaBusProducer publishes canonical events to topics safely with in-memory fallback."""
    producer = KafkaBusProducer()
    await producer.start()

    raw_event = CanonicalRawEvent(
        source_id="test_sensor_01",
        source_type="WEATHER_API",
        external_id="ext-abc-123",
        text="Heavy precipitation recorded in Colaba.",
        latitude=18.9067,
        longitude=72.8147,
        city="Mumbai",
        state="Maharashtra",
        is_demo=True,
    )

    published = await producer.publish(TOPIC_RAW, raw_event, key="test_sensor_01")
    assert published is True

    # If falling back to in-memory queue, verify item was enqueued
    if not producer.is_live:
        q = producer.get_fallback_queue(TOPIC_RAW)
        assert q.qsize() >= 1

    await producer.stop()


@pytest.mark.asyncio
async def test_kafka_bus_consumer_and_dead_letter_routing():
    """Verify that KafkaBusConsumer receives messages, retries on error, and routes to DEAD_LETTER on failure."""
    producer = KafkaBusProducer()
    await producer.start()

    consumer = KafkaBusConsumer(
        topic=TOPIC_RAW,
        group_id="test_worker_group",
        producer=producer,
        max_retries=2,
    )
    await consumer.start()

    error_count = 0

    async def failing_handler(msg: dict):
        nonlocal error_count
        error_count += 1
        raise ValueError("Simulated catastrophic processing error in ingestion worker")

    # Send a payload that will fail
    test_event = CanonicalRawEvent(
        source_id="bad_source_99",
        source_type="RSS_FEED",
        external_id="bad-feed-item",
        text="Malformed XML alert causing worker crash",
        latitude=28.6139,
        longitude=77.2090,
    )

    # Publish
    await producer.publish(TOPIC_RAW, test_event, key=test_event.source_id)

    # Process message with consumer.consume_one - retries and routes to DLQ
    consumed = await consumer.consume_one(failing_handler, timeout_seconds=1.0)
    assert consumed is True
    assert error_count == 2  # Max retries reached

    # Verify routed to dead-letter queue
    if not producer.is_live:
        dl_queue = producer.get_fallback_queue(TOPIC_DEAD_LETTER)
        assert dl_queue.qsize() >= 1
        _, dl_item = await dl_queue.get()
        assert dl_item["failed_topic"] == TOPIC_RAW
        assert "Simulated catastrophic" in dl_item["error"]

    await consumer.stop()
    await producer.stop()


@pytest.mark.asyncio
async def test_persist_normalized_event_to_db(db_session: AsyncSession):
    """Verify that normalized events are correctly persisted to the WeatherReport table with status PENDING."""
    producer = KafkaBusProducer()
    await producer.start()

    raw_event = CanonicalRawEvent(
        source_id="imd_bulletin_radar",
        source_type="GOVERNMENT_API",
        external_id="imd_cyclone_alert_44",
        text="Severe squally winds exceeding 65 kmph expected over coastal Odisha.",
        suggested_category="STRONG_WINDS",
        latitude=20.2961,
        longitude=85.8245,
        city="Bhubaneswar",
        district="Khordha",
        state="Odisha",
        observed_at=datetime.now(timezone.utc),
        is_demo=True,
    )

    # Persist to database
    report = await persist_normalized_event(
        db=db_session,
        raw_payload=raw_event.model_dump(),
    )

    assert report is not None
    assert report.metadata_["tracking_id"].startswith("SP-")
    assert report.primary_category == "STRONG_WINDS"
    assert report.status == ReportStatus.PENDING.value
    assert report.location_city == "Bhubaneswar"
    assert report.location_state == "Odisha"
    assert report.location_lat == 20.2961
    assert report.location_lon == 85.8245

    # Verify queryable from DB
    result = await db_session.execute(
        select(WeatherReport).where(WeatherReport.id == report.id)
    )
    found_report = result.scalar_one_or_none()
    assert found_report is not None
    assert found_report.location_city == "Bhubaneswar"

    await producer.stop()


@pytest.mark.asyncio
async def test_citizen_report_stream_to_kafka_raw(client, test_citizen: User, auth_headers):
    """Verify that submitting a report via POST /api/v1/reports pushes a raw event into the ingestion pipeline."""
    from connectors.kafka_bus import kafka_producer

    q_before = 0
    if not kafka_producer.is_live and TOPIC_RAW in kafka_producer.fallback_queues:
        q_before = kafka_producer.fallback_queues[TOPIC_RAW].qsize()

    payload = {
        "event_type": "RAINFALL",
        "severity": 2,
        "description": "Heavy waterlogging near Hindmata flyover after intense cloudburst.",
        "latitude": 19.0067,
        "longitude": 72.8427,
        "location_name": "Hindmata, Mumbai, Maharashtra",
    }

    headers = auth_headers(test_citizen)
    response = await client.post("/api/v1/reports", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["tracking_id"].startswith("SP-")
    assert data["status"] == "PENDING"

    # Verify that an event landed in TOPIC_RAW
    if not kafka_producer.is_live and TOPIC_RAW in kafka_producer.fallback_queues:
        q_after = kafka_producer.fallback_queues[TOPIC_RAW].qsize()
        assert q_after > q_before


@pytest.mark.asyncio
async def test_end_to_end_demo_connector_to_persistence(db_session: AsyncSession):
    """
    End-to-end integration test:
    DemoConnector -> Raw Ingestion -> Normalization -> Persistence (WeatherReport)
    """
    from connectors.demo_connector import DemoConnector

    demo_conn = DemoConnector(
        name="e2e_demo_stream",
        scenario="storm_cluster",
        rate_seconds=3,
    )
    await demo_conn.start()

    raw_events = await demo_conn.poll()
    assert len(raw_events) >= 1

    producer = KafkaBusProducer()
    await producer.start()

    persisted_reports = []
    for raw_event in raw_events[:2]:
        assert raw_event.is_demo is True
        report = await persist_normalized_event(
            db=db_session,
            raw_payload=raw_event.model_dump(),
        )
        persisted_reports.append(report)

    assert len(persisted_reports) >= 1
    for r in persisted_reports:
        assert r.id is not None
        assert r.metadata_["tracking_id"].startswith("SP-")
        assert r.is_demo is True
        assert r.primary_category in [c.value for c in WeatherCategory]

    await demo_conn.stop()
    await producer.stop()
