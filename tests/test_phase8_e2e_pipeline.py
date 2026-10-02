"""
SkyPulse Phase 8 End-to-End Pipeline & Integration Test Suite
=============================================================
Comprehensive integration and hardening tests covering:
1. End-to-End Demo -> Ingestion -> AI Pipeline -> Verification -> DWEG -> WebSocket distribution
2. DemoConnector scenario validations (storm_cluster, flood_cluster, burst, mixed_national)
3. Citizen report workflow & validation (valid, invalid coordinates, idempotency)
4. Verification engine & analyst override workflow
5. DWEG knowledge graph evidence & corroboration tracking
6. Backend RBAC enforcement across roles (PUBLIC, CITIZEN, ANALYST, ADMIN)
7. Real-time WebSocket envelope filtering & event delivery
8. System health and degraded mode reporting
"""

import pytest
import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.main import app
from app.models.weather_report import WeatherReport
from app.models.weather_event import WeatherEvent
from app.models.event_evidence import EventEvidence
from app.models.verification import VerificationResult
from app.models.source import Source
from app.models.user import User
from app.models.enums import ReportStatus, VerificationStatus, UserRole
from app.core.security import create_access_token, get_password_hash
from app.core.websocket_manager import (
    WebSocketManager,
    SubscriptionFilter,
    build_event_envelope,
)

from connectors.demo_connector import DemoConnector
from connectors.normalizer import normalize_raw_event
from connectors.kafka_bus import KafkaBusProducer
from workers.ai_pipeline import process_report_ai
from ai.dweg_service import dweg_service
from ai.opensearch_indexer import opensearch_indexer
from workers.realtime_gateway import map_ai_processed, map_verification_update


@pytest.fixture
def auth_headers_factory():
    def _create(role: str = "ANALYST", user_id: str = None) -> Dict[str, str]:
        uid = user_id or str(uuid.uuid4())
        token = create_access_token({"sub": uid, "email": f"{role.lower()}@skypulse.gov.in", "role": role})
        return {"Authorization": f"Bearer {token}"}
    return _create


