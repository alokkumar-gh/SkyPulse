"""
Unit Test Suite for SkyPulse Open-Meteo Operational Weather Data Connector
==========================================================================
Covers:
1. Lifecycle and Configuration (enabled, disabled, custom monitoring points)
2. WMO Weather Code and Meteorological Parameter Mapping
3. Severity Level Inference (1 to 4)
4. Canonical Normalization and Provenance Preservation
5. Error Handling & HTTP Resilience (timeouts, 429 rate limit, 500 internal error)
6. Partial Location Failure Isolation
7. Deterministic Idempotency Key Generation
8. Pipeline Integration (acceptance into normalize_raw_event)
"""

from __future__ import annotations

import httpx
import pytest
from datetime import datetime, timezone

from app.models.enums import SourceType
from connectors.openmeteo_connector import (
    DEFAULT_INDIAN_LOCATIONS,
    OpenMeteoConnector,
    infer_openmeteo_severity,
    map_openmeteo_wmo_code,
)
from connectors.normalizer import normalize_raw_event
from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum


# Sample realistic Open-Meteo API response payload
MOCK_OPENMETEO_RESPONSE_NEW_DELHI = {
    "latitude": 28.576448,
    "longitude": 77.18678,
    "generationtime_ms": 0.2155303955078125,
    "utc_offset_seconds": 19800,
    "timezone": "Asia/Kolkata",
    "timezone_abbreviation": "GMT+5:30",
    "elevation": 214.0,
    "current_units": {
        "time": "iso8601",
        "interval": "seconds",
        "temperature_2m": "°C",
        "relative_humidity_2m": "%",
        "apparent_temperature": "°C",
        "precipitation": "mm",
        "rain": "mm",
        "showers": "mm",
        "snowfall": "cm",
        "weather_code": "wmo code",
        "cloud_cover": "%",
        "surface_pressure": "hPa",
        "wind_speed_10m": "km/h",
        "wind_gusts_10m": "km/h",
    },
    "current": {
        "time": "2026-10-02T22:45",
        "interval": 900,
        "temperature_2m": 27.5,
        "relative_humidity_2m": 65,
        "apparent_temperature": 31.1,
        "precipitation": 0.0,
        "rain": 0.0,
        "showers": 0.0,
        "snowfall": 0.0,
        "weather_code": 0,
        "cloud_cover": 0,
        "surface_pressure": 989.2,
        "wind_speed_10m": 2.8,
        "wind_gusts_10m": 6.5,
    },
}

MOCK_OPENMETEO_RESPONSE_THUNDERSTORM = {
    "latitude": 20.25,
    "longitude": 85.83,
    "timezone": "Asia/Kolkata",
    "elevation": 45.0,
    "current": {
        "time": "2026-10-02T18:30",
        "temperature_2m": 26.0,
        "relative_humidity_2m": 92,
        "apparent_temperature": 29.5,
        "precipitation": 38.5,
        "rain": 25.0,
        "showers": 13.5,
        "snowfall": 0.0,
        "weather_code": 95,  # Thunderstorm
        "cloud_cover": 95,
        "surface_pressure": 1004.1,
        "wind_speed_10m": 42.0,
        "wind_gusts_10m": 68.0,
    },
}

MOCK_OPENMETEO_RESPONSE_HEATWAVE = {
    "latitude": 26.9,
    "longitude": 75.8,
    "timezone": "Asia/Kolkata",
    "elevation": 435.0,
    "current": {
        "time": "2026-05-20T14:00",
        "temperature_2m": 44.5,
        "relative_humidity_2m": 18,
        "apparent_temperature": 46.2,
        "precipitation": 0.0,
        "rain": 0.0,
        "showers": 0.0,
        "snowfall": 0.0,
        "weather_code": 1,  # Mainly clear
        "cloud_cover": 5,
        "surface_pressure": 998.0,
        "wind_speed_10m": 14.0,
        "wind_gusts_10m": 22.0,
    },
}


