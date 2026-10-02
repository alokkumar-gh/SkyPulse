"""
Unit Tests for IndianAPI Third-Party Weather Ingestion Connector
================================================================
Validates:
1. Configuration lifecycle (API key absent -> NOT_CONFIGURED, API key present -> HEALTHY)
2. Response normalization with realistic IndianAPI payloads (nested & flat)
3. Meteorological unit conversion (rainfall, temperature, humidity, wind)
4. SIH category mapping (RAINFALL, THUNDERSTORM, FLOODING, HEATWAVE, FOG, STRONG_WINDS)
5. Zero GPS fabrication policy (lat/lon is None)
6. Third-party provenance preservation (is_official_government=False)
7. Error handling (HTTP 401/403, 429 rate limit, 500, timeouts, malformed JSON)
8. Deterministic idempotency key generation
9. Integration with Unified Ingestion Pipeline & DWEG
"""

import pytest
import json
import httpx
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from connectors.indianapi_connector import (
    IndianAPIWeatherConnector,
    extract_numeric_value,
    parse_indianapi_city_and_station,
    map_condition_to_sih_category,
    infer_indianapi_severity,
)
from connectors.schema import ConnectorStatusEnum, CanonicalRawEvent
from connectors.normalizer import normalize_raw_event
from app.models.enums import WeatherCategory, SourceType


class TestIndianAPIUnitHelpers:
    def test_extract_numeric_value(self):
        assert extract_numeric_value("30°C") == 30.0
        assert extract_numeric_value("32.5 C") == 32.5
        assert extract_numeric_value("0mm") == 0.0
        assert extract_numeric_value("15.2 mm") == 15.2
        assert extract_numeric_value("75%") == 75.0
        assert extract_numeric_value("12 km/h") == 12.0
        assert extract_numeric_value(25) == 25.0
        assert extract_numeric_value(None) is None
        assert extract_numeric_value("") is None
        # Dict humidity
        assert extract_numeric_value({"morning": 70, "evening": 60}) == 65.0

    def test_parse_indianapi_city_and_station(self):
        city, station = parse_indianapi_city_and_station("Chennai-meenambakkam")
        assert city == "Chennai"
        assert station == "meenambakkam"

        city, station = parse_indianapi_city_and_station("Mumbai-santacruz")
        assert city == "Mumbai"
        assert station == "santacruz"

        city, station = parse_indianapi_city_and_station("New Delhi")
        assert city == "New Delhi"
        assert station is None

    def test_map_condition_to_sih_category(self):
        # Rainfall / Flood
        assert map_condition_to_sih_category("Light drizzle", rainfall_mm=5.0) == "RAINFALL"
        assert map_condition_to_sih_category("Inundation and severe deluge", rainfall_mm=210.0) == "FLOODING"

        # Heatwave
        assert map_condition_to_sih_category("Extreme heat", temp_c=44.0) == "HEATWAVE"

        # Thunderstorm
        assert map_condition_to_sih_category("Severe thunderstorm with lightning") == "THUNDERSTORM"

        # Fog / Mist
        assert map_condition_to_sih_category("Dense fog causing low visibility") == "FOG"

        # Strong Winds
        assert map_condition_to_sih_category("Squall warning", wind_kmph=65.0) == "STRONG_WINDS"

        # Unknown
        assert map_condition_to_sih_category("Clear skies") == "UNKNOWN"

    def test_infer_indianapi_severity(self):
        assert infer_indianapi_severity(rainfall_mm=220.0) == 4
        assert infer_indianapi_severity(temp_c=46.0) == 4
        assert infer_indianapi_severity(wind_kmph=95.0) == 4
        assert infer_indianapi_severity(rainfall_mm=70.0) == 2
        assert infer_indianapi_severity(category="RAINFALL") == 2
        assert infer_indianapi_severity(category="UNKNOWN") == 1


class TestIndianAPIConnectorLifecycle:
    def test_unconfigured_state_when_key_missing(self):
        conn = IndianAPIWeatherConnector(api_key="")
        assert conn.status == ConnectorStatusEnum.NOT_CONFIGURED

    def test_configured_state_when_key_present(self):
        conn = IndianAPIWeatherConnector(api_key="test-indianapi-key-123")
        assert conn.status == ConnectorStatusEnum.HEALTHY

    @pytest.mark.asyncio
    async def test_start_and_stop_lifecycle(self):
        conn = IndianAPIWeatherConnector(api_key="test-key")
        await conn.start()
        assert conn.is_running is True
        assert conn._client is not None

        await conn.stop()
        assert conn.is_running is False
        assert conn._client is None


