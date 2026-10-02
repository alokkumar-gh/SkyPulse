"""
Unit Tests for SkyPulse Emerging Weather Event Detection Service
================================================================
Validates all 15 minimum functional intelligence requirements:
1. Single weak signal does not create emergence
2. Multiple compatible signals create SIGNAL
3. Temporal acceleration increases emergence score
4. Spatial convergence increases emergence score
5. Independent source diversity increases emergence score
6. Duplicate reports do not artificially increase score
7. Contradictory evidence reduces emergence score
8. Stale signals expire deterministically
9. State transitions are deterministic (SIGNAL -> DEVELOPING -> EMERGING -> CONFIRMED -> DISSIPATING -> EXPIRED)
10. Category-specific rules and meteorological synergies work
11. DWEG integration works
12. Event DNA genesis integration works
13. WebSocket events emitted on detection / state updates
14. API endpoint query and filtering works
15. Empty dataset handled gracefully with zero crashes
"""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.weather_report import WeatherReport
from app.models.weather_event import WeatherEvent
from app.models.source import Source
from app.models.enums import EmergenceState, WeatherCategory, VerificationStatus
from app.services.emerging_event_service import emerging_event_service, EmergingEventService


async def _create_source(
    db: AsyncSession,
    name: str = "Test Ingestion Feed",
    source_type: str = "CITIZEN",
    trust: float = 0.85,
) -> Source:
    src = Source(
        id=uuid.uuid4(),
        name=name,
        source_type=source_type,
        connector_class="TestConnector",
        trust_score=trust,
    )
    db.add(src)
    await db.flush()
    return src


async def _create_report(
    db: AsyncSession,
    source: Source,
    category: str = "RAINFALL",
    lat: float = 22.5726,
    lon: float = 88.3639,
    minutes_ago: int = 15,
    severity: int = 2,
    raw_text: str = "Moderate rainfall observed.",
    is_duplicate: bool = False,
    verification_status: str = "UNVERIFIED",
) -> WeatherReport:
    now = datetime.now(timezone.utc)
    ts = now - timedelta(minutes=minutes_ago)
    rep = WeatherReport(
        id=uuid.uuid4(),
        source_id=source.id,
        primary_category=category,
        severity=severity,
        location_lat=lat,
        location_lon=lon,
        location_state="West Bengal",
        location_district="Kolkata",
        raw_content=raw_text,
        normalized_text=raw_text,
        is_duplicate=is_duplicate,
        status="FLAGGED" if verification_status == "CONTRADICTED" else "PROCESSED",
        classification_confidence=0.75,
        ingested_at=ts,
        event_time=ts,
    )
    db.add(rep)
    await db.flush()
    return rep



@pytest.mark.asyncio
async def test_empty_dataset_handled_gracefully(db_session: AsyncSession):
    """Scenario 15: Empty dataset returns empty list without crashing."""
    res = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60)
    assert res == []


@pytest.mark.asyncio
async def test_single_weak_signal_does_not_create_emergence(db_session: AsyncSession):
    """Scenario 1: A single isolated report is insufficient to form an emerging event."""
    src = await _create_source(db_session, name="Single Citizen", source_type="CITIZEN")
    await _create_report(db_session, src, category="RAINFALL", minutes_ago=10)

    res = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60)
    assert len(res) == 0


@pytest.mark.asyncio
async def test_multiple_compatible_signals_create_signal_state(db_session: AsyncSession):
    """Scenario 2: Multiple compatible signals create a cluster in SIGNAL state."""
    src = await _create_source(db_session, name="Citizen App", source_type="CITIZEN")
    await _create_report(db_session, src, category="RAINFALL", lat=22.57, lon=88.36, minutes_ago=25, raw_text="Rain started at Park Street")
    await _create_report(db_session, src, category="RAINFALL", lat=22.58, lon=88.37, minutes_ago=15, raw_text="Light shower near Salt Lake")

    res = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60)
    assert len(res) >= 1
    event = res[0]
    assert event.state in {EmergenceState.SIGNAL, EmergenceState.DEVELOPING}
    assert event.evidence_count == 2
    assert event.dominant_category == WeatherCategory.RAINFALL
    assert event.spatial_radius_km > 0.0


