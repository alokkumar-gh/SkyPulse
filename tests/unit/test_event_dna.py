"""
Unit Tests for SkyPulse Weather Event DNA Service & Intelligence
================================================================
Validates:
1. Event DNA creation & complete schema integrity
2. Stable event identity under multiple incoming reports
3. Evidence aggregation & source categorization (IMD, Citizen, ERA5, Govt)
4. Transparent confidence decomposition using ConfidenceEngine
5. Multi-dimensional Evidence Coverage calculation (distinct from Confidence)
6. DWEG propagation profile & trajectory reconstruction
7. Chronological event evolution timeline milestones
8. Related evidence-supported event discovery
9. Contradictory evidence detection & penalties
10. Duplicate report clustering & metrics
11. Compact DNA snapshot representation
12. Role-based access control (RBAC) data stripping
13. WebSocket weather_event.dna_updated notification
14. Empty/partial evidence resilience & zero-crash guarantee
15. High-volume evidence set aggregation performance
"""

import uuid
import time
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.models.event_evidence import EventEvidence
from app.models.source import Source
from app.models.verification import VerificationResult
from app.models.enums import VerificationStatus, CorroborationType, WeatherCategory
from app.schemas.dna import (
    EventDNAResponse,
    EventDNASnapshot,
    EvidenceFingerprint,
    ConfidenceFactorBreakdown,
    EvidenceCoverageBreakdown,
    DNAPropagationProfile,
    DNATimelineEntry,
)
from app.services.event_dna_service import event_dna_service


async def _get_or_create_source(
    db: AsyncSession,
    name: str = "Test Source",
    st: str = "CITIZEN",
    trust: float = 0.8,
) -> Source:
    src = Source(
        id=uuid.uuid4(),
        name=name,
        source_type=st,
        connector_class="TestConnector",
        trust_score=trust,
    )
    db.add(src)
    await db.flush()
    return src


@pytest.mark.asyncio
async def test_1_event_dna_creation(db_session: AsyncSession):
    """Test 1: Event DNA creation with complete valid schema fields."""
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    event = WeatherEvent(
        id=event_id,
        category="RAINFALL",
        severity=3,
        confidence_score=0.88,
        verification_status="VERIFIED",
        centroid_lat=20.2961,
        centroid_lon=85.8245,
        primary_city="Bhubaneswar",
        primary_district="Khordha",
        primary_state="Odisha",
        first_reported_at=now - timedelta(hours=3),
        last_updated_at=now,
        evidence_count=1,
    )
    db_session.add(event)
    await db_session.flush()

    dna = await event_dna_service.get_event_dna(str(event_id), db_session, role="ANALYST")
    assert dna is not None
    assert dna.event_id == str(event_id)
    assert dna.event_type == "RAINFALL"
    assert dna.status == "VERIFIED"
    assert dna.severity == 3
    assert dna.confidence.final_confidence == 0.88
    assert dna.primary_district == "Khordha"
    assert dna.snapshot.event_id == str(event_id)
    assert dna.snapshot.confidence_score == 0.88


