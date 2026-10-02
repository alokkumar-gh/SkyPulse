"""
Unit Tests for Open Government Data (data.gov.in) Connector
===========================================================
Tests parsing, timestamp normalization, severity mapping,
deterministic idempotency, pagination, health checks, and error resilience.
"""

import pytest
import httpx
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from connectors.data_gov_connector import (
    DataGovConnector,
    DataGovResourceConfig,
    parse_datagov_timestamp,
    map_datagov_severity,
    IST_TIMEZONE,
)
from connectors.schema import ConnectorStatusEnum
from connectors.normalizer import normalize_raw_event
from connectors.idempotency import idempotency_service
from app.models.enums import WeatherCategory, SourceType


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def rainfall_resource():
    return DataGovResourceConfig(
        resource_id="rainfall-district-daily-v1",
        dataset_name="Daily District Rainfall Report",
        agency_name="India Meteorological Department / MoES",
        category="RAINFALL",
        limit=10,
        location_fields={"state": "state", "district": "district", "station": "station"},
        observation_fields={"rainfall": "rainfall_mm", "temperature": "temp_c"},
    )


@pytest.fixture
def datagov_connector(rainfall_resource):
    conn = DataGovConnector(
        source_id="00000000-0000-0000-0000-000000000003",
        api_base_url="https://api.data.gov.in",
        api_key="test-api-key-sample-12345",
        config={"resources": [rainfall_resource.model_dump()]},
    )
    return conn


# ============================================================================
# 1. TIMESTAMP PARSING TESTS
# ============================================================================

def test_parse_datagov_timestamp_iso():
    dt = parse_datagov_timestamp("2026-10-01T08:30:00+05:30")
    assert dt.tzinfo == timezone.utc
    assert dt.hour == 3
    assert dt.minute == 0


def test_parse_datagov_timestamp_ist_string():
    dt = parse_datagov_timestamp("01-10-2026 08:30 IST")
    assert dt.tzinfo == timezone.utc
    assert dt.day == 1
    assert dt.month == 10
    assert dt.year == 2026
    assert dt.hour == 3
    assert dt.minute == 0


def test_parse_datagov_timestamp_indian_date_formats():
    # DD-MM-YYYY
    dt1 = parse_datagov_timestamp("01-10-2026")
    assert dt1.day == 1
    assert dt1.month == 10
    assert dt1.year == 2026

    # DD/MM/YYYY
    dt2 = parse_datagov_timestamp("15/08/2026")
    assert dt2.day == 15
    assert dt2.month == 8
    assert dt2.year == 2026

    # DD-b-YYYY
    dt3 = parse_datagov_timestamp("01-Oct-2026")
    assert dt3.day == 1
    assert dt3.month == 10
    assert dt3.year == 2026


def test_parse_datagov_timestamp_epoch():
    epoch_sec = 1790823600  # 2026-10-01 03:00:00 UTC
    dt = parse_datagov_timestamp(epoch_sec)
    assert dt == datetime(2026, 10, 1, 3, 0, 0, tzinfo=timezone.utc)


def test_parse_datagov_timestamp_fallback():
    dt = parse_datagov_timestamp("unparseable-date-string")
    assert isinstance(dt, datetime)
    assert dt.tzinfo == timezone.utc


# ============================================================================
# 2. SEVERITY MAPPING TESTS
# ============================================================================

def test_map_datagov_severity_rainfall():
    assert map_datagov_severity(rainfall_mm=250.0) == 4   # Extremely Heavy >= 204.5mm
    assert map_datagov_severity(rainfall_mm=130.0) == 3   # Very Heavy >= 115.6mm
    assert map_datagov_severity(rainfall_mm=75.0) == 2    # Heavy >= 64.5mm
    assert map_datagov_severity(rainfall_mm=20.0) == 1    # Moderate/Light
    assert map_datagov_severity(rainfall_mm=0.0) == 2     # Default fallback when 0


def test_map_datagov_severity_temperature():
    assert map_datagov_severity(temp_c=46.5) == 4   # Extreme Heatwave >= 45°C
    assert map_datagov_severity(temp_c=43.0) == 3   # Severe Heatwave >= 42°C
    assert map_datagov_severity(temp_c=40.5) == 2   # Heatwave >= 40°C
    assert map_datagov_severity(temp_c=32.0) == 1   # Normal temp


