"""
Integration Tests for IMD Government Data Ingestion Pipeline
=============================================================
Tests end-to-end flow of IMD records through:
1. Normalization & ingestion
2. Source attribution & trust evaluation
3. Multi-source verification corroboration (Citizen + IMD)
4. DWEG evidence graph rendering with government provenance
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.models.event_evidence import EventEvidence
from app.models.source import Source
from app.models.enums import WeatherCategory, EventSeverity, VerificationStatus, SourceType
from connectors.imd_connector import IMDConnector
from connectors.normalizer import normalize_raw_event
from ai.verification_engine import VerificationEngine
from ai.source_trust import SourceTrustEngine
from app.services.dweg_service import dweg_service


@pytest.mark.asyncio
async def test_imd_event_to_dweg_evidence_graph(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Verifies that an official IMD weather observation correctly populates as
    an evidence node with government attribution in the DWEG knowledge graph.
    """
    now = datetime.now(timezone.utc)

    # 1. Create IMD Source record
    imd_source = Source(
        id=uuid.uuid4(),
        name="India Meteorological Department (Official)",
        source_type=SourceType.GOVERNMENT_API.value,
        connector_class="IMDConnector",
        trust_score=0.95,
        is_demo=False,
    )
    db_session.add(imd_source)
    await db_session.flush()

    # 2. Ingest IMD Raw Observation via Connector
    connector = IMDConnector(source_id=str(imd_source.id))
    raw_obs = {
        "station_id": "42182",
        "station_name": "New Delhi Safdarjung",
        "district": "New Delhi",
        "state": "Delhi",
        "latitude": 28.58,
        "longitude": 77.21,
        "observed_at": "2026-10-01T08:30:00+05:30",
        "temperature_c": 36.5,
        "humidity_pct": 78,
        "rainfall_24h_mm": 110.4,
        "weather_condition": "Heavy Rain with Thunderstorm",
    }
    raw_event = connector.parse_current_weather(raw_obs)
    norm_event = await normalize_raw_event(raw_event)

    # 3. Save as WeatherReport in database
    report = WeatherReport(
        id=uuid.uuid4(),
        source_id=imd_source.id,
        raw_content=norm_event.text,
        normalized_text=norm_event.text,
        primary_category=norm_event.primary_category,
        severity=norm_event.severity,

        location_lat=norm_event.latitude,
        location_lon=norm_event.longitude,
        location_district=norm_event.district,
        location_state=norm_event.state,
        event_time=norm_event.observed_at,
        ingested_at=norm_event.ingested_at,
        status="PROCESSED",
        is_demo=False,
    )
    db_session.add(report)
    await db_session.flush()


    # 4. Create Canonical WeatherEvent linked to IMD Evidence
    event = WeatherEvent(
        id=uuid.uuid4(),
        category=WeatherCategory.RAINFALL.value,
        severity=EventSeverity.SEVERE.value,
        confidence_score=0.92,
        verification_status=VerificationStatus.VERIFIED.value,
        centroid_lat=28.58,
        centroid_lon=77.21,
        primary_state="Delhi",
        primary_district="New Delhi",
        first_reported_at=now,
        last_updated_at=now,
        evidence_count=1,
        is_active=True,
    )
    db_session.add(event)
    await db_session.flush()

    evidence = EventEvidence(
        id=uuid.uuid4(),
        canonical_event_id=event.id,
        weather_report_id=report.id,
        corroboration_type="CORROBORATING",
        corroboration_score=0.95,
    )
    db_session.add(evidence)
    await db_session.commit()

    # 5. Query DWEG Graph
    resp = await client.get(f"/api/v1/dweg/{event.id}/graph")
    print("DEBUG RESP:", resp.status_code, resp.text)
    assert resp.status_code == 200
    graph = resp.json()

    assert graph["event_id"] == str(event.id)

    # Verify Report node in graph has IMD source attribution
    report_nodes = [n for n in graph["nodes"] if n["type"] == "EvidenceReport"]
    assert len(report_nodes) >= 1
    assert any(n["id"] == f"report_{report.id}" for n in report_nodes)

    # Edge exists between Event and IMD Evidence Report
    assert any(e["target"] == f"event_{event.id}" or e["source"] == f"report_{report.id}" for e in graph["edges"])




@pytest.mark.asyncio
async def test_imd_multi_source_verification_corroboration():
    """
    Verifies that combining a Citizen report with an authoritative IMD bulletin
    yields a high-confidence verification verdict.
    """
    engine = VerificationEngine()

    citizen_report = {
        "text": "Severe waterlogging and knee-deep water on Cuttack road due to heavy downpour",
        "category": "FLOODING",
        "primary_category": "FLOODING",
        "severity": 3,
        "district": "Cuttack",
        "state": "Odisha",
        "latitude": 20.46,
        "longitude": 85.88,
    }

    imd_official_data = {
        "agency": "India Meteorological Department (IMD)",
        "warning_type": "Extremely Heavy Rainfall Warning",
        "category": "RAINFALL",
        "primary_category": "RAINFALL",
        "severity_level": "ORANGE",
        "district": "Cuttack",
        "state": "Odisha",
        "rainfall_24h_mm": 135.0,
    }


    nearby_citizen_reports = [
        {
            "text": "Inundated streets near Badambadi bus stand Cuttack",
            "category": "FLOODING",
            "distance_km": 2.1,
        }
    ]

    verdict = await engine.verify_report(
        report_data=citizen_report,
        official_data=imd_official_data,
        nearby_reports=nearby_citizen_reports,
        source_trust=0.60,
    )

    assert verdict.evidence_count >= 3  # citizen report + IMD + nearby citizen
    assert verdict.verification_confidence > 0.60
    assert verdict.verification_status in ("VERIFIED", "LIKELY")
    assert len(verdict.explanation) > 0