@pytest.mark.asyncio
async def test_temporal_acceleration_increases_emergence_score(db_session: AsyncSession):
    """Scenario 3: Higher arrival rate in recent window accelerates emergence score."""
    src = await _create_source(db_session, name="Crowd Feed", source_type="CITIZEN")

    # Cluster A: Steady 2 reports in older half, 1 report in recent half
    now = datetime.now(timezone.utc)
    for i in range(2):
        await _create_report(db_session, src, category="THUNDERSTORM", lat=19.07, lon=72.87, minutes_ago=45 + i * 5, raw_text=f"Mumbai rumble {i}")
    await _create_report(db_session, src, category="THUNDERSTORM", lat=19.08, lon=72.88, minutes_ago=10, raw_text="Mumbai flash 1")

    res_slow = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60, category="THUNDERSTORM")
    score_slow = res_slow[0].factors.temporal_acceleration_score

    # Now add high accelerating burst in the last 10 minutes
    for i in range(5):
        await _create_report(db_session, src, category="THUNDERSTORM", lat=19.075 + i * 0.005, lon=72.875 + i * 0.005, minutes_ago=5 - i, raw_text=f"Mumbai lightning strike {i}")

    res_fast = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60, category="THUNDERSTORM")
    score_fast = res_fast[0].factors.temporal_acceleration_score

    assert score_fast > score_slow
    assert res_fast[0].acceleration_indicator > 1.0


@pytest.mark.asyncio
async def test_spatial_convergence_increases_emergence_score(db_session: AsyncSession):
    """Scenario 4: Tightly clustered spatial coordinates yield higher spatial convergence score than dispersed ones."""
    src = await _create_source(db_session, name="State Weather", source_type="CITIZEN")

    # Tight cluster (within ~3 km)
    await _create_report(db_session, src, category="FOG", lat=28.6139, lon=77.2090, minutes_ago=20, raw_text="Delhi Fog 1")
    await _create_report(db_session, src, category="FOG", lat=28.6180, lon=77.2120, minutes_ago=15, raw_text="Delhi Fog 2")
    await _create_report(db_session, src, category="FOG", lat=28.6100, lon=77.2050, minutes_ago=10, raw_text="Delhi Fog 3")

    res = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60, category="FOG")
    assert len(res) == 1
    assert res[0].factors.spatial_convergence_score >= 0.80
    assert res[0].spatial_radius_km < 15.0


@pytest.mark.asyncio
async def test_source_diversity_increases_emergence_score(db_session: AsyncSession):
    """Scenario 5: Multi-source corroboration (IMD + Citizen + Weather Station) increases emergence score."""
    src_cit = await _create_source(db_session, name="Citizen App", source_type="CITIZEN")
    src_imd = await _create_source(db_session, name="IMD Doppler Feed", source_type="GOVERNMENT_API")
    src_aws = await _create_source(db_session, name="AWS Automatic Station", source_type="WEATHER_API")

    # 1. Citizen only
    await _create_report(db_session, src_cit, category="STRONG_WINDS", lat=13.08, lon=80.27, minutes_ago=25, raw_text="Chennai gust 1")
    await _create_report(db_session, src_cit, category="STRONG_WINDS", lat=13.09, lon=80.28, minutes_ago=20, raw_text="Chennai gust 2")

    res_single = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60, category="STRONG_WINDS")
    div_single = res_single[0].factors.source_diversity_score

    # 2. Add IMD + Weather Station
    await _create_report(db_session, src_imd, category="STRONG_WINDS", lat=13.085, lon=80.275, minutes_ago=10, raw_text="IMD Radar high wind velocity signature")
    await _create_report(db_session, src_aws, category="STRONG_WINDS", lat=13.082, lon=80.272, minutes_ago=5, raw_text="AWS Anemometer 62 km/h")

    res_multi = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60, category="STRONG_WINDS")
    div_multi = res_multi[0].factors.source_diversity_score

    assert div_multi > div_single
    assert res_multi[0].source_count >= 3
    assert res_multi[0].factors.meteorological_support_score > res_single[0].factors.meteorological_support_score


@pytest.mark.asyncio
async def test_duplicate_reports_do_not_artificially_increase_score(db_session: AsyncSession):
    """Scenario 6: Deduplicated repeated posts do not inflate signal count or emergence score."""
    src = await _create_source(db_session, name="Social Feed", source_type="CITIZEN")

    # 2 legitimate distinct reports
    await _create_report(db_session, src, category="HEATWAVE", lat=26.91, lon=75.78, minutes_ago=30, raw_text="Jaipur scorching heat 44C")
    await _create_report(db_session, src, category="HEATWAVE", lat=26.92, lon=75.79, minutes_ago=25, raw_text="Jaipur heat advisory active")

    res_base = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60, category="HEATWAVE")
    count_base = res_base[0].evidence_count

    # Add 5 duplicate flagged reports of identical text
    for i in range(5):
        await _create_report(db_session, src, category="HEATWAVE", lat=26.91, lon=75.78, minutes_ago=20 - i, raw_text="Jaipur scorching heat 44C", is_duplicate=True)

    res_dup = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60, category="HEATWAVE")
    assert res_dup[0].evidence_count == count_base


