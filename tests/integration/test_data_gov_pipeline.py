"""
Integration Tests for data.gov.in Government Dataset Pipeline
============================================================
Tests end-to-end integration of data.gov.in records through:
1. Normalization & ingestion
2. Source attribution & trust evaluation (GOVERNMENT_DATASET)
3. Multi-source verification corroboration (Citizen + IMD + data.gov.in)
4. DWEG evidence graph rendering with government dataset provenance
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
from app.models.enums import WeatherCategory, EventSeverity, VerificationStatus, SourceType, ReportStatus
from connectors.data_gov_connector import DataGovConnector, DataGovResourceConfig
from connectors.normalizer import normalize_raw_event
from ai.verification_engine import VerificationEngine
from ai.source_trust import SourceTrustEngine
from app.services.dweg_service import dweg_service


@pytest.mark.asyncio
async def test_datagov_event_to_dweg_evidence_graph(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Verifies that a published government dataset record from data.gov.in correctly
    populates as an evidence node with GOVERNMENT_DATASET attribution in DWEG.
    """
    now = datetime.now(timezone.utc)

    # 1. Create data.gov.in Source record
    datagov_source = Source(
        id=uuid.uuid4(),
        name="Open Government Data Platform (data.gov.in)",
        source_type=SourceType.GOVERNMENT_DATASET.value,
        connector_class="DataGovConnector",
        trust_score=0.85,
        is_demo=False,
    )
    db_session.add(datagov_source)
    await db_session.flush()

    # 2. Ingest Record via Connector
    res_config = DataGovResourceConfig(
        resource_id="ogd-rain-test-01",
        dataset_name="Daily District Precipitation Summary",
        agency_name="Ministry of Earth Sciences (data.gov.in)",
        category="RAINFALL",
    )
    connector = DataGovConnector(source_id=str(datagov_source.id), config={"resources": [res_config.model_dump()]})
    raw_record = {
        "id": "ogd_rec_cuttack_88",
        "state": "Odisha",
        "district": "Cuttack",
        "station": "Cuttack Sadar",
        "latitude": 20.462,
        "longitude": 85.882,
        "date": now.strftime("%Y-%m-%d %H:%M:%S IST"),
        "rainfall_mm": "95.5",
    }

    raw_event = connector.parse_dataset_record(raw_record, res_config)
    norm_event = await normalize_raw_event(raw_event)

    # 3. Save as WeatherReport in database
    report = WeatherReport(
        id=uuid.uuid4(),
        source_id=datagov_source.id,
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
        status=ReportStatus.PROCESSED.value,
        classification_confidence=0.90,
        is_demo=False,
    )
    db_session.add(report)
    await db_session.flush()

    # 4. Create WeatherEvent and link via EventEvidence
    event = WeatherEvent(
        id=uuid.uuid4(),
        category=WeatherCategory.RAINFALL.value,
        severity=EventSeverity.SEVERE.value,
        confidence_score=0.92,
        verification_status=VerificationStatus.VERIFIED.value,
        centroid_lat=20.462,
        centroid_lon=85.882,
        primary_district="Cuttack",
        primary_state="Odisha",
        first_reported_at=now - timedelta(hours=1),
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
        corroboration_score=0.88,
    )
    db_session.add(evidence)
    await db_session.commit()

    # 5. Query DWEG Graph
    resp = await client.get(f"/api/v1/dweg/{event.id}/graph")
    assert resp.status_code == 200
    graph_data = resp.json()

    # Assertions on DWEG structure
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    report_nodes = [n for n in nodes if n["id"] == f"report_{report.id}"]
    assert len(report_nodes) == 1
    assert report_nodes[0]["type"] == "EvidenceReport"
    assert report_nodes[0]["properties"]["source_type"] == SourceType.GOVERNMENT_DATASET.value
    assert report_nodes[0]["properties"]["category"] == WeatherCategory.RAINFALL.value

    # Check corroboration edge
    corrob_edges = [
        e for e in edges
        if e["source"] == f"report_{report.id}" and e["target"] == f"event_{event.id}"
    ]
    assert len(corrob_edges) == 1
    assert corrob_edges[0]["type"] == "CORROBORATES"


@pytest.mark.asyncio
async def test_multi_source_verification_with_datagov(db_session: AsyncSession):
    """
    Verifies that multi-source independent evidence:
    1. Citizen field report
    2. IMD Government API bulletin
    3. data.gov.in Published rainfall dataset
    jointly corroborate an event into VERIFIED status with high confidence.
    """
    # 1. Citizen Report
    citizen_report_data = {
        "text": "Intense torrential rainfall in Bhubaneswar causing severe street waterlogging",
        "primary_category": "RAINFALL",
        "district": "Khordha",
        "state": "Odisha",
        "severity": 3,
    }

    # 2. Official IMD Data
    imd_official_data = {
        "agency": "India Meteorological Department (IMD)",
        "warning_type": "Heavy Rainfall Warning",
        "primary_category": "RAINFALL",
        "category": "RAINFALL",
        "district": "Khordha",
        "state": "Odisha",
        "rainfall_24h_mm": 88.0,
    }

    # 3. Published data.gov.in Dataset Observation
    datagov_record = {
        "text": "Official OGD Station precipitation telemetry 94.2 mm",
        "dataset_name": "Daily Precipitation Statistics",
        "agency_name": "Ministry of Earth Sciences / data.gov.in",
        "primary_category": "RAINFALL",
        "category": "RAINFALL",
        "rainfall_mm": 94.2,
        "district": "Khordha",
        "state": "Odisha",
        "distance_km": 1.5,
    }

    # Initial trust for sources
    citizen_trust = SourceTrustEngine.calculate_initial_trust(SourceType.CITIZEN.value)
    datagov_trust = SourceTrustEngine.calculate_initial_trust(SourceType.GOVERNMENT_DATASET.value)
    assert datagov_trust == 0.85

    # Run verification assessment with nearby corroboration including government dataset
    nearby_reports = [
        {"text": "Nearby citizen waterlogging report", "category": "RAINFALL", "district": "Khordha", "severity": 3},
        datagov_record,
    ]

    engine = VerificationEngine()
    verdict = await engine.verify_report(
        report_data=citizen_report_data,
        official_data=imd_official_data,
        nearby_reports=nearby_reports,
        source_trust=citizen_trust,
    )

    # Multi-source corroboration yields elevated confidence and VERIFIED / LIKELY status
    assert verdict.evidence_count >= 3
    assert verdict.verification_confidence >= 0.65
    assert verdict.verification_status in (VerificationStatus.VERIFIED.value, VerificationStatus.LIKELY.value)
    assert len(verdict.explanation) > 0