def test_map_datagov_severity_wind():
    assert map_datagov_severity(wind_kmph=95.0) == 4  # Extreme Wind >= 90 km/h
    assert map_datagov_severity(wind_kmph=65.0) == 3  # Severe Wind >= 60 km/h
    assert map_datagov_severity(wind_kmph=45.0) == 2  # Strong Wind >= 40 km/h


# ============================================================================
# 3. RECORD PARSING & PROVENANCE TESTS
# ============================================================================

def test_parse_dataset_record_rainfall(datagov_connector, rainfall_resource):
    record = {
        "id": "rec_odisha_001",
        "state": "Odisha",
        "district": "Khordha",
        "station": "Bhubaneswar",
        "latitude": "20.296",
        "longitude": "85.824",
        "date": "2026-10-01",
        "rainfall_mm": "145.8",
        "temp_c": "28.5",
    }

    event = datagov_connector.parse_dataset_record(record, rainfall_resource)

    assert event.source_type == SourceType.GOVERNMENT_DATASET.value
    assert event.suggested_category == WeatherCategory.RAINFALL.value
    assert event.severity == 3  # >= 115.6mm -> Severity 3
    assert event.state == "Odisha"
    assert event.district == "Khordha"
    assert event.latitude == 20.296
    assert event.longitude == 85.824
    assert event.raw_payload["provider"] == "data.gov.in"
    assert event.raw_payload["dataset_name"] == "Daily District Rainfall Report"
    assert event.raw_payload["agency_name"] == "India Meteorological Department / MoES"
    assert event.raw_payload["extracted_metrics"]["rainfall_mm"] == 145.8
    assert event.idempotency_key.startswith("datagov:rainfall-district-daily-v1:")


def test_parse_dataset_record_heatwave(datagov_connector):
    heatwave_res = DataGovResourceConfig(
        resource_id="heatwave-telemetry-v1",
        dataset_name="Real-time Maximum Temperature Observatories",
        agency_name="National Disaster Management Authority",
        category="HEATWAVE",
        location_fields={"state": "state_name", "district": "district_name"},
        observation_fields={"temperature": "max_temp_c"},
    )

    record = {
        "state_name": "Rajasthan",
        "district_name": "Churu",
        "date": "2026-05-25 14:30:00 IST",
        "max_temp_c": "47.2",
    }

    event = datagov_connector.parse_dataset_record(record, heatwave_res)

    assert event.suggested_category == WeatherCategory.HEATWAVE.value
    assert event.severity == 4  # >= 45.0°C -> Severity 4
    assert event.state == "Rajasthan"
    assert event.district == "Churu"
    assert event.raw_payload["agency_name"] == "National Disaster Management Authority"
    assert event.raw_payload["extracted_metrics"]["temperature_c"] == 47.2


def test_parse_dataset_record_custom_mapping(datagov_connector):
    cwc_res = DataGovResourceConfig(
        resource_id="cwc-river-gauge-v1",
        dataset_name="River Basin Water Level & Flood Discharge",
        agency_name="Central Water Commission",
        category="FLOODING",
        location_fields={"state": "STATE_NAME", "district": "DIST_NAME", "lat": "LAT", "lon": "LONG"},
        observation_fields={"rainfall": "RAIN_MM", "condition": "FLOOD_STATUS"},
    )

    record = {
        "STATE_NAME": "Assam",
        "DIST_NAME": "Kamrup Metropolitan",
        "LAT": "26.144",
        "LONG": "91.736",
        "DATE": "2026-08-10",
        "RAIN_MM": "220.5",
        "FLOOD_STATUS": "Above Danger Level (Flooding)",
    }

    event = datagov_connector.parse_dataset_record(record, cwc_res)

    assert event.suggested_category == WeatherCategory.FLOODING.value
    assert event.severity == 4
    assert event.state == "Assam"
    assert event.district == "Kamrup Metropolitan"
    assert event.latitude == 26.144
    assert event.longitude == 91.736


# ============================================================================
# 4. DETERMINISTIC IDEMPOTENCY & NORMALIZATION TESTS
# ============================================================================

def test_datagov_deterministic_idempotency(datagov_connector, rainfall_resource):
    record = {
        "id": "rec_dup_check_01",
        "state": "Maharashtra",
        "district": "Pune",
        "date": "2026-10-01 10:00:00 IST",
        "rainfall_mm": "55.0",
    }

    event1 = datagov_connector.parse_dataset_record(record, rainfall_resource)
    event2 = datagov_connector.parse_dataset_record(record, rainfall_resource)

    assert event1.idempotency_key == event2.idempotency_key
    assert event1.external_id == event2.external_id