@pytest.mark.asyncio
async def test_contradictory_evidence_reduces_emergence_score(db_session: AsyncSession):
    """Scenario 7: Contradicted reports trigger a contradiction penalty that lowers emergence score."""
    src = await _create_source(db_session, name="Citizen App", source_type="CITIZEN")

    # Consistent reports
    await _create_report(db_session, src, category="DUST_STORM", lat=26.23, lon=73.02, minutes_ago=30, raw_text="Jodhpur sandstorm approaching")
    await _create_report(db_session, src, category="DUST_STORM", lat=26.24, lon=73.03, minutes_ago=20, raw_text="Jodhpur visibility dropping")

    res_clean = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60, category="DUST_STORM")
    score_clean = res_clean[0].emergence_score

    # Add contradicted observation
    await _create_report(db_session, src, category="DUST_STORM", lat=26.235, lon=73.025, minutes_ago=10, raw_text="Clear skies false alarm", verification_status="CONTRADICTED")

    res_penalized = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60, category="DUST_STORM")
    assert res_penalized[0].factors.contradiction_penalty > 0.0
    assert res_penalized[0].emergence_score < score_clean


@pytest.mark.asyncio
async def test_stale_signals_expire_deterministically(db_session: AsyncSession):
    """Scenario 8: If signals are older than 90 minutes without refresh, state transitions to EXPIRED."""
    src = await _create_source(db_session, name="Old Observations", source_type="CITIZEN")

    await _create_report(db_session, src, category="FOG", lat=30.73, lon=76.77, minutes_ago=110, raw_text="Chandigarh dense fog morning")
    await _create_report(db_session, src, category="FOG", lat=30.74, lon=76.78, minutes_ago=95, raw_text="Chandigarh visibility < 100m")

    res = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=180, category="FOG")
    assert len(res) == 1
    assert res[0].state == EmergenceState.EXPIRED


@pytest.mark.asyncio
async def test_state_transitions_are_deterministic(db_session: AsyncSession):
    """Scenario 9: State progression from SIGNAL -> DEVELOPING -> EMERGING is deterministic."""
    src_cit = await _create_source(db_session, name="Citizen", source_type="CITIZEN")
    src_imd = await _create_source(db_session, name="IMD Official", source_type="GOVERNMENT_API")

    # 1. Two basic reports -> SIGNAL
    await _create_report(db_session, src_cit, category="THUNDERSTORM", lat=12.97, lon=77.59, minutes_ago=35, raw_text="Bengaluru thunder 1")
    await _create_report(db_session, src_cit, category="THUNDERSTORM", lat=12.98, lon=77.60, minutes_ago=30, raw_text="Bengaluru thunder 2")

    res1 = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60, category="THUNDERSTORM")
    assert res1[0].state in {EmergenceState.SIGNAL, EmergenceState.DEVELOPING}

    # 2. Add 3 more reports from independent official source -> EMERGING
    await _create_report(db_session, src_imd, category="THUNDERSTORM", lat=12.975, lon=77.595, minutes_ago=15, raw_text="Doppler radar cell detected")
    await _create_report(db_session, src_imd, category="THUNDERSTORM", lat=12.972, lon=77.592, minutes_ago=10, raw_text="Lightning discharge warning")
    await _create_report(db_session, src_cit, category="THUNDERSTORM", lat=12.978, lon=77.598, minutes_ago=5, raw_text="Heavy downpour starting")

    res2 = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60, category="THUNDERSTORM")
    assert res2[0].state == EmergenceState.EMERGING
    assert res2[0].emergence_score >= 0.65


