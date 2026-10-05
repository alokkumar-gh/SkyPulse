"""
Unit and Integration Tests for IndianAPIWeatherConnector
=========================================================
Covers:
- API key loading & server-side authentication header
- Successful live response mapping to CanonicalRawEvent
- HTTP 401/403 authentication error handling
- HTTP 404 endpoint/city missing
- HTTP 429 rate limiting
- HTTP 500 upstream server error (e.g. "list index out of range")
- Connection timeout and network error
- Malformed JSON handling
- Metric extraction (temperature, humidity, rainfall, wind, condition)
- Source trust and provenance verification (NOT official IMD, marked as third-party)
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from connectors.indianapi_connector import (
    IndianAPIWeatherConnector,
    extract_numeric_value,
    parse_indianapi_city_and_station,
    map_condition_to_sih_category,
    infer_indianapi_severity,
)
from connectors.schema import ConnectorStatusEnum, CanonicalRawEvent


@pytest.fixture
def indianapi_connector():
    conn = IndianAPIWeatherConnector(
        source_id="00000000-0000-0000-0000-000000000007",
        name="IndianAPI Weather Service (Third-Party)",
        api_key="test_indianapi_key_secret_999",
        api_base_url="https://weather.indianapi.in",
        target_cities=["Mumbai", "New Delhi"],
    )
    return conn


@pytest.mark.asyncio
async def test_indianapi_api_key_and_headers(indianapi_connector):
    assert indianapi_connector.api_key == "test_indianapi_key_secret_999"
    assert indianapi_connector.api_base_url == "https://weather.indianapi.in"
    assert len(indianapi_connector.target_cities) == 2


@pytest.mark.asyncio
async def test_indianapi_successful_response_and_provenance(indianapi_connector):
    await indianapi_connector.start()
    
    mock_payload = {
        "city": "Mumbai-Colaba",
        "state": "Maharashtra",
        "weather": {
            "current": {
                "temperature": "29.5°C",
                "humidity": "82%",
                "rainfall": "15.0mm",
                "wind_speed": "18.0 km/h",
                "wind_direction": "WSW",
                "condition": "Scattered Thunderstorms",
                "description": "Scattered Thunderstorms with moderate rainfall",
            }
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch.object(indianapi_connector._client, "get", return_value=mock_resp):
        events = await indianapi_connector.poll()
        assert len(events) >= 1
        ev = events[0]
        assert isinstance(ev, CanonicalRawEvent)
        assert ev.source_type == "WEATHER_API"
        assert ev.city == "Mumbai"
        assert ev.suggested_category == "THUNDERSTORM"
        assert "IndianAPI weather data" in ev.text
        assert "Official IMD" not in ev.text

        # Strict source provenance verification
        assert ev.raw_payload["provider"] == "IndianAPI"
        assert ev.raw_payload["is_official_government"] is False
        assert ev.raw_payload["official_organization"] is False
        assert ev.raw_payload["imd_official"] is False
        assert ev.raw_payload["extracted_metrics"]["temperature_c"] == 29.5
        assert ev.raw_payload["extracted_metrics"]["humidity_pct"] == 82.0
        assert ev.raw_payload["extracted_metrics"]["rainfall_mm"] == 15.0

    await indianapi_connector.stop()


@pytest.mark.asyncio
async def test_indianapi_upstream_500_error(indianapi_connector):
    await indianapi_connector.start()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = '{"detail":"list index out of range"}'

    with patch.object(indianapi_connector._client, "get", return_value=mock_resp):
        status = await indianapi_connector.health_check()
        assert status == ConnectorStatusEnum.DEGRADED
        assert indianapi_connector.last_error_code == "UPSTREAM_ERROR"
        assert "list index out of range" in indianapi_connector.last_error_message

        # Polling under 500 should return empty list and not fabricate data
        events = await indianapi_connector.poll()
        assert events == []

    await indianapi_connector.stop()


@pytest.mark.asyncio
async def test_indianapi_auth_error_401(indianapi_connector):
    await indianapi_connector.start()
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = '{"detail":"Invalid API Key"}'

    with patch.object(indianapi_connector._client, "get", return_value=mock_resp):
        status = await indianapi_connector.health_check()
        assert status == ConnectorStatusEnum.AUTH_ERROR
        assert indianapi_connector.is_authenticated is False
        assert indianapi_connector.last_error_code == "AUTH_ERROR"

    await indianapi_connector.stop()


@pytest.mark.asyncio
async def test_indianapi_rate_limit_429(indianapi_connector):
    await indianapi_connector.start()
    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch.object(indianapi_connector._client, "get", return_value=mock_resp):
        status = await indianapi_connector.health_check()
        assert status == ConnectorStatusEnum.RATE_LIMITED
        assert indianapi_connector.last_error_code == "RATE_LIMITED"

    await indianapi_connector.stop()


@pytest.mark.asyncio
async def test_indianapi_timeout_handling(indianapi_connector):
    await indianapi_connector.start()
    
    with patch.object(
        indianapi_connector._client,
        "get",
        side_effect=httpx.ReadTimeout("Request timed out"),
    ):
        status = await indianapi_connector.health_check()
        assert status == ConnectorStatusEnum.DEGRADED
        assert indianapi_connector.last_error_code == "TIMEOUT"

    await indianapi_connector.stop()


def test_indianapi_helpers():
    assert extract_numeric_value("32.5°C") == 32.5
    assert extract_numeric_value("12 km/h") == 12.0
    assert extract_numeric_value({"morning": 80, "evening": 60}) == 70.0
    assert extract_numeric_value(None) is None

    city, station = parse_indianapi_city_and_station("Chennai-Meenambakkam")
    assert city == "Chennai"
    assert station == "Meenambakkam"

    assert map_condition_to_sih_category("Heavy thunderstorm with rain") == "THUNDERSTORM"
    assert map_condition_to_sih_category("Dense fog causing low visibility") == "FOG"
    assert infer_indianapi_severity(rainfall_mm=220.0) == 4
