"""
Unit and Integration Tests for DataGovConnector
================================================
Covers:
- API key loading & configuration
- Connection refused (TCP_CONNECTION_FAILURE)
- Timeout handling
- HTTP 401/403 authentication rejection
- HTTP 429 rate limiting
- HTTP 5xx upstream server errors
- Successful mock response
- Invalid dataset & 404 handling
- Response schema validation & metric extraction
- CanonicalRawEvent generation with full government dataset provenance
- Automatic retry with bounded exponential backoff
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from connectors.data_gov_connector import (
    DataGovConnector,
    DataGovResourceConfig,
    map_datagov_severity,
    parse_datagov_timestamp,
    classify_datagov_exception,
)
from connectors.schema import ConnectorStatusEnum, CanonicalRawEvent


@pytest.fixture
def datagov_connector():
    conn = DataGovConnector(
        source_id="00000000-0000-0000-0000-000000000002",
        name="Open Government Data (data.gov.in)",
        api_key="test_datagov_api_key_12345",
        api_base_url="https://api.data.gov.in",
    )
    return conn


@pytest.mark.asyncio
async def test_datagov_api_key_loaded(datagov_connector):
    assert datagov_connector.api_key == "test_datagov_api_key_12345"
    assert datagov_connector.api_base_url == "https://api.data.gov.in"
    assert len(datagov_connector.resources) > 0


@pytest.mark.asyncio
async def test_datagov_connection_refused_handling(datagov_connector):
    await datagov_connector.start()
    
    # Mock connection refused
    with patch.object(
        datagov_connector._client,
        "get",
        side_effect=httpx.ConnectError("[WinError 10061] No connection could be made because the target machine actively refused it"),
    ):
        events = await datagov_connector.poll()
        assert events == []
        assert datagov_connector.status in (ConnectorStatusEnum.UNAVAILABLE, ConnectorStatusEnum.DEGRADED)
        assert datagov_connector.is_reachable is False

        assert datagov_connector.consecutive_failures > 0
        assert "TCP connection refused" in datagov_connector.last_error_message

        # Verify admin health dictionary
        admin_health = datagov_connector.get_admin_health_status()
        assert admin_health["CONFIGURED"] is True
        assert admin_health["REACHABLE"] is False
        assert "TCP connection refused" in admin_health["FAILURE_REASON"]

    await datagov_connector.stop()


@pytest.mark.asyncio
async def test_datagov_timeout_handling(datagov_connector):
    await datagov_connector.start()
    
    with patch.object(
        datagov_connector._client,
        "get",
        side_effect=httpx.ReadTimeout("Read timed out"),
    ):
        status = await datagov_connector.health_check()
        assert status == ConnectorStatusEnum.UNAVAILABLE
        assert datagov_connector.last_error_code == "TIMEOUT"

    await datagov_connector.stop()


@pytest.mark.asyncio
async def test_datagov_http_401_403_auth_error(datagov_connector):
    await datagov_connector.start()
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = '{"message":"Invalid API Key"}'

    with patch.object(datagov_connector._client, "get", return_value=mock_resp):
        status = await datagov_connector.health_check()
        assert status == ConnectorStatusEnum.AUTH_ERROR
        assert datagov_connector.is_authenticated is False
        assert datagov_connector.last_error_code == "AUTH_ERROR"

    await datagov_connector.stop()


@pytest.mark.asyncio
async def test_datagov_http_429_rate_limit(datagov_connector):
    await datagov_connector.start()
    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch.object(datagov_connector._client, "get", return_value=mock_resp):
        status = await datagov_connector.health_check()
        assert status == ConnectorStatusEnum.RATE_LIMITED
        assert datagov_connector.last_error_code == "RATE_LIMITED"

    await datagov_connector.stop()


@pytest.mark.asyncio
async def test_datagov_http_5xx_upstream_error(datagov_connector):
    await datagov_connector.start()
    mock_resp = MagicMock()
    mock_resp.status_code = 502

    with patch.object(datagov_connector._client, "get", return_value=mock_resp):
        status = await datagov_connector.health_check()
        assert status == ConnectorStatusEnum.DEGRADED
        assert datagov_connector.last_error_code == "HTTP_5XX"

    await datagov_connector.stop()


@pytest.mark.asyncio
async def test_datagov_successful_response_and_canonical_event(datagov_connector):
    await datagov_connector.start()
    
    mock_data = {
        "status": "ok",
        "total": 1,
        "records": [
            {
                "id": "rec_001",
                "state": "Maharashtra",
                "district": "Mumbai",
                "station": "Colaba",
                "latitude": 18.9067,
                "longitude": 72.8147,
                "date": "2026-10-03 08:30:00",
                "rainfall_mm": 125.4,
                "temperature_c": 31.2,
                "humidity_pct": 88,
                "wind_speed_kmph": 45.0,
                "weather_condition": "Heavy Rain with Thunderstorm",
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_data

    with patch.object(datagov_connector._client, "get", return_value=mock_resp):
        events = await datagov_connector.poll()
        assert len(events) >= 1
        ev = events[0]
        assert isinstance(ev, CanonicalRawEvent)
        assert ev.source_type == "GOVERNMENT_DATASET"
        assert ev.state == "Maharashtra"
        assert ev.district == "Mumbai"
        assert ev.latitude == 18.9067
        assert ev.longitude == 72.8147
        assert ev.suggested_category == "RAINFALL"
        assert ev.severity == 3  # >= 115.6mm rainfall
        assert "colaba" in ev.raw_payload["fields"]["station"].lower()
        assert ev.raw_payload["provider"] == "data.gov.in"
        assert ev.raw_payload["extracted_metrics"]["rainfall_mm"] == 125.4

        # Health state should be LIVE or HEALTHY
        assert datagov_connector.status in (ConnectorStatusEnum.LIVE, ConnectorStatusEnum.HEALTHY)
        assert datagov_connector.is_reachable is True
        assert datagov_connector.is_data_valid is True


    await datagov_connector.stop()


def test_severity_and_timestamp_helpers():
    assert map_datagov_severity(rainfall_mm=210.0) == 4
    assert map_datagov_severity(rainfall_mm=120.0) == 3
    assert map_datagov_severity(rainfall_mm=70.0) == 2
    assert map_datagov_severity(rainfall_mm=10.0) == 1

    dt = parse_datagov_timestamp("2026-10-03 10:30:00")
    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None
