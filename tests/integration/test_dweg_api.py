"""
SkyPulse Phase 10 Integration Tests — DWEG Endpoints & Worker
==============================================================
Tests all DWEG endpoints and background worker processing end-to-end:
1. GET /api/v1/dweg/{event_id}/graph & /api/v1/dweg/events/{event_id}/graph
2. GET /api/v1/dweg/{event_id}/confidence-field & /api/v1/dweg/events/{event_id}/confidence-field
3. GET /api/v1/dweg/{event_id}/propagation-timeline & /api/v1/dweg/{event_id}/propagation
4. GET /api/v1/dweg/{event_id}/evidence-chain & /api/v1/dweg/{event_id}/chain
5. GET /api/v1/dweg/propagation-alerts & /api/v1/dweg/alerts
6. DWEGWorker event message processing and alert dispatch
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.models.event_evidence import EventEvidence
from app.models.source import Source
from app.models.enums import WeatherCategory, EventSeverity, VerificationStatus
from workers.dweg_worker import DWEGWorker


@pytest.mark.asyncio
async def test_dweg_graph_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test /api/v1/dweg/{event_id}/graph and /events/{event_id}/graph."""
    now = datetime.now(timezone.utc)
    event = WeatherEvent(
        id=uuid.uuid4(),
        category=WeatherCategory.RAINFALL.value,
        severity=EventSeverity.MODERATE.value,
        confidence_score=0.86,
        verification_status=VerificationStatus.VERIFIED.value,
        centroid_lat=12.9716,
        centroid_lon=77.5946,
        primary_state="Karnataka",
        primary_district="Bengaluru Urban",
        primary_city="Bengaluru",
        first_reported_at=now,
        last_updated_at=now,
        evidence_count=2,
        is_active=True,
    )
    db_session.add(event)
    await db_session.commit()

    # 1. Standard path
    resp1 = await client.get(f"/api/v1/dweg/{event.id}/graph")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["event_id"] == str(event.id)
    assert len(data1["nodes"]) >= 2  # Event + Location
    assert len(data1["edges"]) >= 1

    # 2. Events prefix path
    resp2 = await client.get(f"/api/v1/dweg/events/{event.id}/graph")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["event_id"] == str(event.id)

    # 3. 404 for nonexistent UUID
    random_id = str(uuid.uuid4())
    resp_404 = await client.get(f"/api/v1/dweg/{random_id}/graph")
    assert resp_404.status_code == 404

    # 4. 400 for invalid UUID string
    resp_400 = await client.get("/api/v1/dweg/not-a-valid-uuid/graph")
    assert resp_400.status_code == 400


@pytest.mark.asyncio
async def test_dweg_confidence_field_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test /api/v1/dweg/{event_id}/confidence-field returns GeoJSON FeatureCollection."""
    now = datetime.now(timezone.utc)
    event = WeatherEvent(
        id=uuid.uuid4(),
        category=WeatherCategory.FLOODING.value,
        severity=EventSeverity.SEVERE.value,
        confidence_score=0.89,
        verification_status=VerificationStatus.VERIFIED.value,
        centroid_lat=13.0827,
        centroid_lon=80.2707,
        primary_state="Tamil Nadu",
        primary_district="Chennai",
        first_reported_at=now,
        last_updated_at=now,
        evidence_count=1,
        is_active=True,
    )
    db_session.add(event)
    await db_session.commit()

    resp = await client.get(f"/api/v1/dweg/{event.id}/confidence-field")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert len(data["features"]) >= 1  # Centroid point feature
    centroid_f = data["features"][0]
    assert centroid_f["geometry"]["type"] == "Point"
    assert centroid_f["properties"]["is_centroid"] is True


@pytest.mark.asyncio
async def test_dweg_propagation_timeline_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test /api/v1/dweg/{event_id}/propagation-timeline and /propagation."""
    now = datetime.now(timezone.utc)
    event = WeatherEvent(
        id=uuid.uuid4(),
        category=WeatherCategory.THUNDERSTORM.value,
        severity=EventSeverity.SEVERE.value,
        confidence_score=0.91,
        verification_status=VerificationStatus.VERIFIED.value,
        centroid_lat=17.3850,
        centroid_lon=78.4867,
        primary_state="Telangana",
        primary_district="Hyderabad",
        first_reported_at=now,
        last_updated_at=now,
        evidence_count=3,
        is_active=True,
    )
    db_session.add(event)
    await db_session.commit()

    resp1 = await client.get(f"/api/v1/dweg/{event.id}/propagation-timeline")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["event_id"] == str(event.id)
    assert len(data1["propagation_steps"]) >= 1

    # Alias /propagation
    resp2 = await client.get(f"/api/v1/dweg/{event.id}/propagation")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2["propagation_steps"]) == len(data1["propagation_steps"])