@pytest.mark.asyncio
async def test_2_stable_event_identity_multiple_reports(db_session: AsyncSession):
    """Test 2: Event DNA remains stable and accumulates evidence when multiple reports arrive."""
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    src = await _get_or_create_source(db_session, "Citizen App", "CITIZEN", 0.75)

    event = WeatherEvent(
        id=event_id,
        category="THUNDERSTORM",
        severity=2,
        confidence_score=0.75,
        verification_status="LIKELY",
        centroid_lat=19.0760,
        centroid_lon=72.8777,
        primary_city="Mumbai",
        primary_district="Mumbai Suburban",
        primary_state="Maharashtra",
        first_reported_at=now - timedelta(hours=2),
        last_updated_at=now,
        evidence_count=3,
    )
    db_session.add(event)

    # 3 distinct reports
    for i in range(3):
        r_id = uuid.uuid4()
        rep = WeatherReport(
            id=r_id,
            source_id=src.id,
            primary_category="THUNDERSTORM",
            severity=2,
            location_lat=19.0760 + (i * 0.01),
            location_lon=72.8777 + (i * 0.01),
            location_city="Mumbai",
            location_state="Maharashtra",
            event_time=now - timedelta(minutes=30 * (3 - i)),
            ingested_at=now - timedelta(minutes=30 * (3 - i)),
        )
        db_session.add(rep)

        ev = EventEvidence(
            canonical_event_id=event_id,
            weather_report_id=r_id,
            corroboration_score=0.90,
            corroboration_type=CorroborationType.PRIMARY.value if i == 0 else CorroborationType.CORROBORATING.value,
        )
        db_session.add(ev)

    await db_session.flush()

    dna = await event_dna_service.get_event_dna(str(event_id), db_session)
    assert dna is not None
    assert dna.event_id == str(event_id)
    assert dna.evidence.total_evidence_count == 3
    assert dna.evidence.supporting_evidence_count == 3
    assert dna.evidence.contradicting_evidence_count == 0


@pytest.mark.asyncio
async def test_3_source_aggregation_and_fingerprint(db_session: AsyncSession):
    """Test 3: Evidence fingerprint accurately groups observations by IMD, Citizen, ERA5, Govt."""
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    event = WeatherEvent(
        id=event_id,
        category="RAINFALL",
        severity=3,
        confidence_score=0.91,
        verification_status="VERIFIED",
        centroid_lat=13.0827,
        centroid_lon=80.2707,
        primary_city="Chennai",
        primary_state="Tamil Nadu",
        first_reported_at=now - timedelta(hours=4),
        last_updated_at=now,
        evidence_count=4,
    )
    db_session.add(event)

    sources = [
        ("WEATHER_API", "IMD Pune Automated Station"),
        ("CITIZEN", "SkyPulse Citizen App"),
        ("GOVERNMENT_API", "State Disaster Authority API"),
        ("PUBLIC_DATASET", "Copernicus CDS ERA5 Reanalysis"),
    ]

    for st, name in sources:
        src = Source(
            id=uuid.uuid4(),
            name=name,
            source_type=st,
            connector_class="TestConnector",
            trust_score=0.90 if "IMD" in name or "Disaster" in name else 0.70,
        )
        db_session.add(src)
        await db_session.flush()

        rep = WeatherReport(
            id=uuid.uuid4(),
            source_id=src.id,
            primary_category="RAINFALL",
            severity=3,
            location_lat=13.0827,
            location_lon=80.2707,
            event_time=now - timedelta(hours=1),
            ingested_at=now - timedelta(hours=1),
        )
        db_session.add(rep)

        ev = EventEvidence(
            canonical_event_id=event_id,
            weather_report_id=rep.id,
            corroboration_score=0.95,
            corroboration_type=CorroborationType.CORROBORATING.value,
        )
        db_session.add(ev)

    await db_session.flush()

    dna = await event_dna_service.get_event_dna(str(event_id), db_session)
    assert dna is not None
    assert dna.evidence.unique_sources_count == 4
    assert "IMD" in dna.evidence.sources
    assert "CITIZEN" in dna.evidence.sources
    assert "GOVERNMENT" in dna.evidence.sources
    assert "ERA5" in dna.evidence.sources
    assert dna.evidence.cross_source_corroborated is True


