"""
Unit Tests for Weather Source Reputation Graph
==============================================
Validates:
1. New source (0 observations -> NEW)
2. Insufficient evidence (1-4 observations -> INSUFFICIENT_EVIDENCE)
3. Established source (≥5 observations -> ESTABLISHED)
4. Trusted state (high support, low contradiction -> TRUSTED)
5. Watch state (rising contradiction / high duplicates -> WATCH)
6. Low-reliability state (high contradiction ≥ 0.40 -> LOW_RELIABILITY)
7. Corroboration rate calculation
8. Contradiction rate calculation
9. Duplicate calculation (deduplicated reports do not inflate observations)
10. Category-specific reputation breakdown
11. Temporal consistency metric
12. Spatial consistency metric
13. Denominator-zero handling (returns None, not 0.0)
14. Historical timeline reconstruction
15. Reputation update and dynamic trust adjustment
16. State transition determinism
17. DWEG integration
18. Event DNA integration
19. WebSocket event broadcasting
20. RBAC and API endpoints
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Callable, Dict
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.source import Source, SourceReputationHistory
from app.models.weather_report import WeatherReport
from app.models.weather_event import WeatherEvent
from app.models.user import User
from app.models.enums import (
    SourceType,
    ReputationState,
    VerificationStatus,
    CorroborationType,
    WeatherCategory,
    UserRole,
)
from app.services.source_reputation_service import source_reputation_service
from app.core.websocket_manager import ws_manager


@pytest.mark.asyncio
async def test_1_new_source_state(db_session: AsyncSession):
    """1. New source with 0 observations has NEW state and None for rate metrics."""
    source = Source(
        id=uuid.uuid4(),
        name="New Meteorological Sensor #1",
        source_type=SourceType.WEATHER_API.value,
        connector_class="app.connectors.GenericConnector",
        trust_score=0.70,
        is_active=True,
    )
    db_session.add(source)
    await db_session.commit()

    profile = await source_reputation_service.build_source_reputation(source.id, db_session)
    assert profile is not None
    assert profile.reputation_state == ReputationState.NEW
    assert profile.observation_count == 0
    assert profile.corroboration_rate is None
    assert profile.contradiction_rate is None
    assert profile.verification_support_rate is None
    assert profile.duplicate_rate is None
    assert any("Newly registered" in e for e in profile.explanation)


@pytest.mark.asyncio
async def test_2_insufficient_evidence_state(db_session: AsyncSession):
    """2. Source with 1-4 observations has INSUFFICIENT_EVIDENCE state."""
    source = Source(
        id=uuid.uuid4(),
        name="Citizen Observer Alpha",
        source_type=SourceType.CITIZEN.value,
        connector_class="app.connectors.CitizenConnector",
        trust_score=0.55,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    for i in range(2):
        r = WeatherReport(
            id=uuid.uuid4(),
            source_id=source.id,
            primary_category=WeatherCategory.RAINFALL.value,
            location_lat=12.97,
            location_lon=77.59,
            status="PROCESSED",
            event_time=now - timedelta(minutes=i * 10),
            ingested_at=now - timedelta(minutes=i * 10),
            is_duplicate=False,
            metadata_={"corroboration_type": CorroborationType.PRIMARY.value},
        )
        db_session.add(r)
    await db_session.commit()

    profile = await source_reputation_service.build_source_reputation(source.id, db_session)
    assert profile is not None
    assert profile.reputation_state == ReputationState.INSUFFICIENT_EVIDENCE
    assert profile.observation_count == 2
    assert any("insufficient" in expl.lower() for expl in profile.explanation)


@pytest.mark.asyncio
async def test_3_established_source_state(db_session: AsyncSession):
    """3. Source with ≥5 consistent observations has ESTABLISHED state."""
    source = Source(
        id=uuid.uuid4(),
        name="Karnataka Weather Network",
        source_type=SourceType.PUBLIC_DATASET.value,
        connector_class="app.connectors.DatasetConnector",
        trust_score=0.65,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    for i in range(6):
        r = WeatherReport(
            id=uuid.uuid4(),
            source_id=source.id,
            primary_category=WeatherCategory.RAINFALL.value,
            location_lat=12.97 + (i * 0.01),
            location_lon=77.59 + (i * 0.01),
            status="PROCESSED",
            event_time=now - timedelta(minutes=i * 15),
            ingested_at=now - timedelta(minutes=i * 15),
            is_duplicate=False,
            metadata_={"corroboration_type": CorroborationType.PRIMARY.value},
        )
        db_session.add(r)
    await db_session.commit()

    profile = await source_reputation_service.build_source_reputation(source.id, db_session)
    assert profile is not None
    assert profile.reputation_state == ReputationState.ESTABLISHED
    assert profile.observation_count == 6
    assert profile.verification_support_rate == 1.0


@pytest.mark.asyncio
async def test_4_trusted_state(db_session: AsyncSession):
    """4. High-volume source with high support and zero/low contradiction reaches TRUSTED."""
    source = Source(
        id=uuid.uuid4(),
        name="IMD Doppler Radar Bengaluru",
        source_type=SourceType.GOVERNMENT_API.value,
        connector_class="app.connectors.IMDConnector",
        trust_score=0.90,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    for i in range(16):
        r = WeatherReport(
            id=uuid.uuid4(),
            source_id=source.id,
            primary_category=WeatherCategory.THUNDERSTORM.value,
            location_lat=13.0 + (i * 0.005),
            location_lon=77.6 + (i * 0.005),
            status="PROCESSED",
            event_time=now - timedelta(hours=i),
            ingested_at=now - timedelta(hours=i),
            is_duplicate=False,
            metadata_={"corroboration_type": CorroborationType.CORROBORATING.value},
        )
        db_session.add(r)
    await db_session.commit()

    profile = await source_reputation_service.build_source_reputation(source.id, db_session)
    assert profile is not None
    assert profile.reputation_state == ReputationState.TRUSTED
    assert profile.observation_count == 16
    assert profile.contradiction_rate == 0.0
    assert profile.is_official is True


@pytest.mark.asyncio
async def test_5_watch_state_on_elevated_contradictions(db_session: AsyncSession):
    """5. Source with elevated contradictions (≥20%) transitions to WATCH state."""
    source = Source(
        id=uuid.uuid4(),
        name="Social Media Stream Feed",
        source_type=SourceType.RSS_FEED.value,
        connector_class="app.connectors.RSSConnector",
        trust_score=0.50,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    # 7 reports: 2 flagged/contradicted (28.5%)
    for i in range(7):
        is_flagged = i < 2
        r = WeatherReport(
            id=uuid.uuid4(),
            source_id=source.id,
            primary_category=WeatherCategory.FLOODING.value,
            location_lat=19.07,
            location_lon=72.87,
            status="FLAGGED" if is_flagged else "PROCESSED",
            event_time=now - timedelta(minutes=i * 20),
            ingested_at=now - timedelta(minutes=i * 20),
            is_duplicate=False,
            metadata_={"corroboration_type": CorroborationType.CONTRADICTING.value if is_flagged else CorroborationType.PRIMARY.value},
        )
        db_session.add(r)
    await db_session.commit()

    profile = await source_reputation_service.build_source_reputation(source.id, db_session)
    assert profile is not None
    assert profile.reputation_state == ReputationState.WATCH
    assert profile.contradiction_rate is not None
    assert profile.contradiction_rate >= 0.20


@pytest.mark.asyncio
async def test_6_low_reliability_state(db_session: AsyncSession):
    """6. Source with severe contradiction rate (≥40%) across ≥8 reports gets LOW_RELIABILITY."""
    source = Source(
        id=uuid.uuid4(),
        name="Unverified Aggregator Bot",
        source_type=SourceType.RSS_FEED.value,
        connector_class="app.connectors.BotConnector",
        trust_score=0.35,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    # 10 reports: 5 flagged/contradicted (50%)
    for i in range(10):
        is_flagged = i < 5
        r = WeatherReport(
            id=uuid.uuid4(),
            source_id=source.id,
            primary_category=WeatherCategory.CYCLONE.value,
            location_lat=20.0,
            location_lon=85.0,
            status="FLAGGED" if is_flagged else "PROCESSED",
            event_time=now - timedelta(minutes=i * 10),
            ingested_at=now - timedelta(minutes=i * 10),
            is_duplicate=False,
            metadata_={"corroboration_type": CorroborationType.CONTRADICTING.value if is_flagged else CorroborationType.PRIMARY.value},
        )
        db_session.add(r)
    await db_session.commit()

    profile = await source_reputation_service.build_source_reputation(source.id, db_session)
    assert profile is not None
    assert profile.reputation_state == ReputationState.LOW_RELIABILITY
    assert profile.contradiction_rate == 0.50
    assert profile.observation_count == 10


@pytest.mark.asyncio
async def test_7_corroboration_calculation(db_session: AsyncSession):
    """7. Corroboration rate accurately computes corroborated observations / eligible observations."""
    source = Source(
        id=uuid.uuid4(),
        name="Community AWS Network",
        source_type=SourceType.CITIZEN.value,
        connector_class="app.connectors.CitizenConnector",
        trust_score=0.60,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    # 5 reports: 3 corroborated
    for i in range(5):
        is_corr = i < 3
        r = WeatherReport(
            id=uuid.uuid4(),
            source_id=source.id,
            primary_category=WeatherCategory.RAINFALL.value,
            location_lat=13.0,
            location_lon=77.5,
            status="PROCESSED",
            event_time=now - timedelta(minutes=i * 10),
            ingested_at=now - timedelta(minutes=i * 10),
            is_duplicate=False,
            metadata_={"corroboration_type": CorroborationType.CORROBORATING.value if is_corr else CorroborationType.PRIMARY.value},
        )
        db_session.add(r)
    await db_session.commit()

    profile = await source_reputation_service.build_source_reputation(source.id, db_session)
    assert profile is not None
    assert profile.corroboration_rate == 0.60


@pytest.mark.asyncio
async def test_8_contradiction_calculation(db_session: AsyncSession):
    """8. Contradiction rate strictly measures contradicted observations / eligible observations."""
    source = Source(
        id=uuid.uuid4(),
        name="Private Station Delta",
        source_type=SourceType.WEATHER_API.value,
        connector_class="app.connectors.StationConnector",
        trust_score=0.55,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    # 8 reports: 2 contradicted (25%)
    for i in range(8):
        is_contra = i < 2
        r = WeatherReport(
            id=uuid.uuid4(),
            source_id=source.id,
            primary_category=WeatherCategory.HEATWAVE.value,
            location_lat=28.61,
            location_lon=77.20,
            status="FLAGGED" if is_contra else "PROCESSED",
            event_time=now - timedelta(minutes=i * 15),
            ingested_at=now - timedelta(minutes=i * 15),
            is_duplicate=False,
            metadata_={"corroboration_type": CorroborationType.CONTRADICTING.value if is_contra else CorroborationType.PRIMARY.value},
        )
        db_session.add(r)
    await db_session.commit()

    profile = await source_reputation_service.build_source_reputation(source.id, db_session)
    assert profile is not None
    assert profile.contradiction_rate == 0.25


@pytest.mark.asyncio
async def test_9_duplicate_calculation_isolation(db_session: AsyncSession):
    """9. Duplicate reports are counted in duplicate_rate but NOT in observation_count."""
    source = Source(
        id=uuid.uuid4(),
        name="Social Echo Bot",
        source_type=SourceType.RSS_FEED.value,
        connector_class="app.connectors.RSSConnector",
        trust_score=0.50,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    # 5 unique reports + 5 duplicate echoes
    for i in range(5):
        r = WeatherReport(
            id=uuid.uuid4(),
            source_id=source.id,
            primary_category=WeatherCategory.RAINFALL.value,
            location_lat=12.9,
            location_lon=77.6,
            status="PROCESSED",
            event_time=now - timedelta(minutes=i * 10),
            ingested_at=now - timedelta(minutes=i * 10),
            is_duplicate=False,
            metadata_={"corroboration_type": CorroborationType.PRIMARY.value},
        )
        db_session.add(r)

    for i in range(5):
        r_dup = WeatherReport(
            id=uuid.uuid4(),
            source_id=source.id,
            primary_category=WeatherCategory.RAINFALL.value,
            location_lat=12.9,
            location_lon=77.6,
            status="PROCESSED",
            event_time=now - timedelta(minutes=i * 10),
            ingested_at=now - timedelta(minutes=i * 10),
            is_duplicate=True,
            metadata_={"corroboration_type": CorroborationType.PRIMARY.value},
        )
        db_session.add(r_dup)
    await db_session.commit()

    profile = await source_reputation_service.build_source_reputation(source.id, db_session)
    assert profile is not None
    assert profile.observation_count == 5
    assert profile.duplicate_count == 5
    assert profile.duplicate_rate == 0.50


@pytest.mark.asyncio
async def test_10_category_specific_reputation(db_session: AsyncSession):
    """10. Computes category-specific breakdown (strong in RAINFALL, limited in FOG, empty in DUST_STORM)."""
    source = Source(
        id=uuid.uuid4(),
        name="Regional AWS Hub",
        source_type=SourceType.WEATHER_API.value,
        connector_class="app.connectors.AWSConnector",
        trust_score=0.75,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    # 4 RAINFALL reports (verified)
    for i in range(4):
        r = WeatherReport(
            id=uuid.uuid4(),
            source_id=source.id,
            primary_category=WeatherCategory.RAINFALL.value,
            location_lat=12.9,
            location_lon=77.6,
            status="PROCESSED",
            event_time=now - timedelta(minutes=i * 10),
            ingested_at=now - timedelta(minutes=i * 10),
            is_duplicate=False,
            metadata_={"corroboration_type": CorroborationType.CORROBORATING.value},
        )
        db_session.add(r)

    # 1 FOG report
    r_fog = WeatherReport(
        id=uuid.uuid4(),
        source_id=source.id,
        primary_category=WeatherCategory.FOG.value,
        location_lat=12.9,
        location_lon=77.6,
        status="PROCESSED",
        event_time=now,
        ingested_at=now,
        is_duplicate=False,
        metadata_={"corroboration_type": CorroborationType.PRIMARY.value},
    )
    db_session.add(r_fog)
    await db_session.commit()

    profile = await source_reputation_service.build_source_reputation(source.id, db_session)
    assert profile is not None
    rain_detail = profile.category_breakdown.get("RAINFALL")
    assert rain_detail is not None
    assert rain_detail.observation_count == 4
    assert rain_detail.reliability_level == "STRONG_EVIDENCE"

    fog_detail = profile.category_breakdown.get("FOG")
    assert fog_detail is not None
    assert fog_detail.observation_count == 1
    assert fog_detail.reliability_level == "LIMITED_EVIDENCE"

    dust_detail = profile.category_breakdown.get("DUST_STORM")
    assert dust_detail is not None
    assert dust_detail.observation_count == 0
    assert dust_detail.reliability_level == "INSUFFICIENT_EVIDENCE"


@pytest.mark.asyncio
async def test_11_temporal_consistency_score(db_session: AsyncSession):
    """11. Temporal consistency measures fraction of observations with valid event_time."""
    source = Source(
        id=uuid.uuid4(),
        name="Sensor Station Epsilon",
        source_type=SourceType.WEATHER_API.value,
        connector_class="app.connectors.SensorConnector",
        trust_score=0.70,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    for i in range(5):
        r = WeatherReport(
            id=uuid.uuid4(),
            source_id=source.id,
            primary_category=WeatherCategory.RAINFALL.value,
            location_lat=13.0,
            location_lon=77.5,
            status="PROCESSED",
            event_time=now - timedelta(minutes=i * 10) if i < 4 else None,
            ingested_at=now,
            is_duplicate=False,
            metadata_={"corroboration_type": CorroborationType.PRIMARY.value},
        )
        db_session.add(r)
    await db_session.commit()

    profile = await source_reputation_service.build_source_reputation(source.id, db_session)
    assert profile is not None
    assert profile.temporal_accuracy == 0.80  # 4/5


@pytest.mark.asyncio
async def test_12_spatial_consistency_score(db_session: AsyncSession):
    """12. Spatial consistency measures fraction of observations within geographic bounds."""
    source = Source(
        id=uuid.uuid4(),
        name="GPS Sensor Zeta",
        source_type=SourceType.WEATHER_API.value,
        connector_class="app.connectors.GPSConnector",
        trust_score=0.70,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    for i in range(5):
        valid_coords = i < 4
        r = WeatherReport(
            id=uuid.uuid4(),
            source_id=source.id,
            primary_category=WeatherCategory.RAINFALL.value,
            location_lat=13.0 if valid_coords else -45.0,
            location_lon=77.5 if valid_coords else 170.0,
            status="PROCESSED",
            event_time=now,
            ingested_at=now,
            is_duplicate=False,
            metadata_={"corroboration_type": CorroborationType.PRIMARY.value},
        )
        db_session.add(r)
    await db_session.commit()

    profile = await source_reputation_service.build_source_reputation(source.id, db_session)
    assert profile is not None
    assert profile.spatial_accuracy == 0.80  # 4/5


@pytest.mark.asyncio
async def test_13_denominator_zero_handling(db_session: AsyncSession):
    """13. Zero eligible observations returns None for rates (not 0.0 or divide-by-zero)."""
    source = Source(
        id=uuid.uuid4(),
        name="Zero Obs Source",
        source_type=SourceType.PUBLIC_DATASET.value,
        connector_class="app.connectors.DatasetConnector",
        trust_score=0.50,
        is_active=True,
    )
    db_session.add(source)
    await db_session.commit()

    profile = await source_reputation_service.build_source_reputation(source.id, db_session)
    assert profile is not None
    assert profile.corroboration_rate is None
    assert profile.contradiction_rate is None
    assert profile.verification_support_rate is None


@pytest.mark.asyncio
async def test_14_historical_timeline_reconstruction(db_session: AsyncSession):
    """14. Timeline reconstructs genesis, verification outcomes, and state milestones."""
    source = Source(
        id=uuid.uuid4(),
        name="Audit Tracked Station",
        source_type=SourceType.GOVERNMENT_API.value,
        connector_class="app.connectors.GovConnector",
        trust_score=0.85,
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    # Add 2 history adjustments
    hist1 = SourceReputationHistory(
        id=uuid.uuid4(),
        source_id=source.id,
        old_score=0.85,
        new_score=0.88,
        outcome="VERIFIED",
        recorded_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    hist2 = SourceReputationHistory(
        id=uuid.uuid4(),
        source_id=source.id,
        old_score=0.88,
        new_score=0.82,
        outcome="CONTRADICTED",
        recorded_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add_all([hist1, hist2])
    await db_session.commit()

    timeline_res = await source_reputation_service.get_source_reputation_timeline(source.id, db_session)
    assert timeline_res is not None
    assert len(timeline_res.timeline) >= 3
    event_types = [m.event_type for m in timeline_res.timeline]
    assert "SOURCE_REGISTERED" in event_types
    assert "VERIFICATION_CONFIRMED" in event_types
    assert "CONTRADICTION_FLAGGED" in event_types


@pytest.mark.asyncio
async def test_15_record_verification_outcome_and_trust_adjustment(db_session: AsyncSession):
    """15. Recording verification outcome dynamically adjusts trust and logs history."""
    source = Source(
        id=uuid.uuid4(),
        name="Dynamic Trust Station",
        source_type=SourceType.CITIZEN.value,
        connector_class="app.connectors.CitizenConnector",
        trust_score=0.55,
        is_active=True,
    )
    db_session.add(source)
    await db_session.commit()

    # Record a VERIFIED outcome
    updated = await source_reputation_service.record_verification_outcome(
        source_id=source.id,
        outcome="VERIFIED",
        event_id=uuid.uuid4(),
        db=db_session,
    )
    assert updated is not None
    assert updated.current_trust > 0.55

    # Check history record
    h_res = await db_session.execute(
        select(SourceReputationHistory).where(SourceReputationHistory.source_id == source.id)
    )
    history = h_res.scalars().all()
    assert len(history) == 1
    assert history[0].outcome == "VERIFIED"


@pytest.mark.asyncio
async def test_16_state_transition_determinism(db_session: AsyncSession):
    """16. State transitions are deterministic based on observation count and contradiction rate."""
    svc = source_reputation_service

    # NEW: 0 obs
    assert svc._determine_reputation_state(0, None, None, None, 0.5, False, 0) == ReputationState.NEW

    # INSUFFICIENT_EVIDENCE: 3 obs
    assert svc._determine_reputation_state(3, 1.0, 0.0, 0.0, 0.7, False, 0) == ReputationState.INSUFFICIENT_EVIDENCE

    # ESTABLISHED: 6 obs, 0.8 support, 0.1 contradiction
    assert svc._determine_reputation_state(6, 0.8, 0.1, 0.0, 0.65, False, 0) == ReputationState.ESTABLISHED

    # WATCH: 6 obs, 0.25 contradiction
    assert svc._determine_reputation_state(6, 0.75, 0.25, 0.0, 0.60, False, 1) == ReputationState.WATCH

    # LOW_RELIABILITY: 10 obs, 0.50 contradiction
    assert svc._determine_reputation_state(10, 0.50, 0.50, 0.0, 0.40, False, 5) == ReputationState.LOW_RELIABILITY

    # TRUSTED: 20 obs, 0.90 support, 0.05 contradiction, 0.85 trust
    assert svc._determine_reputation_state(20, 0.90, 0.05, 0.0, 0.85, False, 1) == ReputationState.TRUSTED


@pytest.mark.asyncio
async def test_17_dweg_integration(db_session: AsyncSession):
    """17. connect_source_to_dweg creates source reputation node without error."""
    source = Source(
        id=uuid.uuid4(),
        name="DWEG Linked Source",
        source_type=SourceType.WEATHER_API.value,
        connector_class="app.connectors.GenericConnector",
        trust_score=0.80,
        is_active=True,
    )
    db_session.add(source)
    await db_session.commit()

    # Test that DWEG linking executes gracefully
    event_id = uuid.uuid4()
    await source_reputation_service.connect_source_to_dweg(
        source_id=source.id,
        event_id=event_id,
        outcome="VERIFIED",
        db=db_session,
    )


@pytest.mark.asyncio
async def test_18_event_dna_navigation_compatibility(db_session: AsyncSession):
    """18. Source reputation integrates cleanly with Event DNA evidence fingerprints."""
    source = Source(
        id=uuid.uuid4(),
        name="DNA Evidenced Source",
        source_type=SourceType.GOVERNMENT_API.value,
        connector_class="app.connectors.IMDConnector",
        trust_score=0.88,
        is_active=True,
    )
    db_session.add(source)
    await db_session.commit()

    profile = await source_reputation_service.build_source_reputation(source.id, db_session)
    assert profile is not None
    assert profile.source_type == "GOVERNMENT_API"
    assert profile.current_trust == 0.88


@pytest.mark.asyncio
async def test_19_websocket_broadcast_on_update(db_session: AsyncSession):
    """19. Emits WebSocket broadcast when source reputation changes."""
    source = Source(
        id=uuid.uuid4(),
        name="WS Broadcast Sensor",
        source_type=SourceType.CITIZEN.value,
        connector_class="app.connectors.CitizenConnector",
        trust_score=0.50,
        is_active=True,
    )
    db_session.add(source)
    await db_session.commit()

    # Record outcome which calls _broadcast_reputation_events
    res = await source_reputation_service.record_verification_outcome(
        source_id=source.id,
        outcome="VERIFIED",
        event_id=uuid.uuid4(),
        db=db_session,
    )
    assert res is not None


@pytest.mark.asyncio
async def test_20_api_endpoints_and_rbac(
    client: AsyncClient,
    db_session: AsyncSession,
    test_analyst: User,
    auth_headers: Callable[[User], Dict[str, str]],
):
    """20. Validates REST API endpoints for Source Reputation under /api/v1/sources/reputation."""
    source = Source(
        id=uuid.uuid4(),
        name="API Test Doppler Source",
        source_type=SourceType.GOVERNMENT_API.value,
        connector_class="app.connectors.IMDConnector",
        trust_score=0.88,
        is_active=True,
    )
    db_session.add(source)
    await db_session.commit()

    headers = auth_headers(test_analyst)

    # GET /api/v1/sources/reputation
    resp = await client.get("/api/v1/sources/reputation", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert any(s["source_id"] == str(source.id) for s in data["items"])

    # GET /api/v1/sources/{id}/reputation
    resp_single = await client.get(f"/api/v1/sources/{source.id}/reputation", headers=headers)
    assert resp_single.status_code == 200
    single_data = resp_single.json()
    assert single_data["source_id"] == str(source.id)
    assert single_data["reputation_state"] == "NEW"

    # GET /api/v1/sources/{id}/reputation/timeline
    resp_timeline = await client.get(f"/api/v1/sources/{source.id}/reputation/timeline", headers=headers)
    assert resp_timeline.status_code == 200
    timeline_data = resp_timeline.json()
    assert "timeline" in timeline_data

    # GET /api/v1/sources/{id}/reputation/categories
    resp_cat = await client.get(f"/api/v1/sources/{source.id}/reputation/categories", headers=headers)
    assert resp_cat.status_code == 200
    cat_data = resp_cat.json()
    assert "categories" in cat_data