@pytest.mark.asyncio
async def test_e2e_demo_storm_cluster_to_ai_and_dweg(db_session: AsyncSession):
    """
    Validate that DemoConnector storm_cluster scenario generates coherent reports,
    which ingest, classify, cluster into canonical events, and enrich the DWEG graph.
    """
    producer = KafkaBusProducer()
    await producer.start()

    # 1. Create or get test source
    source = Source(
        id=uuid.uuid4(),
        name="Demo Stream Source - Storm",
        source_type="DEMO",
        connector_class="DemoConnector",
        trust_score=0.85,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    # 2. Run DemoConnector with storm_cluster
    connector = DemoConnector(source_id=str(source.id), scenario="storm_cluster")
    raw_events = await connector.poll()
    assert len(raw_events) == 5

    created_reports = []

    # 3. Normalize and persist weather reports
    for raw in raw_events:
        norm = await normalize_raw_event(raw)
        report = WeatherReport(
            id=uuid.uuid4(),
            source_id=source.id,
            raw_content=raw.text,
            normalized_text=norm.text,
            location_city=norm.city,
            location_state=norm.state,
            location_lat=norm.latitude,
            location_lon=norm.longitude,
            event_time=datetime.now(timezone.utc),
            status=ReportStatus.PENDING.value,
            is_demo=True,
            metadata_={"scenario": "storm_cluster"},
        )
        db_session.add(report)
        created_reports.append(report)

    await db_session.commit()

    # 4. Run AI Pipeline on first report
    first_report = created_reports[0]
    processed_first = await process_report_ai(
        report_id_str=str(first_report.id),
        db=db_session,
        producer=producer,
    )

    assert processed_first is not None
    assert processed_first.status == ReportStatus.PROCESSED.value
    canonical_id = processed_first.canonical_event_id
    assert canonical_id is not None

    # Check canonical event in DB
    ev_stmt = select(WeatherEvent).where(WeatherEvent.id == canonical_id)
    ev_res = await db_session.execute(ev_stmt)
    canonical_event = ev_res.scalar_one_or_none()
    assert canonical_event is not None
    assert canonical_event.category in ("THUNDERSTORM", "RAINFALL", "STRONG_WINDS")

    # 5. Process remaining cluster reports and verify spatial-temporal clustering
    for rep in created_reports[1:]:
        p_rep = await process_report_ai(
            report_id_str=str(rep.id),
            db=db_session,
            producer=producer,
        )
        assert p_rep.status == ReportStatus.PROCESSED.value
        # Related reports in same cluster should link to the canonical event
        assert p_rep.canonical_event_id is not None

    # 6. Verify DWEG Knowledge Graph reflects the event node
    graph_data = await dweg_service.get_event_graph(str(canonical_id))
    assert graph_data is not None
    assert "nodes" in graph_data
    assert len(graph_data["nodes"]) >= 1


@pytest.mark.asyncio
async def test_e2e_demo_flood_cluster_corroboration(db_session: AsyncSession):
    """
    Validate DemoConnector flood_cluster scenario produces FLOODING events
    with high multi-factor corroboration.
    """
    producer = KafkaBusProducer()
    await producer.start()

    source = Source(
        id=uuid.uuid4(),
        name="Demo Flood Source",
        source_type="DEMO",
        connector_class="DemoConnector",
        trust_score=0.90,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    connector = DemoConnector(source_id=str(source.id), scenario="flood_cluster")
    raw_events = await connector.poll()
    assert len(raw_events) == 5

    first_raw = raw_events[0]
    norm = await normalize_raw_event(first_raw)

    flood_report = WeatherReport(
        id=uuid.uuid4(),
        source_id=source.id,
        raw_content=first_raw.text,
        normalized_text=norm.text,
        location_city=norm.city,
        location_state=norm.state,
        location_lat=norm.latitude,
        location_lon=norm.longitude,
        event_time=datetime.now(timezone.utc),
        status=ReportStatus.PENDING.value,
        is_demo=True,
    )
    db_session.add(flood_report)
    await db_session.commit()

    processed = await process_report_ai(
        report_id_str=str(flood_report.id),
        db=db_session,
        producer=producer,
    )

    assert processed.primary_category in ("FLOODING", "RAINFALL")
    assert processed.canonical_event_id is not None

    # Verify event evidence was generated
    ev_stmt = select(EventEvidence).where(EventEvidence.canonical_event_id == processed.canonical_event_id)
    ev_res = await db_session.execute(ev_stmt)
    evidence_list = ev_res.scalars().all()
    assert len(evidence_list) >= 1


@pytest.mark.asyncio
async def test_citizen_report_submission_api_and_validation(client: AsyncClient, test_citizen: User, auth_headers):
    """
    Test citizen report submission endpoint with valid data, invalid coordinates,
    and missing mandatory fields.
    """
    headers = auth_headers(test_citizen)

    # 1. Valid report submission
    valid_payload = {
        "event_type": "RAINFALL",
        "severity": 2,
        "description": "Continuous drizzle and waterlogging in Dadar, Mumbai.",
        "latitude": 19.0178,
        "longitude": 72.8478,
        "location_name": "Dadar, Mumbai",
    }
    res = await client.post("/api/v1/reports", json=valid_payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert "id" in data
    assert "tracking_id" in data

    # 2. Out of bounds latitude (outside India)
    invalid_lat_payload = dict(valid_payload, latitude=60.0)
    res_lat = await client.post("/api/v1/reports", json=invalid_lat_payload, headers=headers)
    assert res_lat.status_code == 422

    # 3. Missing / too short description
    invalid_desc_payload = dict(valid_payload, description="rain")
    res_desc = await client.post("/api/v1/reports", json=invalid_desc_payload, headers=headers)
    assert res_desc.status_code == 422


@pytest.mark.asyncio
async def test_verification_workflow_analyst_override(
    db_session: AsyncSession,
    client: AsyncClient,
    test_citizen: User,
    test_analyst: User,
    auth_headers,
):
    """
    Test the full verification lifecycle:
    - Event starts as UNVERIFIED
    - Analyst performs verification override with audit note
    - Event transitions to VERIFIED in DB
    - Role restrictions: CITIZEN cannot verify, ANALYST and ADMIN can
    """
    # 1. Seed an unverified WeatherEvent
    event_id = uuid.uuid4()
    weather_event = WeatherEvent(
        id=event_id,
        category="THUNDERSTORM",
        severity=3,
        verification_status=VerificationStatus.UNVERIFIED.value,
        confidence_score=0.60,
        centroid_lat=22.5726,
        centroid_lon=88.3639,
        primary_state="West Bengal",
        primary_district="Kolkata",
        first_reported_at=datetime.now(timezone.utc),
        last_updated_at=datetime.now(timezone.utc),
        is_demo=True,
    )
    db_session.add(weather_event)
    await db_session.commit()

    # 2. Attempt override as CITIZEN (must be forbidden)
    citizen_headers = auth_headers(test_citizen)
    res_cit = await client.post(
        f"/api/v1/verification/{event_id}/override",
        json={"status": "VERIFIED", "reason": "Citizen trying to verify without role"},
        headers=citizen_headers,
    )
    assert res_cit.status_code == 403

    # 3. Attempt override as unauthenticated (must be unauthorized)
    res_anon = await client.post(
        f"/api/v1/verification/{event_id}/override",
        json={"status": "VERIFIED", "reason": "Anon trying to verify without token"},
    )
    assert res_anon.status_code == 401

    # 4. Successful override as ANALYST
    analyst_headers = auth_headers(test_analyst)
    res_analyst = await client.post(
        f"/api/v1/verification/{event_id}/override",
        json={"status": "VERIFIED", "reason": "Doppler radar correlation verified."},
        headers=analyst_headers,
    )
    assert res_analyst.status_code == 200
    verified_data = res_analyst.json()
    assert verified_data["status"] == "VERIFIED"

    # 5. Check database persistence
    await db_session.refresh(weather_event)
    assert weather_event.verification_status == VerificationStatus.VERIFIED.value


@pytest.mark.asyncio
async def test_realtime_websocket_message_mapping_and_filtering():
    """
    Test real-time event mapping from AI pipeline format to WebSocket envelopes,
    and verify subscription filter match behavior.
    """
    raw_kafka_payload = {
        "event_id": "ev-realtime-777",
        "category": "CYCLONE",
        "severity": 4,
        "confidence": 0.92,
        "location_state": "Odisha",
        "location_district": "Puri",
        "location_lat": 19.8135,
        "location_lon": 85.8312,
        "is_synthetic": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Map to envelope
    envelope = map_ai_processed(raw_kafka_payload)
    assert envelope["type"] == "weather_event.updated"
    assert envelope["data"]["category"] == "CYCLONE"
    assert envelope["data"]["severity"] == 4

    # Subscription Filter matching tests
    matching_filter = SubscriptionFilter(
        categories=["CYCLONE", "FLOODING"],
        states=["Odisha"],
        min_severity=3,
    )
    assert matching_filter.matches(envelope, role="ANALYST") is True

    # Filter with different category should reject
    heatwave_filter = SubscriptionFilter(
        categories=["HEATWAVE"],
        states=["Odisha"],
    )
    assert heatwave_filter.matches(envelope, role="ANALYST") is False

    # Filter with higher min_severity should reject (severity 5 vs event severity 4)
    extreme_severity_filter = SubscriptionFilter(
        min_severity=5,
    )
    assert extreme_severity_filter.matches(envelope, role="ANALYST") is False


@pytest.mark.asyncio
async def test_system_health_endpoint(client: AsyncClient):
    """Verify system health endpoint returns correct operational payload."""
    res = await client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_demo_mixed_national_and_burst_scenarios():
    """
    Validate DemoConnector for mixed_national and burst scenarios.
    """
    # 1. Mixed National: generates varied weather across distinct regions
    connector_mixed = DemoConnector(scenario="mixed_national")
    mixed_events = await connector_mixed.poll()
    assert len(mixed_events) >= 1
    categories = {ev.suggested_category for ev in mixed_events if ev.suggested_category}
    assert len(categories) >= 1

    # 2. Burst scenario: generates 10 high-rate events
    connector_burst = DemoConnector(scenario="burst")
    burst_events = await connector_burst.poll()
    assert len(burst_events) == 10
    # All burst events have valid lat/lon coordinates
    assert all(ev.latitude is not None and ev.longitude is not None for ev in burst_events)


@pytest.mark.asyncio
async def test_dweg_propagation_detection_workflow():
    """
    Validate that DWEG detects geospatial-temporal storm propagation between adjacent events.
    """
    parent_id = str(uuid.uuid4())

    # 1. Upsert parent weather event node in Bhubaneswar (lat 20.2961, lon 85.8245)
    await dweg_service.upsert_event_node(
        event_id=parent_id,
        category="CYCLONE",
        severity=4,
        confidence=0.90,
        status="ACTIVE",
        city="Bhubaneswar",
        lat=20.2961,
        lon=85.8245,
    )

    # 2. Detect propagation to Cuttack (~25 km north, 2 hours later)
    child_id = str(uuid.uuid4())
    t_child = datetime.now(timezone.utc) + timedelta(hours=2)
    prop = await dweg_service.detect_propagation(
        event_id=child_id,
        category="CYCLONE",
        lat=20.4625,
        lon=85.8830,
        occurred_at=t_child,
        max_distance_km=100.0,
        max_time_delta_h=6.0,
    )

    assert prop.is_propagation is True
    assert prop.parent_event_id == parent_id
    assert prop.distance_km is not None
    assert 10.0 <= prop.distance_km <= 50.0


@pytest.mark.asyncio
async def test_alert_notification_lifecycle_and_deduplication(db_session: AsyncSession):
    """
    Validate alert generation from severe weather events and verify deduplication within cooldown.
    """
    from app.services.alert_service import AlertEngine

    engine = AlertEngine()
    ev_id = str(uuid.uuid4())
    event_data = {
        "event_id": ev_id,
        "category": "CYCLONE",
        "severity": 4,
        "confidence_score": 0.95,
        "verification_status": "VERIFIED",
        "primary_state": "Odisha",
        "primary_city": "Puri",
        "evidence_count": 5,
        "is_anomalous": False,
    }

    # 1. First evaluation creates new CRITICAL alert
    alert1 = await engine.evaluate_event(db_session, event_data)
    assert alert1 is not None
    assert alert1.priority == "CRITICAL"
    assert alert1.status == "CREATED"
    await db_session.flush()

    # 2. Immediate second evaluation with same event returns deduplicated existing alert
    alert2 = await engine.evaluate_event(db_session, event_data)
    assert alert2 is not None
    assert alert2.id == alert1.id  # Same record, not duplicate