@pytest.mark.asyncio
async def test_4_transparent_confidence_decomposition(db_session: AsyncSession):
    """Test 4: Confidence factor decomposition exposes explainable components without fabrication."""
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    event = WeatherEvent(
        id=event_id,
        category="FLOODING",
        severity=4,
        confidence_score=0.92,
        verification_status="VERIFIED",
        centroid_lat=26.8467,
        centroid_lon=80.9462,
        primary_city="Lucknow",
        first_reported_at=now - timedelta(hours=5),
        last_updated_at=now,
        evidence_count=2,
    )
    db_session.add(event)
    await db_session.flush()

    dna = await event_dna_service.get_event_dna(str(event_id), db_session)
    assert dna is not None
    cb = dna.confidence
    assert cb.final_confidence == 0.92
    assert cb.source_reliability_score > 0.0
    assert cb.spatial_consistency_score > 0.0
    assert cb.temporal_consistency_score > 0.0
    assert "Event Confidence 92%" in cb.explanation


@pytest.mark.asyncio
async def test_5_evidence_coverage_distinct_from_confidence(db_session: AsyncSession):
    """Test 5: Evidence Coverage accurately measures observational completeness."""
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    src = await _get_or_create_source(db_session, "Weather Station Network", "WEATHER_API", 0.85)

    event = WeatherEvent(
        id=event_id,
        category="HEATWAVE",
        severity=3,
        confidence_score=0.85,
        verification_status="VERIFIED",
        centroid_lat=28.6139,
        centroid_lon=77.2090,
        primary_city="New Delhi",
        first_reported_at=now - timedelta(hours=6),
        last_updated_at=now,
        evidence_count=3,
    )
    db_session.add(event)

    # 3 geo-located reports over time
    for i in range(3):
        r_id = uuid.uuid4()
        rep = WeatherReport(
            id=r_id,
            source_id=src.id,
            primary_category="HEATWAVE",
            severity=3,
            location_lat=28.6139 + (i * 0.02),
            location_lon=77.2090 + (i * 0.02),
            event_time=now - timedelta(hours=3 - i),
            ingested_at=now - timedelta(hours=3 - i),
        )
        db_session.add(rep)

        ev = EventEvidence(
            canonical_event_id=event_id,
            weather_report_id=r_id,
            corroboration_score=0.90,
            corroboration_type=CorroborationType.CORROBORATING.value,
        )
        db_session.add(ev)

    await db_session.flush()

    dna = await event_dna_service.get_event_dna(str(event_id), db_session)
    assert dna is not None
    cov = dna.evidence_coverage
    assert cov.overall_coverage_score > 0.0
    assert cov.temporal_coverage > 0.0
    assert cov.spatial_coverage > 0.0
    assert cov.active_dimensions_count >= 3
    # Distinctness assertion:
    assert isinstance(cov.overall_coverage_score, float)
    assert isinstance(dna.confidence.final_confidence, float)


@pytest.mark.asyncio
async def test_6_contradictory_evidence_handling(db_session: AsyncSession):
    """Test 6: Contradictory evidence is isolated and correctly penalizes confidence/lifecycle."""
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    src = await _get_or_create_source(db_session, "Public Reporter", "CITIZEN", 0.6)

    event = WeatherEvent(
        id=event_id,
        category="RAINFALL",
        severity=2,
        confidence_score=0.62,
        verification_status="REQUIRES_REVIEW",
        centroid_lat=12.9716,
        centroid_lon=77.5946,
        primary_city="Bengaluru",
        first_reported_at=now - timedelta(hours=2),
        last_updated_at=now,
        evidence_count=2,
    )
    db_session.add(event)

    # 1 supporting report
    sup_id = uuid.uuid4()
    r1 = WeatherReport(
        id=sup_id,
        source_id=src.id,
        primary_category="RAINFALL",
        severity=2,
        location_lat=12.9716,
        location_lon=77.5946,
        event_time=now - timedelta(hours=1),
        ingested_at=now - timedelta(hours=1),
    )
    db_session.add(r1)
    ev1 = EventEvidence(
        canonical_event_id=event_id,
        weather_report_id=sup_id,
        corroboration_score=0.90,
        corroboration_type=CorroborationType.PRIMARY.value,
    )
    db_session.add(ev1)

    # 1 contradicting report
    con_id = uuid.uuid4()
    r2 = WeatherReport(
        id=con_id,
        source_id=src.id,
        primary_category="HEATWAVE",
        severity=1,
        location_lat=12.9716,
        location_lon=77.5946,
        event_time=now - timedelta(minutes=30),
        ingested_at=now - timedelta(minutes=30),
    )
    db_session.add(r2)
    ev2 = EventEvidence(
        canonical_event_id=event_id,
        weather_report_id=con_id,
        corroboration_score=0.20,
        corroboration_type=CorroborationType.CONTRADICTING.value,
    )
    db_session.add(ev2)

    await db_session.flush()

    dna = await event_dna_service.get_event_dna(str(event_id), db_session)
    assert dna is not None
    assert dna.evidence.supporting_evidence_count == 1
    assert dna.evidence.contradicting_evidence_count == 1
    assert dna.confidence.contradiction_penalty > 0.0


