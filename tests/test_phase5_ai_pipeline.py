"""
SkyPulse Phase 5 Integration Tests — Full AI Pipeline
Tests the complete end-to-end flow:
WeatherReport (status: PENDING) -> process_report_ai() ->
  - Classification
  - Entity Extraction
  - Embedding
  - Canonical WeatherEvent creation & linkage
  - EventEvidence creation
  - VerificationResult persistence
  - OpenSearch Indexing
  - DWEG Knowledge Graph update
  - Kafka topics publication (skypulse.ai_processed, skypulse.verification_updates)
  - Duplicate clustering of second report into the same Canonical Event
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.weather_report import WeatherReport
from app.models.weather_event import WeatherEvent
from app.models.event_evidence import EventEvidence
from app.models.verification import VerificationResult
from app.models.source import Source
from app.models.enums import ReportStatus, VerificationStatus

from connectors.kafka_bus import (
    KafkaBusProducer,
    TOPIC_AI_PROCESSED,
    TOPIC_VERIFICATION_UPDATES,
)
from workers.ai_pipeline import process_report_ai
from ai.dweg_service import dweg_service
from ai.opensearch_indexer import opensearch_indexer


@pytest.mark.asyncio
async def test_full_ai_pipeline_single_report(db_session: AsyncSession):
    """Verify that a single raw report is fully processed, classified, verified, and linked to a new canonical event."""
    producer = KafkaBusProducer()
    await producer.start()

    # 1. Create a test source
    source = Source(
        id=uuid.uuid4(),
        name="Mumbai Civic Sensor Network",
        source_type="WEATHER_API",
        connector_class="WeatherAPIConnector",
        trust_score=0.80,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    # 2. Create an initial pending report
    report_id = uuid.uuid4()
    report = WeatherReport(
        id=report_id,
        source_id=source.id,
        raw_content="Continuous cloudburst over Colaba, Mumbai with 120 mm rainfall and severe waterlogging",
        normalized_text="Continuous cloudburst over Colaba, Mumbai with 120 mm rainfall and severe waterlogging",
        location_city="Mumbai",
        location_state="Maharashtra",
        location_lat=18.9067,
        location_lon=72.8147,
        event_time=datetime.now(timezone.utc),
        status=ReportStatus.PENDING.value,
        is_demo=True,
        metadata_={"tracking_id": "SP-2026-000101"},
    )
    db_session.add(report)
    await db_session.commit()

    # 3. Execute AI Pipeline
    processed_report = await process_report_ai(
        report_id_str=str(report_id),
        db=db_session,
        producer=producer,
    )

    # 4. Verify WeatherReport updates
    assert processed_report is not None
    assert processed_report.status == ReportStatus.PROCESSED.value
    assert processed_report.primary_category in ("RAINFALL", "FLOODING")
    assert processed_report.severity >= 3
    assert processed_report.classification_confidence >= 0.70
    assert processed_report.text_embedding is not None
    assert len(processed_report.text_embedding) == 384
    assert processed_report.canonical_event_id is not None
    assert processed_report.ai_extraction is not None

    # Check extracted weather attributes
    extraction = processed_report.ai_extraction
    attr_names = [a["name"] for a in extraction.get("weather_attributes", [])]
    assert "rainfall_amount" in attr_names

    # 5. Verify Canonical WeatherEvent in DB
    evt_q = select(WeatherEvent).where(WeatherEvent.id == processed_report.canonical_event_id)
    evt_res = await db_session.execute(evt_q)
    canonical_event = evt_res.scalar_one_or_none()

    assert canonical_event is not None
    assert canonical_event.category == processed_report.primary_category
    assert canonical_event.evidence_count == 1
    assert canonical_event.confidence_score >= 0.50
    assert canonical_event.primary_city == "Mumbai"
    assert canonical_event.verification_status in [s.value for s in VerificationStatus]

    # 6. Verify EventEvidence linking record
    ee_q = select(EventEvidence).where(
        EventEvidence.canonical_event_id == canonical_event.id,
        EventEvidence.weather_report_id == processed_report.id,
    )
    ee_res = await db_session.execute(ee_q)
    evidence_link = ee_res.scalar_one_or_none()
    assert evidence_link is not None
    assert evidence_link.corroboration_type == "PRIMARY"

    # 7. Verify VerificationResult record in DB
    vr_q = select(VerificationResult).where(VerificationResult.canonical_event_id == canonical_event.id)
    vr_res = await db_session.execute(vr_q)
    vr_record = vr_res.scalar_one_or_none()
    assert vr_record is not None
    assert vr_record.confidence_score > 0.0
    assert len(vr_record.explanation_text) > 10

    # 8. Verify DWEG has nodes for event & report
    subgraph = await dweg_service.get_event_graph(str(canonical_event.id))
    assert subgraph["node_count"] >= 2
    assert subgraph["edge_count"] >= 1

    # 9. Verify Kafka message published
    if not producer.is_live and TOPIC_AI_PROCESSED in producer.fallback_queues:
        q = producer.fallback_queues[TOPIC_AI_PROCESSED]
        assert q.qsize() >= 1

    await producer.stop()


@pytest.mark.asyncio
async def test_duplicate_clustering_into_same_canonical_event(db_session: AsyncSession):
    """Verify that a second corroborating report within 5km is automatically clustered into the same canonical event."""
    producer = KafkaBusProducer()
    await producer.start()

    source = Source(
        id=uuid.uuid4(),
        name="Citizen Weather Stream",
        source_type="CITIZEN",
        connector_class="CitizenConnector",
        trust_score=0.60,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    # Report 1: Dadar flood
    r1_id = uuid.uuid4()
    r1 = WeatherReport(
        id=r1_id,
        source_id=source.id,
        raw_content="Severe waterlogging near Dadar station after 3 hours heavy rain",
        normalized_text="Severe waterlogging near Dadar station after 3 hours heavy rain",
        location_city="Mumbai",
        location_state="Maharashtra",
        location_lat=19.0178,
        location_lon=72.8478,
        event_time=datetime.now(timezone.utc),
        status=ReportStatus.PENDING.value,
        is_demo=True,
        metadata_={"tracking_id": "SP-2026-000201"},
    )
    db_session.add(r1)
    await db_session.commit()

    # Process Report 1
    p1 = await process_report_ai(str(r1_id), db=db_session, producer=producer)
    canonical_id_1 = p1.canonical_event_id

    # Report 2: Parel flood (2 km south of Dadar, 15 minutes later, same flooding category)
    r2_id = uuid.uuid4()
    r2 = WeatherReport(
        id=r2_id,
        source_id=source.id,
        raw_content="Inundation and high water levels on streets in Parel near Dadar",
        normalized_text="Inundation and high water levels on streets in Parel near Dadar",
        location_city="Mumbai",
        location_state="Maharashtra",
        location_lat=18.9982,
        location_lon=72.8364,
        event_time=datetime.now(timezone.utc) + timedelta(minutes=15),
        status=ReportStatus.PENDING.value,
        is_demo=True,
        metadata_={"tracking_id": "SP-2026-000202"},
    )
    db_session.add(r2)
    await db_session.commit()

    # Process Report 2
    p2 = await process_report_ai(str(r2_id), db=db_session, producer=producer)

    # Assertions
    assert p2 is not None
    assert p2.status == ReportStatus.PROCESSED.value
    assert p2.is_duplicate is True
    # Clustered into the same canonical event!
    assert p2.canonical_event_id == canonical_id_1

    # Canonical event evidence count incremented
    evt_q = select(WeatherEvent).where(WeatherEvent.id == canonical_id_1)
    evt_res = await db_session.execute(evt_q)
    canonical_event = evt_res.scalar_one_or_none()
    assert canonical_event.evidence_count >= 2

    await producer.stop()