@pytest.mark.asyncio
async def test_normalize_datagov_event(datagov_connector, rainfall_resource):
    idempotency_service._memory_cache.clear()

    record = {
        "id": "rec_norm_001",
        "state": "Odisha",
        "district": "Cuttack",
        "latitude": 20.462,
        "longitude": 85.882,
        "date": "2026-10-01T09:00:00+05:30",
        "rainfall_mm": "92.0",
    }

    raw_event = datagov_connector.parse_dataset_record(record, rainfall_resource)
    norm_event = await normalize_raw_event(raw_event)

    assert norm_event.source_type == SourceType.GOVERNMENT_DATASET.value
    assert norm_event.primary_category == WeatherCategory.RAINFALL.value
    assert norm_event.district == "Cuttack"
    assert norm_event.state == "Odisha"
    assert norm_event.tracking_id.startswith("SP-")
    assert norm_event.is_duplicate is False

    # Second normalization of the identical event flags duplicate
    norm_event_2 = await normalize_raw_event(raw_event)
    assert norm_event_2.is_duplicate is True


# ============================================================================
# 5. CONNECTOR HEALTH & ERROR RESILIENCE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_health_check_not_configured():
    conn = DataGovConnector(api_key="", config={"resources": []})
    status = await conn.health_check()
    assert status == ConnectorStatusEnum.NOT_CONFIGURED


@pytest.mark.asyncio
async def test_health_check_healthy(datagov_connector):
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = httpx.Response(status_code=200, json={"records": []})
        datagov_connector.is_running = True
        status = await datagov_connector.health_check()
        assert status == ConnectorStatusEnum.HEALTHY


@pytest.mark.asyncio
async def test_health_check_auth_error(datagov_connector):
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = httpx.Response(status_code=401, json={"message": "Invalid API key"})
        datagov_connector.is_running = True
        status = await datagov_connector.health_check()
        assert status == ConnectorStatusEnum.ERROR


@pytest.mark.asyncio
async def test_health_check_rate_limit(datagov_connector):
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = httpx.Response(status_code=429, json={"message": "Rate limit exceeded"})
        datagov_connector.is_running = True
        status = await datagov_connector.health_check()
        assert status == ConnectorStatusEnum.DEGRADED


# ============================================================================
# 6. POLLING & PAGINATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_poll_pagination(datagov_connector, rainfall_resource):
    page1_records = [
        {"id": f"rec_{i}", "state": "Kerala", "district": "Ernakulam", "rainfall_mm": "35.0", "date": "2026-10-01"}
        for i in range(10)
    ]
    page2_records = [
        {"id": f"rec_{i}", "state": "Kerala", "district": "Wayanad", "rainfall_mm": "72.0", "date": "2026-10-01"}
        for i in range(10, 15)
    ]

    datagov_connector.is_running = True

    with patch("httpx.AsyncClient.get") as mock_get:
        # First poll page 1
        mock_get.return_value = httpx.Response(
            status_code=200,
            json={"records": page1_records, "total": 15, "count": 10, "offset": 0, "limit": 10},
        )
        events_1 = await datagov_connector.poll()
        assert len(events_1) == 10
        assert datagov_connector.resource_offsets[rainfall_resource.resource_id] == 10

        # Second poll page 2
        mock_get.return_value = httpx.Response(
            status_code=200,
            json={"records": page2_records, "total": 15, "count": 5, "offset": 10, "limit": 10},
        )
        events_2 = await datagov_connector.poll()
        assert len(events_2) == 5
        # Offset wraps around to 0 when total reached
        assert datagov_connector.resource_offsets[rainfall_resource.resource_id] == 0


@pytest.mark.asyncio
async def test_poll_handles_malformed_records(datagov_connector):
    datagov_connector.is_running = True
    bad_payload = {
        "total": 2,
        "records": [
            None,
            {"invalid_field": "corrupted"},
            {"state": "Punjab", "district": "Ludhiana", "rainfall_mm": "45.0", "date": "2026-10-01"},
        ],
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = httpx.Response(status_code=200, json=bad_payload)
        events = await datagov_connector.poll()
        assert len(events) >= 1
        assert events[-1].district == "Ludhiana"


@pytest.mark.asyncio
async def test_poll_handles_network_timeout(datagov_connector):
    datagov_connector.is_running = True
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectTimeout("Connection timed out")):
        events = await datagov_connector.poll()
        assert events == []
        assert datagov_connector.consecutive_failures == 1