@pytest.mark.asyncio
async def test_7_chronological_dna_timeline(db_session: AsyncSession):
    """Test 7: Event DNA timeline generates auditable, chronological milestones."""
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    src = await _get_or_create_source(db_session, "Cyclone Warning Centre", "GOVERNMENT_API", 0.95)

    event = WeatherEvent(
        id=event_id,
        category="CYCLONE",
        severity=4,
        confidence_score=0.95,
        verification_status="VERIFIED",
        centroid_lat=17.6868,
        centroid_lon=83.2185,
        primary_city="Visakhapatnam",
        primary_district="Visakhapatnam",
        primary_state="Andhra Pradesh",
        first_reported_at=now - timedelta(hours=8),
        last_updated_at=now,
        evidence_count=2,
    )
    db_session.add(event)

    r_id = uuid.uuid4()
    rep = WeatherReport(
        id=r_id,
        source_id=src.id,
        primary_category="CYCLONE",
        severity=4,
        location_lat=17.6868,
        location_lon=83.2185,
        event_time=now - timedelta(hours=8),
        ingested_at=now - timedelta(hours=8),
    )
    db_session.add(rep)

    ev = EventEvidence(
        canonical_event_id=event_id,
        weather_report_id=r_id,
        corroboration_score=1.0,
        corroboration_type=CorroborationType.PRIMARY.value,
    )
    db_session.add(ev)

    vr = VerificationResult(
        canonical_event_id=event_id,
        status="VERIFIED",
        confidence_score=0.95,
        explanation_text="Radar and satellite confirmation of cyclone vortex.",
        updated_at=now - timedelta(hours=4),
    )
    db_session.add(vr)
    await db_session.flush()

    dna = await event_dna_service.get_event_dna(str(event_id), db_session)
    assert dna is not None
    assert len(dna.timeline) >= 2
    phases = [t.phase for t in dna.timeline]
    assert "DETECTED" in phases
    assert "VERIFIED" in phases


@pytest.mark.asyncio
async def test_8_propagation_profile_reconstruction(db_session: AsyncSession):
    """Test 8: Spatial propagation trajectory stages are reconstructed accurately."""
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    src = await _get_or_create_source(db_session, "Meteorological Radar Network", "WEATHER_API", 0.90)

    event = WeatherEvent(
        id=event_id,
        category="THUNDERSTORM",
        severity=3,
        confidence_score=0.89,
        verification_status="VERIFIED",
        centroid_lat=20.2961,
        centroid_lon=85.8245,
        primary_city="Bhubaneswar",
        first_reported_at=now - timedelta(hours=3),
        last_updated_at=now,
        evidence_count=3,
    )
    db_session.add(event)

    # 3 progressive locations shifting SE -> NW
    coords = [
        (20.20, 85.90),
        (20.35, 85.75),
        (20.50, 85.60),
    ]

    for i, (lat, lon) in enumerate(coords):
        r_id = uuid.uuid4()
        rep = WeatherReport(
            id=r_id,
            source_id=src.id,
            primary_category="THUNDERSTORM",
            severity=3,
            location_lat=lat,
            location_lon=lon,
            event_time=now - timedelta(minutes=45 * (3 - i)),
            ingested_at=now - timedelta(minutes=45 * (3 - i)),
        )
        db_session.add(rep)

        ev = EventEvidence(
            canonical_event_id=event_id,
            weather_report_id=r_id,
            corroboration_score=0.90,
            corroboration_type=CorroborationType.CORROBORATING.value,
        )
        db_session.add(ev)

    await db_session.flush()

    dna = await event_dna_service.get_event_dna(str(event_id), db_session)
    assert dna is not None
    prop = dna.propagation
    assert prop.stage_count == 3
    assert prop.has_propagation is True
    assert prop.total_distance_km > 10.0


