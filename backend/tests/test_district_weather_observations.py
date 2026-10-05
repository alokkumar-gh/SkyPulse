import pytest
from app.db.session import async_session_factory
from app.services.district_weather_service import district_weather_service


@pytest.mark.asyncio
async def test_district_weather_service_structure():
    """Verifies that district weather service retrieves real observation structures."""
    async with async_session_factory() as session:
        districts = await district_weather_service.get_district_weather_list(session)
        assert isinstance(districts, list)
        assert len(districts) > 0

        first = districts[0]
        assert "district_name" in first
        assert "state" in first
        assert "latitude" in first
        assert "longitude" in first
        assert "weather" in first
        assert "temperature_c" in first["weather"]
        assert "source" in first
        assert first["source"]["provider"] == "Open-Meteo"


@pytest.mark.asyncio
async def test_map_observations_layer_geojson():
    """Verifies that observation layer outputs valid GeoJSON for the map."""
    async with async_session_factory() as session:
        layer = await district_weather_service.get_map_observations_layer(session, zoom=6)
        assert layer["type"] == "FeatureCollection"
        assert layer["layer"] == "DISTRICT_WEATHER_OBSERVATIONS"
        assert len(layer["features"]) > 0

        feat = layer["features"][0]
        assert feat["type"] == "Feature"
        assert "geometry" in feat
        assert feat["geometry"]["type"] == "Point"
        assert "properties" in feat
        assert "temperature_c" in feat["properties"]
        assert "weather_icon" in feat["properties"]
        assert feat["properties"]["layer_type"] == "WEATHER_OBSERVATION"
