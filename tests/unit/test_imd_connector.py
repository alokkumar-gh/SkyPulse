"""
Unit Tests for SkyPulse IMD Government Weather Data Connector
==============================================================
Tests parsing, normalization, time-handling, severity mapping,
error resilience, and idempotency for all official IMD feed types.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
import httpx

from connectors.imd_connector import (
    IMDConnector,
    parse_imd_timestamp,
    map_warning_color_to_severity,
    map_rainfall_to_severity,
    IST_TIMEZONE,
)
from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum
from connectors.normalizer import normalize_raw_event
from app.models.enums import WeatherCategory


# ============================================================================
# 1. TIMESTAMP PARSER TESTS
# ============================================================================

def test_parse_imd_timestamp_iso():
    iso_str = "2026-10-01T12:00:00Z"
    dt = parse_imd_timestamp(iso_str)
    assert dt.tzinfo == timezone.utc
    assert dt.year == 2026
    assert dt.month == 10
    assert dt.day == 1
    assert dt.hour == 12


def test_parse_imd_timestamp_ist_string():
    # 08:30 IST is 03:00 UTC
    ist_str = "01-10-2026 08:30 IST"
    dt = parse_imd_timestamp(ist_str)
    assert dt.tzinfo == timezone.utc
    assert dt.hour == 3
    assert dt.minute == 0



def test_parse_imd_timestamp_epoch():
    epoch_ts = 1790856000.0  # Unix timestamp
    dt = parse_imd_timestamp(epoch_ts)
    assert dt.tzinfo == timezone.utc


def test_parse_imd_timestamp_fallback():
    dt = parse_imd_timestamp(None)
    assert dt.tzinfo == timezone.utc
    assert isinstance(dt, datetime)


# ============================================================================
# 2. SEVERITY MAPPING TESTS
# ============================================================================

def test_map_warning_color_to_severity():
    assert map_warning_color_to_severity("RED") == 4
    assert map_warning_color_to_severity("Take Action (Red)") == 4
    assert map_warning_color_to_severity("ORANGE") == 3
    assert map_warning_color_to_severity("Be Prepared (Orange)") == 3
    assert map_warning_color_to_severity("YELLOW") == 2
    assert map_warning_color_to_severity("Be Updated (Yellow)") == 2
    assert map_warning_color_to_severity("GREEN") == 1
    assert map_warning_color_to_severity("No Warning") == 1
    assert map_warning_color_to_severity(None) == 2


def test_map_rainfall_to_severity():
    assert map_rainfall_to_severity(250.0) == 4  # Extremely heavy (>= 204.5mm)
    assert map_rainfall_to_severity(150.0) == 3  # Very heavy (115.6 - 204.4mm)
    assert map_rainfall_to_severity(75.0) == 2   # Heavy (64.5 - 115.5mm)
    assert map_rainfall_to_severity(25.0) == 1   # Light/Moderate (< 64.5mm)


# ============================================================================
# 3. FEED PARSING TESTS
# ============================================================================

@pytest.fixture
def imd_connector():
    return IMDConnector(
        source_id="00000000-0000-0000-0000-000000000002",
        name="India Meteorological Department",
        api_base_url="https://api.imd.gov.in",
        api_key="test-api-key",
    )


def test_parse_current_weather(imd_connector):
    raw_obs = {
        "station_id": "42182",
        "station_name": "New Delhi (Safdarjung)",
        "district": "New Delhi",
        "state": "Delhi",
        "latitude": 28.58,
        "longitude": 77.21,
        "observed_at": "2026-10-01T08:30:00+05:30",
        "temperature_c": 36.5,
        "humidity_pct": 78,
        "rainfall_24h_mm": 85.4,
        "wind_speed_kmh": 28.0,
        "wind_direction": "ENE",
        "pressure_hpa": 1004.2,
        "weather_condition": "Thunderstorm with rain",
    }

    event = imd_connector.parse_current_weather(raw_obs)
    assert isinstance(event, CanonicalRawEvent)
    assert event.source_type == "GOVERNMENT_API"
    assert event.district == "New Delhi"
    assert event.state == "Delhi"
    assert event.suggested_category == WeatherCategory.THUNDERSTORM.value
    assert event.severity == 2  # 85.4mm is Heavy rain (sev 2)
    assert event.raw_payload["data_type"] == "OBSERVATION"
    assert event.is_demo is False
    assert "Safdarjung" in event.text
    assert event.idempotency_key is not None


def test_parse_district_nowcast(imd_connector):
    raw_nowcast = {
        "district": "Cuttack",
        "state": "Odisha",
        "latitude": 20.46,
        "longitude": 85.88,
        "phenomena": "Moderate Thunderstorm with lightning and gusty surface wind (40-50 kmph)",
        "valid_from": "2026-10-01T14:00:00+05:30",
        "valid_until": "2026-10-01T17:00:00+05:30",
        "warning_level": "ORANGE",
    }

    event = imd_connector.parse_district_nowcast(raw_nowcast)
    assert event.source_type == "GOVERNMENT_API"
    assert event.district == "Cuttack"
    assert event.state == "Odisha"
    assert event.suggested_category == WeatherCategory.THUNDERSTORM.value
    assert event.severity == 3  # Orange -> 3
    assert event.raw_payload["data_type"] == "NOWCAST"
    assert "District Nowcast" in event.text
    assert "imd:nowcast:Cuttack" in event.idempotency_key


def test_parse_district_warning(imd_connector):
    raw_warning = {
        "district": "Ernakulam",
        "state": "Kerala",
        "latitude": 9.98,
        "longitude": 76.30,
        "color": "RED",
        "warning_type": "Extremely Heavy Rainfall Warning",
        "description": "Extremely heavy rainfall exceeding 204.4mm expected at isolated places.",
        "date": "2026-10-01",
    }

    event = imd_connector.parse_district_warning(raw_warning)
    assert event.source_type == "GOVERNMENT_API"
    assert event.district == "Ernakulam"
    assert event.suggested_category == WeatherCategory.RAINFALL.value
    assert event.severity == 4  # Red -> 4
    assert event.raw_payload["data_type"] == "WARNING"
    assert "RED" in event.text


def test_parse_district_rainfall(imd_connector):
    raw_rain = {
        "district": "Pune",
        "state": "Maharashtra",
        "actual_rainfall_mm": 128.5,
        "normal_rainfall_mm": 18.2,
        "departure_pct": 606.0,
        "category": "Large Excess",
        "date": "2026-10-01",
    }

    event = imd_connector.parse_district_rainfall(raw_rain)
    assert event.source_type == "GOVERNMENT_API"
    assert event.district == "Pune"
    assert event.suggested_category == WeatherCategory.RAINFALL.value
    assert event.severity == 3  # 128.5mm -> Very Heavy (sev 3)
    assert event.raw_payload["actual_rainfall_mm"] == 128.5
    assert "128.5 mm" in event.text


def test_parse_state_rainfall(imd_connector):
    raw_state = {
        "state": "Assam",
        "actual_rainfall_mm": 45.2,
        "normal_rainfall_mm": 12.0,
        "departure_pct": 276.0,
        "date": "2026-10-01",
    }

    event = imd_connector.parse_state_rainfall(raw_state)
    assert event.source_type == "GOVERNMENT_API"
    assert event.state == "Assam"
    assert event.suggested_category == WeatherCategory.RAINFALL.value
    assert event.raw_payload["spatial_level"] == "STATE"
    assert "Assam" in event.text


def test_parse_aws_observation(imd_connector):
    raw_aws = {
        "station_id": "AWS_MUM_04",
        "station_name": "Mumbai Santacruz AWS",
        "district": "Mumbai Suburban",
        "state": "Maharashtra",
        "latitude": 19.09,
        "longitude": 72.85,
        "timestamp": "2026-10-01T11:00:00+05:30",
        "temperature": 31.2,
        "humidity": 92,
        "rain_1h_mm": 38.5,
        "rain_24h_mm": 142.0,
        "wind_speed_kmh": 35.0,
        "wind_direction": "SSW",
        "pressure": 1002.5,
    }

    event = imd_connector.parse_aws_observation(raw_aws)
    assert event.source_type == "GOVERNMENT_API"
    assert event.raw_payload["sensor_type"] == "AWS"
    assert event.severity == 3  # 142.0mm -> sev 3
    assert event.suggested_category == WeatherCategory.RAINFALL.value
    assert "AWS Station Telemetry" in event.text


def test_parse_city_forecast(imd_connector):
    raw_fcst = {
        "city": "Chennai",
        "state": "Tamil Nadu",
        "forecast_date": "2026-10-02",
        "max_temp_c": 35.0,
        "min_temp_c": 27.0,
        "forecast": "Thunderstorm with rain",
    }

    event = imd_connector.parse_city_forecast(raw_fcst)
    assert event.source_type == "GOVERNMENT_API"
    assert event.city == "Chennai"
    # FORECAST semantic distinction
    assert event.raw_payload["data_type"] == "FORECAST"
    assert event.suggested_category == WeatherCategory.THUNDERSTORM.value
    assert "Official Forecast" in event.text


def test_parse_river_basin_qpf(imd_connector):
    raw_qpf = {
        "basin_name": "Mahanadi",
        "state": "Odisha",
        "qpf_range_mm": "51-100 mm",
        "valid_date": "2026-10-01",
    }

    event = imd_connector.parse_river_basin_qpf(raw_qpf)
    assert event.source_type == "GOVERNMENT_API"
    assert event.raw_payload["hydrological_type"] == "QPF"
    assert event.suggested_category == WeatherCategory.RAINFALL.value
    assert "Mahanadi" in event.text


# ============================================================================
# 4. NORMALIZATION & IDEMPOTENCY PIPELINE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_normalize_imd_event(imd_connector):
    from connectors.idempotency import idempotency_service
    idempotency_service._memory_cache.clear()

    raw_obs = {
        "station_id": "42182_TEST_NORM",
        "station_name": "New Delhi (Safdarjung Test)",
        "district": "New Delhi",
        "state": "Delhi",
        "latitude": 28.58,
        "longitude": 77.21,
        "observed_at": "2026-10-01T12:00:00+05:30",
        "temperature_c": 36.5,
        "humidity_pct": 78,
        "rainfall_24h_mm": 85.4,
        "weather_condition": "Thunderstorm with rain",
    }

    raw_event = imd_connector.parse_current_weather(raw_obs)
    norm_event = await normalize_raw_event(raw_event)

    assert norm_event.source_type == "GOVERNMENT_API"
    assert norm_event.primary_category == WeatherCategory.THUNDERSTORM.value
    assert norm_event.district == "New Delhi"
    assert norm_event.tracking_id.startswith("SP-")
    assert norm_event.is_duplicate is False

    # Second normalization of the identical event triggers duplicate detection
    norm_event_2 = await normalize_raw_event(raw_event)
    assert norm_event_2.is_duplicate is True


# ============================================================================
# 5. CONNECTOR HEALTH & ERROR RESILIENCE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_health_check_not_configured():
    conn = IMDConnector(api_base_url="")
    status = await conn.health_check()
    assert status == ConnectorStatusEnum.NOT_CONFIGURED


@pytest.mark.asyncio
async def test_health_check_healthy(imd_connector):
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = httpx.Response(status_code=200)
        imd_connector.is_running = True
        status = await imd_connector.health_check()
        assert status == ConnectorStatusEnum.HEALTHY


@pytest.mark.asyncio
async def test_health_check_auth_error(imd_connector):
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = httpx.Response(status_code=401)
        imd_connector.is_running = True
        status = await imd_connector.health_check()
        assert status == ConnectorStatusEnum.ERROR
        assert "Authentication failed" in imd_connector.metrics.last_error


@pytest.mark.asyncio
async def test_poll_handles_network_failure(imd_connector):
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
        imd_connector.is_running = True
        events = await imd_connector.poll()
        assert events == []
        assert imd_connector.metrics.records_rejected > 0
        assert imd_connector.status == ConnectorStatusEnum.ERROR