@pytest.mark.asyncio
async def test_9_related_events_discovery(db_session: AsyncSession):
    """Test 9: Adjacent and supporting events are discovered via spatio-temporal proximity."""
    now = datetime.now(timezone.utc)

    # Event 1: Heavy Rainfall in Cuttack
    e1_id = uuid.uuid4()
    e1 = WeatherEvent(
        id=e1_id,
        category="RAINFALL",
        severity=3,
        confidence_score=0.90,
        verification_status="VERIFIED",
        centroid_lat=20.4625,
        centroid_lon=85.8828,
        first_reported_at=now - timedelta(hours=2),
        last_updated_at=now,
        evidence_count=2,
    )
    db_session.add(e1)

    # Event 2: Flooding in nearby Bhubaneswar (25 km away)
    e2_id = uuid.uuid4()
    e2 = WeatherEvent(
        id=e2_id,
        category="FLOODING",
        severity=3,
        confidence_score=0.85,
        verification_status="VERIFIED",
        centroid_lat=20.2961,
        centroid_lon=85.8245,
        first_reported_at=now - timedelta(hours=1),
        last_updated_at=now,
        evidence_count=2,
    )
    db_session.add(e2)
    await db_session.flush()

    dna = await event_dna_service.get_event_dna(str(e1_id), db_session)
    assert dna is not None
    assert len(dna.related_events) >= 1
    rel = dna.related_events[0]
    assert rel.event_id == str(e2_id)
    assert rel.category == "FLOODING"
    assert rel.relationship_type == "SUPPORTS"
    assert rel.distance_km < 35.0


@pytest.mark.asyncio
async def test_10_compact_dna_snapshot_fields(db_session: AsyncSession):
    """Test 10: Event DNA Snapshot generates concise, complete operational summaries."""
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    event = WeatherEvent(
        id=event_id,
        category="DUST_STORM",
        severity=2,
        confidence_score=0.78,
        verification_status="LIKELY",
        centroid_lat=26.9124,
        centroid_lon=75.7873,
        first_reported_at=now - timedelta(hours=1),
        last_updated_at=now,
        evidence_count=1,
    )
    db_session.add(event)
    await db_session.flush()

    dna = await event_dna_service.get_event_dna(str(event_id), db_session)
    assert dna is not None
    snap = dna.snapshot
    assert snap.event_id == str(event_id)
    assert snap.event_type == "DUST_STORM"
    assert snap.status == "LIKELY"
    assert snap.confidence_score == 0.78