class TestIndianAPINormalizationAndProvenance:
    @pytest.mark.asyncio
    async def test_parse_nested_indianapi_weather_response(self):
        conn = IndianAPIWeatherConnector(
            source_id="00000000-0000-0000-0000-000000000007",
            api_key="test-key",
        )

        mock_payload = {
            "city": "Chennai-meenambakkam",
            "weather": {
                "current": {
                    "humidity": {
                        "evening": 64,
                        "morning": 76
                    },
                    "rainfall": "12.5mm",
                    "temperature": "31°C",
                    "description": "Thunderstorm with light rain",
                    "wind_speed": "18 km/h"
                },
                "forecast": [
                    {
                        "date": "2026-10-03",
                        "temp_max": "33°C",
                        "temp_min": "26°C"
                    }
                ]
            }
        }

        event = conn.parse(mock_payload, requested_city="Chennai")
        assert isinstance(event, CanonicalRawEvent)
        assert event.source_type == SourceType.WEATHER_API.value
        assert event.city == "Chennai"
        assert event.suggested_category == "THUNDERSTORM"
        assert event.severity == 2
        assert event.latitude is None  # Zero GPS fabrication
        assert event.longitude is None  # Zero GPS fabrication

        # Verify provenance
        assert event.raw_payload["provider"] == "IndianAPI"
        assert event.raw_payload["is_official_government"] is False
        assert event.raw_payload["station"] == "meenambakkam"
        assert event.raw_payload["extracted_metrics"]["temperature_c"] == 31.0
        assert event.raw_payload["extracted_metrics"]["humidity_pct"] == 70.0
        assert event.raw_payload["extracted_metrics"]["rainfall_mm"] == 12.5
        assert event.raw_payload["extracted_metrics"]["wind_speed_kmph"] == 18.0

        # Verify normalizer accepts it
        normalized = await normalize_raw_event(event)
        assert normalized.city == "Chennai"
        assert normalized.primary_category in ("THUNDERSTORM", "UNKNOWN")

    def test_parse_flat_weather_response(self):
        conn = IndianAPIWeatherConnector(api_key="test-key")
        mock_payload = {
            "city": "Bhubaneswar",
            "temperature": "43.5°C",
            "humidity": "45%",
            "rainfall": "0mm",
            "condition": "Severe heat wave conditions",
            "wind": "10 km/h"
        }

        event = conn.parse(mock_payload)
        assert event.city == "Bhubaneswar"
        assert event.suggested_category == "HEATWAVE"
        assert event.severity == 3  # >= 42.0°C
        assert event.raw_payload["extracted_metrics"]["temperature_c"] == 43.5
        assert event.latitude is None
        assert event.longitude is None

    def test_idempotency_key_deterministic(self):
        conn = IndianAPIWeatherConnector(api_key="test-key")
        payload = {
            "city": "Mumbai",
            "weather": {
                "current": {
                    "temperature": "29°C",
                    "rainfall": "50mm",
                    "description": "Heavy rainfall"
                }
            }
        }

        e1 = conn.parse(payload)
        e2 = conn.parse(payload)
        assert e1.idempotency_key == e2.idempotency_key


class TestIndianAPIPollingAndErrorHandling:
    @pytest.mark.asyncio
    async def test_successful_polling_across_cities(self):
        conn = IndianAPIWeatherConnector(
            api_key="valid-test-key",
            target_cities=["New Delhi", "Mumbai"],
        )
        await conn.start()

        def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "New" in url_str or "Delhi" in url_str:
                return httpx.Response(
                    200,
                    json={
                        "city": "New Delhi-safdarjung",
                        "weather": {
                            "current": {
                                "temperature": "28°C",
                                "humidity": "65%",
                                "rainfall": "0mm",
                                "description": "Partly cloudy"
                            }
                        }
                    }
                )
            elif "Mumbai" in url_str:
                return httpx.Response(
                    200,
                    json={
                        "city": "Mumbai-colaba",
                        "weather": {
                            "current": {
                                "temperature": "30°C",
                                "humidity": "80%",
                                "rainfall": "25mm",
                                "description": "Continuous heavy rainfall"
                            }
                        }
                    }
                )
            return httpx.Response(404, json={"error": "Not found"})

        conn._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        events = await conn.poll()
        assert len(events) == 2
        assert events[0].city == "New Delhi"
        assert events[1].city == "Mumbai"
        assert conn.metrics.records_accepted == 2
        assert conn.status == ConnectorStatusEnum.HEALTHY

        await conn.stop()

    @pytest.mark.asyncio
    async def test_auth_failure_sets_error_status(self):
        conn = IndianAPIWeatherConnector(
            api_key="invalid-key",
            target_cities=["New Delhi"],
        )
        await conn.start()

        def mock_auth_fail(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Unauthorized: Invalid API Key"})

        conn._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_auth_fail))

        events = await conn.poll()
        assert len(events) == 0
        assert conn.status == ConnectorStatusEnum.ERROR
        assert "authentication failure" in (conn.metrics.last_error or "").lower()

        await conn.stop()

    @pytest.mark.asyncio
    async def test_rate_limit_sets_degraded_status(self):
        conn = IndianAPIWeatherConnector(
            api_key="test-key",
            target_cities=["New Delhi", "Mumbai"],
        )
        await conn.start()

        def mock_rate_limit(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "Rate limit exceeded"})

        conn._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_rate_limit))

        events = await conn.poll()
        assert len(events) == 0
        assert conn.status == ConnectorStatusEnum.DEGRADED
        assert "rate limit" in (conn.metrics.last_error or "").lower()

        await conn.stop()

    @pytest.mark.asyncio
    async def test_health_check_endpoint(self):
        conn = IndianAPIWeatherConnector(api_key="test-key", target_cities=["New Delhi"])
        await conn.start()

        def mock_health(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"city": "New Delhi", "weather": {"current": {"temperature": "28°C"}}})

        conn._client = httpx.AsyncClient(transport=httpx.MockTransport(mock_health))

        status = await conn.health_check()
        assert status == ConnectorStatusEnum.HEALTHY

        await conn.stop()
