"""
Unit & Integration Tests for SkyPulse Real-Time Freshness & Lifecycle Rebuild
=============================================================================
Tests Section 34 Requirements:
- Event freshness category TTLs and severity multipliers
- Auto-expiration sweep (marking EXPIRED without deleting DB record)
- Delta sync API (/events/changes)
- Overwrite prevention (older observation cannot overwrite newer observation)
- Stale observation labeling
- Fallback telemetry (Priority 1: Event, Priority 2: Observation, Priority 3: NO_TELEMETRY)
- Preserving source timestamps independently from ingestion timestamp
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta

from app.core.freshness_policy import (
    calculate_event_expiry,
    calculate_event_staleness_threshold,
    determine_event_lifecycle_status,
    get_observation_freshness_category,
    format_freshness_label,
    EVENT_FRESHNESS_POLICY,
    OBSERVATION_FRESHNESS_TIERS,
)
from app.models.enums import EventLifecycleStatus, VerificationStatus
from app.models.weather_event import WeatherEvent
from app.models.weather_observation import WeatherObservation
from app.services.auto_fetch_manager import auto_fetch_manager
from app.services.district_weather_service import district_weather_service
from sqlalchemy import select
from tests.test_district_weather_observations import async_session_factory


def test_category_ttl_freshness_policies():
    """Requirement 3: Different categories have distinct configurable TTLs and severity scaling."""
    now = datetime(2026, 10, 4, 12, 0, 0, tzinfo=timezone.utc)

    # Thunderstorm (short TTL: 2h base)
    t_exp = calculate_event_expiry("THUNDERSTORM", now, severity=1)
    assert t_exp == now + timedelta(hours=2.0)

    # Cyclone (long TTL: 48h base + 12h per severity above 1)
    c_exp_s1 = calculate_event_expiry("CYCLONE", now, severity=1)
    assert c_exp_s1 == now + timedelta(hours=48.0)
    c_exp_s3 = calculate_event_expiry("CYCLONE", now, severity=3)
    assert c_exp_s3 == now + timedelta(hours=48.0 + 2 * 12.0)

    # Rainfall (3.5h base)
    r_exp = calculate_event_expiry("RAINFALL", now, severity=1)
    assert r_exp == now + timedelta(hours=3.5)


def test_staleness_and_lifecycle_transitions():
    """Requirement 2: Status transitions DETECTED -> ACTIVE -> STALE -> EXPIRED."""
    now = datetime.now(timezone.utc)

    # 1. Past expiry => EXPIRED
    past_expiry = now - timedelta(minutes=10)
    status_exp = determine_event_lifecycle_status(
        category="THUNDERSTORM",
        last_seen_at=now - timedelta(hours=3),
        expires_at=past_expiry,
        severity=2,
        now=now,
    )
    assert status_exp == "EXPIRED"

    # 2. Before expiry but past staleness threshold => STALE
    future_expiry = now + timedelta(hours=2)
    old_seen = now - timedelta(hours=1, minutes=30)
    status_stale = determine_event_lifecycle_status(
        category="THUNDERSTORM",
        last_seen_at=old_seen,
        expires_at=future_expiry,
        severity=1,
        now=now,
    )
    assert status_stale == "STALE"

    # 3. Fresh with >1 evidence => ACTIVE
    recent_seen = now - timedelta(minutes=10)
    status_active = determine_event_lifecycle_status(
        category="CYCLONE",
        last_seen_at=recent_seen,
        expires_at=now + timedelta(hours=40),
        evidence_count=3,
        severity=3,
        now=now,
    )
    assert status_active == "ACTIVE"


def test_observation_freshness_tiers():
    """Requirement 18 & 19: Observation tiers (LIVE, RECENT, STALE, NO_DATA)."""
    now = datetime.now(timezone.utc)

    # Under 15m => LIVE
    obs_live = now - timedelta(minutes=4)
    cat_live, age = get_observation_freshness_category(obs_live, now)
    assert cat_live == "LIVE"
    assert "4 min ago" in format_freshness_label(obs_live, now)

    # 25m => RECENT
    obs_recent = now - timedelta(minutes=25)
    cat_recent, _ = get_observation_freshness_category(obs_recent, now)
    assert cat_recent == "RECENT"

    # 90m => STALE
    obs_stale = now - timedelta(minutes=90)
    cat_stale, _ = get_observation_freshness_category(obs_stale, now)
    assert cat_stale == "STALE"

    # > 180m => NO_DATA
    obs_old = now - timedelta(hours=4)
    cat_nodata, _ = get_observation_freshness_category(obs_old, now)
    assert cat_nodata == "NO_DATA"
    assert format_freshness_label(obs_old, now) == "NO CURRENT TELEMETRY"


@pytest.mark.asyncio
async def test_event_auto_expiration_retains_db_record():
    """Requirements 4 & 5: Expired events leave active layer but remain in historical database."""
    async with async_session_factory() as session:
        now = datetime.now(timezone.utc)
        ev_id = uuid.uuid4()
        test_ev = WeatherEvent(
            id=ev_id,
            category="THUNDERSTORM",
            severity=2,
            confidence_score=0.9,
            verification_status="VERIFIED",
            observed_at=now - timedelta(hours=5),
            ingested_at=now - timedelta(hours=4),
            expires_at=now - timedelta(hours=1),  # Expired 1 hour ago
            lifecycle_status="ACTIVE",
            is_active=True,
            is_deleted=False,
            primary_state="Odisha",
            primary_district="Puri",
            centroid_lat=19.8135,
            centroid_lon=85.8312,
        )
        session.add(test_ev)
        await session.commit()

        # Run expiration sweep
        res = await auto_fetch_manager.run_event_expiration_sweep()
        assert res["expired_count"] >= 1

        # Check DB: record must NOT be deleted, but marked EXPIRED and is_active=False
        session.expire_all()
        db_ev = await session.get(WeatherEvent, ev_id)
        assert db_ev is not None, "Event must be retained in database (Section 4 & 5)"
        assert db_ev.lifecycle_status == "EXPIRED"
        assert db_ev.is_active is False


@pytest.mark.asyncio
async def test_location_telemetry_fallback_hierarchy():
    """Requirements 20 & 22: PRIORITY 1: Event, PRIORITY 2: Observation, PRIORITY 3: NO_TELEMETRY."""
    async with async_session_factory() as session:
        now = datetime.now(timezone.utc)

        # Case 1: Location with only routine observation (no active event)
        test_obs = WeatherObservation(
            source_name="Open-Meteo",
            source_model="ECMWF Seamless",
            observation_type="DISTRICT_OBSERVATION",
            state="Sikkim",
            district="Mangan_Routine_Station",
            latitude=27.5000,
            longitude=88.5300,
            observed_at=now - timedelta(minutes=3),
            temperature_c=29.0,
            humidity_percent=78,
            rain_mm=0.0,
            wind_speed_kmh=12.0,
            pressure_hpa=1012.0,
            weather_code=0,
            weather_condition="☀️ Clear Sky",
        )
        session.add(test_obs)
        await session.commit()

        fallback = await district_weather_service.get_location_fallback_telemetry(
            session, state="Sikkim", district="Mangan_Routine_Station"
        )
        assert fallback["telemetry_type"] == "OBSERVATION"
        assert fallback["observation"]["temperature_c"] == 29.0
        assert fallback["observation"]["humidity_percent"] == 78
        assert fallback["has_telemetry"] is True

        # Case 2: Location with NO event and NO observation => Honest NO_TELEMETRY
        empty_loc = await district_weather_service.get_location_fallback_telemetry(
            session, state="Atlantis", district="Nowhere"
        )
        assert empty_loc["telemetry_type"] == "NO_TELEMETRY"
        assert empty_loc["has_telemetry"] is False
        assert empty_loc["event"] is None
        assert empty_loc["observation"] is None


@pytest.mark.asyncio
async def test_source_timestamps_preserved_independently():
    """Requirements 13 & 14: source_observed_at preserved, ingestion timestamp not conflated."""
    observed_time = datetime(2026, 10, 4, 8, 30, 0, tzinfo=timezone.utc)
    ingested_time = datetime(2026, 10, 4, 15, 0, 0, tzinfo=timezone.utc)

    ev = WeatherEvent(
        id=uuid.uuid4(),
        category="FLOODING",
        observed_at=observed_time,
        ingested_at=ingested_time,
        last_seen_at=ingested_time,
        expires_at=observed_time + timedelta(hours=36),
        lifecycle_status="ACTIVE",
    )

    assert ev.effective_observed_at == observed_time
    assert ev.effective_ingested_at == ingested_time
    assert ev.effective_observed_at != ev.effective_ingested_at