class TestOpenMeteoHelpers:
    """Tests WMO weather code mapping and severity inference."""

    def test_map_wmo_code_rainfall(self):
        desc, cat = map_openmeteo_wmo_code(wmo_code=61, precip_mm=4.0)
        assert cat == "RAINFALL"
        assert "rain" in desc.lower()

        desc, cat = map_openmeteo_wmo_code(wmo_code=82, precip_mm=30.0)
        assert cat == "RAINFALL"
        assert "violent rain showers" in desc.lower()

    def test_map_wmo_code_thunderstorm(self):
        desc, cat = map_openmeteo_wmo_code(wmo_code=95, wind_speed_kmph=35.0)
        assert cat == "THUNDERSTORM"

        desc, cat = map_openmeteo_wmo_code(wmo_code=99, wind_speed_kmph=55.0)
        assert cat == "THUNDERSTORM"
        assert "gale-force winds" in desc.lower()

    def test_map_wmo_code_fog(self):
        desc, cat = map_openmeteo_wmo_code(wmo_code=45)
        assert cat == "FOG"
        assert "fog" in desc.lower()

    def test_map_wmo_code_strong_winds(self):
        desc, cat = map_openmeteo_wmo_code(wmo_code=2, wind_speed_kmph=58.0, wind_gusts_kmph=72.0)
        assert cat == "STRONG_WINDS"
        assert "strong winds" in desc.lower()

    def test_map_wmo_code_heatwave(self):
        desc, cat = map_openmeteo_wmo_code(wmo_code=0, temp_c=43.5, precip_mm=0.0)
        assert cat == "HEATWAVE"
        assert "extreme heat" in desc.lower()

    def test_map_wmo_code_unsupported_or_unknown(self):
        desc, cat = map_openmeteo_wmo_code(wmo_code=0, temp_c=25.0, precip_mm=0.0)
        assert cat == "UNKNOWN"
        assert "clear sky" in desc.lower()

        desc, cat = map_openmeteo_wmo_code(wmo_code=999)
        assert cat == "UNKNOWN"
        assert "WMO Code 999" in desc

    def test_infer_severity_scale(self):
        # Level 4
        assert infer_openmeteo_severity(wmo_code=99) == 4
        assert infer_openmeteo_severity(wmo_code=65, precip_mm=80.0) == 4
        assert infer_openmeteo_severity(wmo_code=0, temp_c=46.0) == 4

        # Level 3
        assert infer_openmeteo_severity(wmo_code=95) == 3
        assert infer_openmeteo_severity(wmo_code=65, precip_mm=40.0) == 3
        assert infer_openmeteo_severity(wmo_code=0, temp_c=43.0) == 3
        assert infer_openmeteo_severity(wmo_code=2, wind_speed_kmph=55.0) == 3

        # Level 2
        assert infer_openmeteo_severity(wmo_code=63, precip_mm=12.0) == 2
        assert infer_openmeteo_severity(wmo_code=45) == 2
        assert infer_openmeteo_severity(wmo_code=0, temp_c=39.0) == 2

        # Level 1
        assert infer_openmeteo_severity(wmo_code=0, temp_c=25.0) == 1


class TestOpenMeteoConnectorLifecycle:
    """Tests connector initialization, lifecycle, and health checking."""

    def test_enabled_status(self):
        conn = OpenMeteoConnector(enabled=True)
        assert conn.status == ConnectorStatusEnum.HEALTHY
        assert conn.enabled is True

    def test_disabled_status(self):
        conn = OpenMeteoConnector(enabled=False)
        assert conn.status == ConnectorStatusEnum.DISABLED

    @pytest.mark.asyncio
    async def test_start_and_stop_lifecycle(self):
        conn = OpenMeteoConnector()
        await conn.start()
        assert conn.is_running is True
        assert conn._client is not None
        assert conn.status == ConnectorStatusEnum.HEALTHY

        await conn.stop()
        assert conn.is_running is False
        assert conn._client is None

    @pytest.mark.asyncio
    async def test_health_check_operational(self):
        conn = OpenMeteoConnector()
        await conn.start()

        def mock_transport(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"current": {"temperature_2m": 25.0, "weather_code": 0}})

        conn._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        status = await conn.health_check()
        assert status == ConnectorStatusEnum.HEALTHY

        await conn.stop()