@pytest.mark.asyncio
async def test_category_specific_rules_and_synergies(db_session: AsyncSession):
    """Scenario 10: Category synergies cluster related meteorological phenomena (e.g. RAINFALL + FLOODING)."""
    src = await _create_source(db_session, name="Met Source", source_type="CITIZEN")

    # Ingest Rainfall and Flooding in same city
    await _create_report(db_session, src, category="RAINFALL", lat=25.59, lon=85.13, minutes_ago=25, raw_text="Patna torrential rain")
    await _create_report(db_session, src, category="FLOODING", lat=25.60, lon=85.14, minutes_ago=15, raw_text="Water logging in Patna low-lying streets")

    res = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60)
    assert len(res) >= 1
    # Both reports should cluster together due to RAINFALL <-> FLOODING synergy
    patna_cluster = next((e for e in res if "Patna" in (e.location_summary or "") or e.spatial_centroid_lat == pytest.approx(25.595, abs=0.05)), None)
    assert patna_cluster is not None
    assert patna_cluster.evidence_count == 2


@pytest.mark.asyncio
async def test_dweg_and_event_dna_integration(db_session: AsyncSession):
    """Scenario 11 & 12: DWEG node connectivity and Event DNA genesis timeline are populated."""
    src = await _create_source(db_session, name="IMD Doppler", source_type="GOVERNMENT_API")

    await _create_report(db_session, src, category="CYCLONE", lat=20.29, lon=85.82, minutes_ago=30, raw_text="Bhubaneswar coastal gale warning")
    await _create_report(db_session, src, category="CYCLONE", lat=20.30, lon=85.83, minutes_ago=15, raw_text="Bhubaneswar barometric pressure dropping")

    res = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60, category="CYCLONE")
    assert len(res) == 1
    ev = res[0]
    assert ev.dweg_node_id.startswith("node-emg-")
    assert len(ev.timeline) >= 2
    assert ev.timeline[0].title == "First Signal Detected"
    assert ev.timeline[0].state == EmergenceState.SIGNAL


@pytest.mark.asyncio
async def test_websocket_broadcast_emits_payload(db_session: AsyncSession):
    """Scenario 13: broadcast_emerging_event sends properly structured payload over WebSocket manager."""
    src = await _create_source(db_session, name="Sensor", source_type="WEATHER_API")
    await _create_report(db_session, src, category="HEATWAVE", lat=23.25, lon=77.41, minutes_ago=20, raw_text="Bhopal 43.5C")
    await _create_report(db_session, src, category="HEATWAVE", lat=23.26, lon=77.42, minutes_ago=10, raw_text="Bhopal 44.0C")

    res = await emerging_event_service.detect_emerging_events(db=db_session, lookback_minutes=60, category="HEATWAVE")
    ev = res[0]

    with patch("app.core.websocket_manager.ws_manager.broadcast", new_callable=AsyncMock) as mock_broadcast:
        await emerging_event_service.broadcast_emerging_event(ev, event_subtype="detected")
        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args[0][0]
        assert call_args["type"] == "emerging_event.detected"
        assert call_args["emerging_event_id"] == ev.id
        assert call_args["category"] == "HEATWAVE"
        assert "centroid" in call_args


@pytest.mark.asyncio
async def test_api_endpoints_list_and_details(db_session: AsyncSession, client: AsyncClient):
    """Scenario 14: REST API endpoints under /api/v1/emerging-events work correctly."""
    src = await _create_source(db_session, name="IMD Sensor", source_type="GOVERNMENT_API")
    await _create_report(db_session, src, category="RAINFALL", lat=15.29, lon=74.12, minutes_ago=20, raw_text="Goa heavy rain")
    await _create_report(db_session, src, category="RAINFALL", lat=15.30, lon=74.13, minutes_ago=10, raw_text="Goa rain intensifying")

    # 1. List emerging events
    resp = await client.get("/api/v1/emerging-events?category=RAINFALL")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1

    emg_id = data["items"][0]["id"]

    # 2. Get specific emerging event
    detail_resp = await client.get(f"/api/v1/emerging-events/{emg_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["id"] == emg_id
    assert detail_data["dominant_category"] == "RAINFALL"
    assert "factors" in detail_data

    # 3. Get signals
    signals_resp = await client.get(f"/api/v1/emerging-events/{emg_id}/signals")
    assert signals_resp.status_code == 200
    signals_data = signals_resp.json()
    assert len(signals_data["signals"]) >= 2

    # 4. Get timeline
    timeline_resp = await client.get(f"/api/v1/emerging-events/{emg_id}/timeline")
    assert timeline_resp.status_code == 200
    timeline_data = timeline_resp.json()
    assert len(timeline_data["milestones"]) >= 2

    # 5. Get evidence
    evidence_resp = await client.get(f"/api/v1/emerging-events/{emg_id}/evidence")
    assert evidence_resp.status_code == 200
    evidence_data = evidence_resp.json()
    assert "source_diversity" in evidence_data