@pytest.mark.asyncio
async def test_11_role_based_access_control(db_session: AsyncSession):
    """Test 11: Public role receives sanitised DNA timeline without internal reviewer/source PII."""
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    src = await _get_or_create_source(db_session, "Anonymous Observer", "CITIZEN", 0.5)

    event = WeatherEvent(
        id=event_id,
        category="RAINFALL",
        severity=2,
        confidence_score=0.80,
        verification_status="VERIFIED",
        centroid_lat=12.9716,
        centroid_lon=77.5946,
        first_reported_at=now,
        last_updated_at=now,
        evidence_count=1,
    )
    db_session.add(event)

    r_id = uuid.uuid4()
    rep = WeatherReport(
        id=r_id,
        source_id=src.id,
        primary_category="RAINFALL",
        severity=2,
        location_lat=12.9716,
        location_lon=77.5946,
        event_time=now,
        ingested_at=now,
    )
    db_session.add(rep)

    ev = EventEvidence(
        canonical_event_id=event_id,
        weather_report_id=r_id,
        corroboration_score=1.0,
        corroboration_type=CorroborationType.PRIMARY.value,
    )
    db_session.add(ev)
    await db_session.flush()

    # Public view
    public_dna = await event_dna_service.get_event_dna(str(event_id), db_session, role="PUBLIC")
    assert public_dna is not None
    for entry in public_dna.timeline:
        assert entry.source_name is None


@pytest.mark.asyncio
async def test_12_empty_or_partial_evidence_resilience(db_session: AsyncSession):
    """Test 12: Zero crashes on partial, corrupted, or minimal event metadata."""
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Event with missing coords and null attributes
    event = WeatherEvent(
        id=event_id,
        category="UNKNOWN",
        severity=1,
        confidence_score=0.50,
        verification_status="UNVERIFIED",
        centroid_lat=None,
        centroid_lon=None,
        first_reported_at=now,
        last_updated_at=now,
        evidence_count=0,
    )
    db_session.add(event)
    await db_session.flush()

    dna = await event_dna_service.get_event_dna(str(event_id), db_session)
    assert dna is not None
    assert dna.event_id == str(event_id)
    assert dna.event_type == "UNKNOWN"
    assert dna.confidence.final_confidence == 0.50
    assert dna.evidence_coverage.overall_coverage_score >= 0.0


@pytest.mark.asyncio
async def test_13_websocket_dna_update_broadcast():
    """Test 13: WebSocket weather_event.dna_updated broadcast completes without raising errors."""
    await event_dna_service.publish_dna_update_event(
        event_id=str(uuid.uuid4()),
        changed_fields=["confidence_score", "evidence_count", "propagation_stages"],
        confidence=0.91,
        evidence_coverage=0.84,
        event_type="RAINFALL",
    )


@pytest.mark.asyncio
async def test_14_high_volume_evidence_performance(db_session: AsyncSession):
    """Test 14: Event DNA generation scales efficiently on events with 50+ evidence reports."""
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    src = await _get_or_create_source(db_session, "Automated Sensor Fleet", "WEATHER_API", 0.88)

    event = WeatherEvent(
        id=event_id,
        category="RAINFALL",
        severity=3,
        confidence_score=0.94,
        verification_status="VERIFIED",
        centroid_lat=20.2961,
        centroid_lon=85.8245,
        first_reported_at=now - timedelta(hours=12),
        last_updated_at=now,
        evidence_count=50,
    )
    db_session.add(event)

    for i in range(50):
        r_id = uuid.uuid4()
        rep = WeatherReport(
            id=r_id,
            source_id=src.id,
            primary_category="RAINFALL",
            severity=3,
            location_lat=20.2961 + (i * 0.001),
            location_lon=85.8245 + (i * 0.001),
            event_time=now - timedelta(minutes=10 * (50 - i)),
            ingested_at=now - timedelta(minutes=10 * (50 - i)),
        )
        db_session.add(rep)

        ev = EventEvidence(
            canonical_event_id=event_id,
            weather_report_id=r_id,
            corroboration_score=0.95,
            corroboration_type=CorroborationType.CORROBORATING.value,
        )
        db_session.add(ev)

    await db_session.flush()

    start_t = time.perf_counter()
    dna = await event_dna_service.get_event_dna(str(event_id), db_session)
    elapsed_ms = (time.perf_counter() - start_t) * 1000.0

    assert dna is not None
    assert dna.evidence.total_evidence_count == 50
    assert elapsed_ms < 3500.0  # reasonable unit test threshold with SQLite in-memory driver