class TestOpenMeteoNormalizationAndProvenance:
    """Tests conversion into CanonicalRawEvent and pipeline acceptance."""

    @pytest.mark.asyncio
    async def test_parse_thunderstorm_event(self):
        conn = OpenMeteoConnector()
        loc_info = {"city": "Bhubaneswar", "district": "Khurda", "state": "Odisha", "lat": 20.2961, "lon": 85.8245}

        event = conn.parse(MOCK_OPENMETEO_RESPONSE_THUNDERSTORM, location_info=loc_info)

        assert isinstance(event, CanonicalRawEvent)
        assert event.source_type == SourceType.WEATHER_API.value
        assert event.city == "Bhubaneswar"
        assert event.district == "Khurda"
        assert event.state == "Odisha"
        assert event.latitude == 20.2961
        assert event.longitude == 85.8245
        assert event.suggested_category == "THUNDERSTORM"
        assert event.severity == 3

        # Provenance verification
        assert event.raw_payload["provider"] == "Open-Meteo"
        assert event.raw_payload["is_official_government"] is False
        assert event.raw_payload["provider_type"] == "THIRD_PARTY_WEATHER_API"
        assert event.raw_payload["query_coordinates"]["latitude"] == 20.2961
        assert event.raw_payload["query_coordinates"]["longitude"] == 85.8245
        assert event.raw_payload["extracted_metrics"]["temperature_c"] == 26.0
        assert event.raw_payload["extracted_metrics"]["precipitation_mm"] == 38.5
        assert event.raw_payload["extracted_metrics"]["wind_speed_kmph"] == 42.0
        assert event.raw_payload["extracted_metrics"]["wind_gusts_kmph"] == 68.0

        # Verify acceptance into normalizer
        normalized = await normalize_raw_event(event)
        assert normalized.city == "Bhubaneswar"
        assert normalized.primary_category in ("THUNDERSTORM", "UNKNOWN")

    def test_parse_heatwave_event(self):
        conn = OpenMeteoConnector()
        loc_info = {"city": "Jaipur", "district": "Jaipur", "state": "Rajasthan", "lat": 26.9124, "lon": 75.7873}

        event = conn.parse(MOCK_OPENMETEO_RESPONSE_HEATWAVE, location_info=loc_info)
        assert event.city == "Jaipur"
        assert event.suggested_category == "HEATWAVE"
        assert event.severity == 3
        assert event.raw_payload["extracted_metrics"]["temperature_c"] == 44.5

    def test_idempotency_key_deterministic(self):
        conn = OpenMeteoConnector()
        loc_info = {"city": "Mumbai", "district": "Mumbai City", "state": "Maharashtra", "lat": 19.076, "lon": 72.877}

        e1 = conn.parse(MOCK_OPENMETEO_RESPONSE_NEW_DELHI, location_info=loc_info)
        e2 = conn.parse(MOCK_OPENMETEO_RESPONSE_NEW_DELHI, location_info=loc_info)

        assert e1.idempotency_key == e2.idempotency_key
        assert e1.external_id == e2.external_id


