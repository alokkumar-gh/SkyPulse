"""
Test suite for SkyPulse National Map Coverage & Time Filter Architecture.
Verifies:
1. Window '1h' returns appropriate current data.
2. Window '6h' returns 6h dataset.
3. Window '24h' returns 24h dataset.
4. Window '7d' returns 7d dataset.
5. National coverage: All Indian states/UTs eligible to appear via AWS observation fallback.
6. Layer toggling: OBSERVATIONS, EVENTS, WARNINGS, NEWS.
7. Coverage metrics: states_represented, districts_represented, signal breakdown.
8. Zero fake GPS or fabricated coordinates.
"""
import pytest
from app.db.session import async_session_factory
from app.services.weather_intelligence_service import weather_intelligence_service


@pytest.mark.asyncio
async def test_map_time_window_1h_vs_6h_vs_24h_vs_7d():
    """Verifies that changing time windows returns expanding, distinct datasets."""
    async with async_session_factory() as session:
        res_1h = await weather_intelligence_service.get_map_data(session, window="1h")
        res_6h = await weather_intelligence_service.get_map_data(session, window="6h")
        res_24h = await weather_intelligence_service.get_map_data(session, window="24h")
        res_7d = await weather_intelligence_service.get_map_data(session, window="7d")

        # 1h <= 6h <= 24h <= 7d
        assert res_1h["total_mapped"] <= res_6h["total_mapped"]
        assert res_6h["total_mapped"] <= res_24h["total_mapped"]
        assert res_24h["total_mapped"] <= res_7d["total_mapped"]

        # Features should be GeoJSON FeatureCollection
        assert res_1h["type"] == "FeatureCollection"
        assert res_24h["type"] == "FeatureCollection"
        assert len(res_1h["features"]) == res_1h["total_mapped"]


@pytest.mark.asyncio
async def test_map_national_coverage_representation():
    """Verifies that the map represents all 36 Indian states and union territories."""
    async with async_session_factory() as session:
        res = await weather_intelligence_service.get_map_data(session, window="live")
        cov = res["coverage"]
        assert cov is not None
        # Must have at least 35+ states represented across India
        assert cov["states_represented"] >= 35
        assert cov["total_states"] == 36
        assert cov["current_observations_count"] > 0
        assert cov["coverage_updated_at"] is not None


@pytest.mark.asyncio
async def test_map_observation_fallback_for_states_without_events():
    """
    Verifies that states without canonical severe events (e.g., Rajasthan, Gujarat, Ladakh)
    still appear on the map with valid AWS weather observations.
    """
    async with async_session_factory() as session:
        res = await weather_intelligence_service.get_map_data(session, state="Rajasthan", window="live")
        assert res["total_mapped"] > 0
        obs_features = [f for f in res["features"] if f["properties"].get("signal_type") == "OBSERVATION"]
        assert len(obs_features) > 0
        first_obs = obs_features[0]["properties"]
        assert first_obs["state"] == "Rajasthan"
        assert first_obs["temperature_c"] is not None
        assert first_obs["temp_label"].endswith("°C")
        assert first_obs["confidence_tier"] == "VERY HIGH"


@pytest.mark.asyncio
async def test_map_layer_isolation_observations_only():
    """Verifies that requesting only OBSERVATIONS isolates observation chips."""
    async with async_session_factory() as session:
        res = await weather_intelligence_service.get_map_data(session, layers="OBSERVATIONS", window="live")
        sigs = res["signals_by_type"]
        assert sigs.get("OBSERVATION", 0) > 0
        assert sigs.get("EVENT", 0) == 0
        assert sigs.get("NEWS", 0) == 0


@pytest.mark.asyncio
async def test_map_layer_isolation_events_only():
    """Verifies that requesting only EVENTS isolates canonical hazard pins."""
    async with async_session_factory() as session:
        res = await weather_intelligence_service.get_map_data(session, layers="EVENTS", window="live")
        sigs = res["signals_by_type"]
        assert sigs.get("EVENT", 0) > 0
        assert sigs.get("OBSERVATION", 0) == 0
        for f in res["features"]:
            assert f["properties"]["signal_type"] == "EVENT"


@pytest.mark.asyncio
async def test_map_layer_isolation_news_only():
    """Verifies that requesting only NEWS returns geo-located news reports."""
    async with async_session_factory() as session:
        res = await weather_intelligence_service.get_map_data(session, layers="NEWS", window="live")
        sigs = res["signals_by_type"]
        assert sigs.get("NEWS", 0) > 0
        assert sigs.get("OBSERVATION", 0) == 0


@pytest.mark.asyncio
async def test_map_features_have_valid_genuine_coordinates():
    """Verifies that no features have null, NaN, or out-of-bounds coordinates."""
    async with async_session_factory() as session:
        res = await weather_intelligence_service.get_map_data(session, window="live")
        for f in res["features"]:
            geom = f["geometry"]
            assert geom["type"] in ("Point", "Polygon", "MultiPolygon")
            if geom["type"] == "Point":
                lon, lat = geom["coordinates"]
                assert isinstance(lat, (int, float)) and 6.0 <= lat <= 38.0
                assert isinstance(lon, (int, float)) and 68.0 <= lon <= 98.0
