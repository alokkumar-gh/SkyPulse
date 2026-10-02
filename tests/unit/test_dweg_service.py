"""
SkyPulse Phase 10 Unit Tests — DWEG Service
============================================
Tests DWEG graph service algorithms:
1. Spatio-temporal propagation detection with known spatial graph
2. Confidence field GeoJSON generation
3. Ordered propagation timeline generation
4. Explainable evidence chain narrative generation
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.dweg_service import (
    DWEGService,
    haversine_distance_km,
    calculate_bearing_deg,
    bearing_to_cardinal,
)
from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.models.event_evidence import EventEvidence
from app.models.source import Source
from app.models.enums import WeatherCategory, EventSeverity, VerificationStatus


def test_spatial_math_helpers():
    """Verify haversine distance and bearing calculations."""
    # Distance between Pune (18.5204, 73.8567) and Mumbai (19.0760, 72.8777) ~ 120km
    dist = haversine_distance_km(18.5204, 73.8567, 19.0760, 72.8777)
    assert 110.0 <= dist <= 130.0

    # Heading from Pune to Mumbai is North-West (~300°)
    bearing = calculate_bearing_deg(18.5204, 73.8567, 19.0760, 72.8777)
    assert 280.0 <= bearing <= 330.0
    assert "WEST" in bearing_to_cardinal(bearing) or "NORTH" in bearing_to_cardinal(bearing)


@pytest.mark.asyncio
async def test_dweg_service_propagation_detection(db_session: AsyncSession):
    """
    Test propagation detection with known events:
    Event A at T0 in Pune (18.52, 73.85)
    Event B at T0 + 2h in Mumbai (19.07, 72.87) with same category (THUNDERSTORM)
    """
    service = DWEGService()
    now = datetime.now(timezone.utc)

    # 1. Parent storm cell in Pune 2 hours ago
    parent_event = WeatherEvent(
        id=uuid.uuid4(),
        category=WeatherCategory.THUNDERSTORM.value,
        severity=EventSeverity.SEVERE.value,
        confidence_score=0.88,
        verification_status=VerificationStatus.VERIFIED.value,
        centroid_lat=18.5204,
        centroid_lon=73.8567,
        primary_state="Maharashtra",
        primary_district="Pune",
        first_reported_at=now - timedelta(hours=2),
        last_updated_at=now - timedelta(hours=2),
        evidence_count=4,
        is_active=True,
    )

    # 2. Propagated storm cell in Mumbai now (~120km distance, 2 hours later)
    target_event = WeatherEvent(
        id=uuid.uuid4(),
        category=WeatherCategory.THUNDERSTORM.value,
        severity=EventSeverity.SEVERE.value,
        confidence_score=0.82,
        verification_status=VerificationStatus.UNVERIFIED.value,
        centroid_lat=19.0760,
        centroid_lon=72.8777,
        primary_state="Maharashtra",
        primary_district="Mumbai",
        first_reported_at=now,
        last_updated_at=now,
        evidence_count=2,
        is_active=True,
    )

    # 3. Distant event in Delhi (should NOT be detected as propagation, > 1000km)
    distant_event = WeatherEvent(
        id=uuid.uuid4(),
        category=WeatherCategory.THUNDERSTORM.value,
        severity=EventSeverity.SEVERE.value,
        confidence_score=0.90,
        verification_status=VerificationStatus.VERIFIED.value,
        centroid_lat=28.6139,
        centroid_lon=77.2090,
        primary_state="Delhi",
        primary_district="New Delhi",
        first_reported_at=now - timedelta(hours=1),
        last_updated_at=now - timedelta(hours=1),
        evidence_count=3,
        is_active=True,
    )

    # 4. Different category event in Lonavala (FLOODING vs THUNDERSTORM)
    diff_cat_event = WeatherEvent(
        id=uuid.uuid4(),
        category=WeatherCategory.HEATWAVE.value,
        severity=EventSeverity.SEVERE.value,
        confidence_score=0.75,
        verification_status=VerificationStatus.VERIFIED.value,
        centroid_lat=18.7557,
        centroid_lon=73.4091,
        primary_state="Maharashtra",
        primary_district="Pune",
        first_reported_at=now - timedelta(hours=1),
        last_updated_at=now - timedelta(hours=1),
        evidence_count=1,
        is_active=True,
    )

    db_session.add_all([parent_event, target_event, distant_event, diff_cat_event])
    await db_session.commit()

    # Detect propagation for target event (Mumbai)
    prop_res = await service.detect_propagation(str(target_event.id), db_session)

    assert prop_res.is_propagation is True
    assert prop_res.parent_event_id == str(parent_event.id)
    assert prop_res.target_event_id == str(target_event.id)
    assert 110.0 <= prop_res.distance_km <= 130.0
    assert prop_res.time_delta_minutes >= 110
    assert prop_res.confidence >= 0.50
    assert prop_res.direction_name is not None


@pytest.mark.asyncio
async def test_confidence_field_geojson_generation(db_session: AsyncSession):
    """Verify confidence field GeoJSON with centroid and evidence weights."""
    service = DWEGService()
    now = datetime.now(timezone.utc)

    # 1. Event
    event = WeatherEvent(
        id=uuid.uuid4(),
        category=WeatherCategory.FLOODING.value,
        severity=EventSeverity.CATASTROPHIC.value,
        confidence_score=0.85,
        verification_status=VerificationStatus.VERIFIED.value,
        centroid_lat=11.605,
        centroid_lon=76.083,
        primary_state="Kerala",
        primary_district="Wayanad",
        first_reported_at=now - timedelta(hours=3),
        last_updated_at=now,
        evidence_count=2,
        is_active=True,
    )
    db_session.add(event)
    await db_session.flush()

    # 2. Sources & Reports
    source_cit = Source(
        id=uuid.uuid4(),
        name="Citizen Network",
        source_type="CITIZEN",
        connector_class="manual",
        trust_score=0.80,
        is_active=True,
    )
    source_gov = Source(
        id=uuid.uuid4(),
        name="CWC Central Water Commission",
        source_type="GOVERNMENT_API",
        connector_class="api",
        trust_score=0.95,
        is_active=True,
    )
    db_session.add_all([source_cit, source_gov])
    await db_session.flush()

    report1 = WeatherReport(
        id=uuid.uuid4(),
        source_id=source_cit.id,
        primary_category=WeatherCategory.FLOODING.value,
        raw_content="Kabini river overflowing at Panamaram",
        normalized_text="Kabini river overflowing at Panamaram",
        classification_confidence=0.80,
        location_lat=11.741,
        location_lon=76.071,
        event_time=now - timedelta(hours=2),
    )
    report2 = WeatherReport(
        id=uuid.uuid4(),
        source_id=source_gov.id,
        primary_category=WeatherCategory.FLOODING.value,
        raw_content="CWC Gauge Level Warning",
        normalized_text="CWC Gauge Level Warning",
        classification_confidence=0.95,
        location_lat=11.605,
        location_lon=76.083,
        event_time=now - timedelta(hours=1),
    )
    db_session.add_all([report1, report2])
    await db_session.flush()

    # 3. Evidence links
    ev1 = EventEvidence(
        canonical_event_id=event.id,
        weather_report_id=report1.id,
        corroboration_score=0.90,
        corroboration_type="PRIMARY",
    )
    ev2 = EventEvidence(
        canonical_event_id=event.id,
        weather_report_id=report2.id,
        corroboration_score=1.0,
        corroboration_type="CORROBORATING",
    )
    db_session.add_all([ev1, ev2])
    await db_session.commit()

    field = await service.compute_confidence_field(str(event.id), db_session)

    assert field["type"] == "FeatureCollection"
    assert len(field["features"]) == 3  # 1 centroid + 2 reports

    # Check centroid
    centroid_f = next(f for f in field["features"] if f["properties"]["is_centroid"])
    assert centroid_f["properties"]["weight"] == 1.0

    # Check weighted reports
    report_features = [f for f in field["features"] if not f["properties"]["is_centroid"]]
    assert len(report_features) == 2
    for rf in report_features:
        assert 0.0 < rf["properties"]["weight"] <= 1.0
        assert rf["geometry"]["type"] == "Point"


@pytest.mark.asyncio
async def test_evidence_chain_and_propagation_timeline(db_session: AsyncSession):
    """Test propagation timeline and explainable narrative chain for an active event."""
    service = DWEGService()
    now = datetime.now(timezone.utc)

    event = WeatherEvent(
        id=uuid.uuid4(),
        category=WeatherCategory.CYCLONE.value,
        severity=EventSeverity.CATASTROPHIC.value,
        confidence_score=0.94,
        verification_status=VerificationStatus.VERIFIED.value,
        centroid_lat=19.81,
        centroid_lon=85.82,
        primary_state="Odisha",
        primary_district="Puri",
        first_reported_at=now - timedelta(hours=4),
        last_updated_at=now,
        evidence_count=5,
        is_active=True,
    )
    db_session.add(event)
    await db_session.commit()

    # 1. Timeline
    timeline_res = await service.get_propagation_timeline(str(event.id), db_session)
    assert timeline_res.event_id == str(event.id)
    assert len(timeline_res.propagation_steps) >= 1
    assert timeline_res.propagation_steps[0].location["district"] == "Puri"

    # 2. Evidence Chain Narrative
    chain_res = await service.generate_evidence_chain(str(event.id), db_session)
    assert chain_res.event_id == str(event.id)
    assert chain_res.confidence == 0.94
    assert "CYCLONE" in chain_res.narrative
    assert len(chain_res.evidence_chain) >= 1