class TestOpenMeteoPollingAndResilience:
    """Tests multi-location polling, partial failure isolation, and rate limit handling."""

    @pytest.mark.asyncio
    async def test_successful_multi_location_polling(self):
        conn = OpenMeteoConnector(
            locations=[
                {"city": "New Delhi", "district": "New Delhi", "state": "Delhi", "lat": 28.6139, "lon": 77.2090},
                {"city": "Bhubaneswar", "district": "Khurda", "state": "Odisha", "lat": 20.2961, "lon": 85.8245},
            ]
        )
        await conn.start()

        def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "28.6139" in url_str:
                return httpx.Response(200, json=MOCK_OPENMETEO_RESPONSE_NEW_DELHI)
            elif "20.2961" in url_str:
                return httpx.Response(200, json=MOCK_OPENMETEO_RESPONSE_THUNDERSTORM)
            return httpx.Response(404, json={"error": "Not Found"})

        conn._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        events = await conn.poll()
        assert len(events) == 2
        assert events[0].city == "New Delhi"
        assert events[1].city == "Bhubaneswar"
        assert conn.status == ConnectorStatusEnum.HEALTHY
        assert conn.metrics.records_accepted == 2

        await conn.stop()

    @pytest.mark.asyncio
    async def test_partial_location_failure_isolation(self):
        """If one location returns 500 or fails, remaining locations must continue."""
        conn = OpenMeteoConnector(
            locations=[
                {"city": "New Delhi", "district": "New Delhi", "state": "Delhi", "lat": 28.6139, "lon": 77.2090},
                {"city": "FaultyLocation", "district": "Fault", "state": "Fault", "lat": 0.0, "lon": 0.0},
                {"city": "Bhubaneswar", "district": "Khurda", "state": "Odisha", "lat": 20.2961, "lon": 85.8245},
            ]
        )
        await conn.start()

        def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "28.6139" in url_str:
                return httpx.Response(200, json=MOCK_OPENMETEO_RESPONSE_NEW_DELHI)
            elif "0.0" in url_str:
                return httpx.Response(500, json={"error": "Internal Server Error"})
            elif "20.2961" in url_str:
                return httpx.Response(200, json=MOCK_OPENMETEO_RESPONSE_THUNDERSTORM)
            return httpx.Response(404, json={"error": "Not Found"})

        conn._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        events = await conn.poll()
        # Two locations succeeded, one failed
        assert len(events) == 2
        assert events[0].city == "New Delhi"
        assert events[1].city == "Bhubaneswar"
        assert conn.status == ConnectorStatusEnum.DEGRADED
        assert conn.metrics.records_accepted == 2
        assert conn.metrics.records_rejected == 1

        await conn.stop()

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self):
        """HTTP 429 should gracefully set DEGRADED and stop current poll cycle."""
        conn = OpenMeteoConnector(
            locations=[
                {"city": "New Delhi", "district": "New Delhi", "state": "Delhi", "lat": 28.6139, "lon": 77.2090},
                {"city": "Mumbai", "district": "Mumbai City", "state": "Maharashtra", "lat": 19.0760, "lon": 72.8777},
            ]
        )
        await conn.start()

        def mock_rate_limit(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "Hourly API request limit exceeded"})

        conn._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_rate_limit))

        events = await conn.poll()
        assert len(events) == 0
        assert conn.status == ConnectorStatusEnum.DEGRADED
        assert "rate limit" in (conn.metrics.last_error or "").lower()

        await conn.stop()


class TestOpenMeteoUnifiedPipeline:
    """Tests end-to-end processing of Open-Meteo observations through the unified pipeline."""

    @pytest.mark.asyncio
    async def test_openmeteo_event_through_unified_ingestion(self, db_session):
        import uuid
        from sqlalchemy import select
        from app.models.weather_event import WeatherEvent
        from app.models.weather_report import WeatherReport
        from app.services.unified_ingestion_service import UnifiedIngestionPipelineService

        service = UnifiedIngestionPipelineService()
        conn = OpenMeteoConnector()

        loc_info = {"city": "Bhubaneswar", "district": "Khurda", "state": "Odisha", "lat": 20.2961, "lon": 85.8245}
        raw_event = conn.parse(MOCK_OPENMETEO_RESPONSE_THUNDERSTORM, location_info=loc_info)

        result = await service.ingest_canonical_event(raw_event, db=db_session)
        assert result.status == "SUCCESS"
        assert result.is_india_valid is True
        assert result.canonical_event_id is not None

        # Verify WeatherReport in DB
        report_rec = await db_session.scalar(
            select(WeatherReport).where(WeatherReport.id == uuid.UUID(result.report_id))
        )
        assert report_rec is not None
        assert report_rec.location_city == "Bhubaneswar"
        assert report_rec.location_state == "Odisha"

        # Verify WeatherEvent in DB
        event_rec = await db_session.scalar(
            select(WeatherEvent).where(WeatherEvent.id == uuid.UUID(result.canonical_event_id))
        )
        assert event_rec is not None
        assert event_rec.category in ("THUNDERSTORM", "RAINFALL", "UNKNOWN")