@pytest.mark.asyncio
async def test_dweg_evidence_chain_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test /api/v1/dweg/{event_id}/evidence-chain and /chain."""
    now = datetime.now(timezone.utc)
    event = WeatherEvent(
        id=uuid.uuid4(),
        category=WeatherCategory.CYCLONE.value,
        severity=EventSeverity.CATASTROPHIC.value,
        confidence_score=0.95,
        verification_status=VerificationStatus.VERIFIED.value,
        centroid_lat=20.2961,
        centroid_lon=85.8245,
        primary_state="Odisha",
        primary_district="Khordha",
        first_reported_at=now,
        last_updated_at=now,
        evidence_count=4,
        is_active=True,
    )
    db_session.add(event)
    await db_session.commit()

    resp = await client.get(f"/api/v1/dweg/{event.id}/evidence-chain")
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_id"] == str(event.id)
    assert "CYCLONE" in data["narrative"]
    assert len(data["evidence_chain"]) >= 1

    # Alias /chain
    resp_alias = await client.get(f"/api/v1/dweg/{event.id}/chain")
    assert resp_alias.status_code == 200


@pytest.mark.asyncio
async def test_dweg_propagation_alerts_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test /api/v1/dweg/propagation-alerts and /alerts."""
    now = datetime.now(timezone.utc)
    # Severe active event
    event = WeatherEvent(
        id=uuid.uuid4(),
        category=WeatherCategory.FLOODING.value,
        severity=EventSeverity.CATASTROPHIC.value,
        confidence_score=0.90,
        verification_status=VerificationStatus.VERIFIED.value,
        centroid_lat=9.9312,
        centroid_lon=76.2673,
        primary_state="Kerala",
        primary_district="Ernakulam",
        first_reported_at=now,
        last_updated_at=now,
        evidence_count=6,
        is_active=True,
    )
    db_session.add(event)
    await db_session.commit()

    resp = await client.get("/api/v1/dweg/propagation-alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data

    resp_alias = await client.get("/api/v1/dweg/alerts")
    assert resp_alias.status_code == 200


@pytest.mark.asyncio
async def test_dweg_worker_processing(
    db_session: AsyncSession,
):
    """Test DWEGWorker processes event message, builds graph, and runs propagation detection."""
    now = datetime.now(timezone.utc)
    event = WeatherEvent(
        id=uuid.uuid4(),
        category=WeatherCategory.THUNDERSTORM.value,
        severity=EventSeverity.SEVERE.value,
        confidence_score=0.85,
        verification_status=VerificationStatus.VERIFIED.value,
        centroid_lat=18.5204,
        centroid_lon=73.8567,
        primary_state="Maharashtra",
        primary_district="Pune",
        first_reported_at=now,
        last_updated_at=now,
        evidence_count=2,
        is_active=True,
    )
    db_session.add(event)
    await db_session.commit()

    worker = DWEGWorker()
    msg = {
        "canonical_event_id": str(event.id),
        "category": "THUNDERSTORM",
        "severity": 3,
    }

    result = await worker.process_event_message(msg, db=db_session)
    assert result["status"] == "PROCESSED"
    assert result["event_id"] == str(event.id)
    assert result["node_count"] >= 2
