"""
SkyPulse Open Government Data (data.gov.in) Ingestion Connector
================================================================
Connects to official Open Government Data (OGD) Platform India (data.gov.in),
ingesting published government meteorological, hydrological, and disaster dataset
resources into the SkyPulse canonical streaming pipeline.

Diagnostic Error Classification:
  - DNS_FAILURE: Hostname resolution failure
  - TCP_CONNECTION_FAILURE: TCP connection refused / RST / unreachable
  - TLS_FAILURE: SSL/TLS handshake or certificate error
  - HTTP_401 / AUTH_ERROR: Missing or invalid API key
  - HTTP_403 / ACCESS_DENIED: Key unauthorized for resource
  - HTTP_404 / RESOURCE_NOT_FOUND: Resource ID does not exist or expired
  - HTTP_429 / RATE_LIMITED: OGD gateway throttling
  - HTTP_5XX / UPSTREAM_SERVER_ERROR: data.gov.in internal gateway/server error
  - MALFORMED_RESPONSE / INVALID_JSON: Non-JSON or schema mismatch
  - TIMEOUT: Connection or read timeout
  - UPSTREAM_MAINTENANCE: Gateway down for scheduled maintenance

Source Attribution:
  - source_type: GOVERNMENT_DATASET
  - provider: data.gov.in
  - agency_name: Dataset-specific Indian government agency (e.g. MoES, CWC, NDMA, CPCB)
  - high-trust published government dataset provenance
"""

import asyncio
import hashlib
import json
import logging
import random
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
import httpx
from pydantic import BaseModel, Field

from app.core.config import settings
from app.models.enums import SourceType, WeatherCategory
from connectors.base import BaseConnector, sanitize_error_message
from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum

logger = logging.getLogger("skypulse.connectors.datagov")

IST_TIMEZONE = timezone(timedelta(hours=5, minutes=30))

DEFAULT_DATA_GOV_RESOURCES: List[Dict[str, Any]] = [
    {
        "resource_id": "950b0e55-e452-49e3-8026-79174f63c621",
        "dataset_name": "IMD Daily Weather Observations & Rainfall",
        "agency_name": "India Meteorological Department (MoES)",
        "category": "RAINFALL",
        "poll_interval_seconds": 600,
        "limit": 100,
        "enabled": True,
        "timestamp_field": "date",
        "location_fields": {
            "state": "state",
            "district": "district",
            "station": "station",
            "lat": "latitude",
            "lon": "longitude",
        },
        "observation_fields": {
            "rainfall": "rainfall_mm",
            "temperature": "temperature_c",
            "humidity": "humidity_pct",
            "wind_speed": "wind_speed_kmph",
        },
    },
    {
        "resource_id": "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69",
        "dataset_name": "National River Basin Water Levels & Flood Bulletins",
        "agency_name": "Central Water Commission (CWC)",
        "category": "FLOODING",
        "poll_interval_seconds": 600,
        "limit": 50,
        "enabled": True,
        "timestamp_field": "bulletin_date",
        "location_fields": {
            "state": "state",
            "district": "district",
            "station": "site_name",
        },
        "observation_fields": {
            "rainfall": "warning_level_rainfall",
        },
    },
]


class DataGovResourceConfig(BaseModel):
    """Configuration definition for an individual data.gov.in dataset resource."""
    resource_id: str
    dataset_name: str = "Government Weather Dataset"
    agency_name: str = "Government of India (data.gov.in)"
    category: Optional[str] = None
    endpoint: Optional[str] = None
    poll_interval_seconds: int = 600
    limit: int = 100
    enabled: bool = True
    timestamp_field: Optional[str] = None
    location_fields: Dict[str, str] = Field(default_factory=dict)
    observation_fields: Dict[str, str] = Field(default_factory=dict)


def parse_datagov_timestamp(ts_val: Any) -> datetime:
    """
    Parses various data.gov.in timestamp and date formats to timezone-aware UTC datetime.
    Supports ISO 8601, epoch timestamps, IST strings, and Indian date formats (DD-MM-YYYY, DD/MM/YYYY).
    """
    if not ts_val:
        return datetime.now(timezone.utc)

    if isinstance(ts_val, datetime):
        if ts_val.tzinfo is None:
            return ts_val.replace(tzinfo=timezone.utc)
        return ts_val.astimezone(timezone.utc)

    if isinstance(ts_val, (int, float)):
        if ts_val > 1e11:  # milliseconds
            ts_val = ts_val / 1000.0
        return datetime.fromtimestamp(ts_val, tz=timezone.utc)

    s = str(ts_val).strip()
    is_ist = False
    if "IST" in s:
        is_ist = True
        s = s.replace("IST", "").strip()

    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%b-%Y",
        "%d-%B-%Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(s.replace("Z", "+0000"), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IST_TIMEZONE if is_ist else timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue

    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST_TIMEZONE if is_ist else timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    return datetime.now(timezone.utc)


def map_datagov_severity(
    rainfall_mm: Optional[float] = None,
    temp_c: Optional[float] = None,
    wind_kmph: Optional[float] = None,
    default_severity: int = 2,
) -> int:
    """
    Computes standard SkyPulse 1-4 severity scale from observed meteorological values:
      - Rainfall: >=204.5mm (4), >=115.6mm (3), >=64.5mm (2), <64.5mm (1)
      - Temperature: >=45.0°C (4), >=42.0°C (3), >=40.0°C (2), <40°C (1)
      - Wind speed: >=90 km/h (4), >=60 km/h (3), >=40 km/h (2), <40 km/h (1)
    """
    severities = []
    if rainfall_mm is not None:
        if rainfall_mm >= 204.5:
            severities.append(4)
        elif rainfall_mm >= 115.6:
            severities.append(3)
        elif rainfall_mm >= 64.5:
            severities.append(2)
        elif rainfall_mm > 0:
            severities.append(1)

    if temp_c is not None:
        if temp_c >= 45.0:
            severities.append(4)
        elif temp_c >= 42.0:
            severities.append(3)
        elif temp_c >= 40.0:
            severities.append(2)
        elif temp_c > 0:
            severities.append(1)

    if wind_kmph is not None:
        if wind_kmph >= 90.0:
            severities.append(4)
        elif wind_kmph >= 60.0:
            severities.append(3)
        elif wind_kmph >= 40.0:
            severities.append(2)
        elif wind_kmph > 0:
            severities.append(1)

    return max(severities) if severities else default_severity


def classify_datagov_exception(exc: Exception) -> Tuple[str, str]:
    """
    Determines exact diagnostic failure category and human-readable sanitized reason.
    """
    msg = str(exc)
    msg_lower = msg.lower()

    if isinstance(exc, httpx.ConnectError) or "10061" in msg or "connection refused" in msg_lower:
        return "TCP_CONNECTION_FAILURE", f"TCP connection refused by upstream host api.data.gov.in: {msg}"
    if isinstance(exc, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException)) or "timed out" in msg_lower:
        return "TIMEOUT", f"Connection timed out waiting for api.data.gov.in: {msg}"
    if "getaddrinfo failed" in msg_lower or "name resolution" in msg_lower or "dns" in msg_lower:
        return "DNS_FAILURE", f"DNS resolution failed for api.data.gov.in: {msg}"
    if "ssl" in msg_lower or "certificate" in msg_lower or "handshake" in msg_lower:
        return "TLS_FAILURE", f"TLS/SSL handshake failure connecting to api.data.gov.in: {msg}"
    if isinstance(exc, json.JSONDecodeError) or "invalid json" in msg_lower:
        return "MALFORMED_RESPONSE", f"Malformed or non-JSON response from data.gov.in: {msg}"

    return "UPSTREAM_ERROR", sanitize_error_message(msg)


class DataGovConnector(BaseConnector):
    """
    Official Open Government Data (data.gov.in) ingestion connector.
    Supports polling multiple configurable OGD datasets with pagination,
    schema extraction, deterministic idempotency, and provenance preservation.
    """

    def __init__(
        self,
        source_id: str = "00000000-0000-0000-0000-000000000002",
        name: str = "Open Government Data (data.gov.in)",
        source_type: str = SourceType.GOVERNMENT_DATASET.value,
        config: Optional[Dict[str, Any]] = None,
        is_demo: bool = False,
        api_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        super().__init__(
            source_id=source_id,
            name=name,
            source_type=source_type,
            config=config or {},
            is_demo=is_demo,
        )
        self.api_base_url = (
            api_base_url
            or self.config.get("api_base_url")
            or getattr(settings, "DATA_GOV_API_BASE_URL", "https://api.data.gov.in")
            or "https://api.data.gov.in"
        ).rstrip("/")
        self.api_key = (
            api_key
            or self.config.get("api_key")
            or getattr(settings, "DATA_GOV_API_KEY", "")
            or ""
        )
        self.poll_interval = int(
            self.config.get("poll_interval_seconds")
            or getattr(settings, "DATA_GOV_POLL_INTERVAL_SECONDS", 600)
            or 600
        )
        self.timeout_seconds = float(
            self.config.get("timeout_seconds")
            or getattr(settings, "DATA_GOV_TIMEOUT_SECONDS", 10.0)
            or 10.0
        )
        self.max_retries = int(
            self.config.get("max_retries")
            or getattr(settings, "DATA_GOV_MAX_RETRIES", 2)
            or 2
        )

        # Resource definitions registry
        self.resources: List[DataGovResourceConfig] = self._init_resources()
        self.resource_offsets: Dict[str, int] = {r.resource_id: 0 for r in self.resources}
        self.is_data_valid: bool = False
        self._client: Optional[httpx.AsyncClient] = None

        # Check configuration
        if not self.api_key or not self.resources:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
        else:
            # Not marked healthy until verified by a live request
            self.status = ConnectorStatusEnum.UNAVAILABLE

    def _init_resources(self) -> List[DataGovResourceConfig]:
        """Loads resource configurations from connector config, settings, or verified defaults."""
        raw_resources = self.config.get("resources") or getattr(settings, "DATA_GOV_RESOURCES", "")
        if isinstance(raw_resources, str) and raw_resources.strip():
            try:
                raw_resources = json.loads(raw_resources)
            except Exception as e:
                logger.warning("Failed to parse DATA_GOV_RESOURCES JSON: %s", e)
                raw_resources = []

        if isinstance(raw_resources, list) and raw_resources:
            parsed = []
            for item in raw_resources:
                if isinstance(item, dict) and item.get("resource_id"):
                    parsed.append(DataGovResourceConfig(**item))
            if parsed:
                return parsed

        # Fallback to standard verified meteorological resources
        return [DataGovResourceConfig(**r) for r in DEFAULT_DATA_GOV_RESOURCES]

    async def start(self) -> None:
        """Initializes HTTP client with short connection timeouts."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds, connect=5.0),
            headers={"User-Agent": "SkyPulse-NationalWeatherAnalytics/1.0 (GovernmentDataConnector)"},
            follow_redirects=True,
        )
        self.is_running = True

        if not self.api_key or not self.resources:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            logger.info("DataGovConnector initialized in NOT_CONFIGURED state (missing API key or resources).")
        else:
            logger.info("DataGovConnector started with %d configured resource(s).", len(self.resources))

    async def stop(self) -> None:
        """Gracefully closes HTTP client and shuts down connector."""
        self.is_running = False
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("DataGovConnector stopped.")

    async def health_check(self) -> ConnectorStatusEnum:
        """Evaluates health of the data.gov.in integration via a live bounded probe."""
        if not self.api_key or not self.resources:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return ConnectorStatusEnum.NOT_CONFIGURED

        if not self.is_running:
            return ConnectorStatusEnum.DISABLED

        self.last_attempt_at = datetime.now(timezone.utc)
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds, connect=5.0))
        close_after = self._client is None

        try:
            test_res = self.resources[0].resource_id if self.resources else "ping"
            url = f"{self.api_base_url}/resource/{test_res}"
            params = {"api-key": self.api_key, "format": "json", "limit": 1}

            resp = await client.get(url, params=params)

            if resp.status_code == 200:
                self.status = ConnectorStatusEnum.LIVE
                self.is_reachable = True
                self.is_authenticated = True
                self.is_data_valid = True
                self.consecutive_failures = 0
                self.last_error_code = None
                self.last_error_message = None
                return ConnectorStatusEnum.LIVE
            elif resp.status_code in (401, 403):
                self.status = ConnectorStatusEnum.AUTH_ERROR
                self.is_reachable = True
                self.is_authenticated = False
                self.record_error(f"data.gov.in authentication rejected (HTTP {resp.status_code})", "AUTH_ERROR")
                return ConnectorStatusEnum.AUTH_ERROR
            elif resp.status_code == 404:
                self.status = ConnectorStatusEnum.DEGRADED
                self.is_reachable = True
                self.record_error(f"Configured resource ID '{test_res}' not found (HTTP 404)", "INVALID_RESOURCE_ID")
                return ConnectorStatusEnum.DEGRADED
            elif resp.status_code == 429:
                self.status = ConnectorStatusEnum.RATE_LIMITED
                self.is_reachable = True
                self.record_error("data.gov.in rate limit exceeded (HTTP 429)", "RATE_LIMITED")
                return ConnectorStatusEnum.RATE_LIMITED
            elif resp.status_code >= 500:
                self.status = ConnectorStatusEnum.DEGRADED
                self.is_reachable = True
                self.record_error(f"data.gov.in gateway error (HTTP {resp.status_code})", "HTTP_5XX")
                return ConnectorStatusEnum.DEGRADED
            else:
                self.status = ConnectorStatusEnum.DEGRADED
                self.record_error(f"data.gov.in returned unexpected HTTP {resp.status_code}", "UNEXPECTED_STATUS")
                return ConnectorStatusEnum.DEGRADED

        except Exception as exc:
            err_code, err_reason = classify_datagov_exception(exc)
            self.is_reachable = False
            self.status = ConnectorStatusEnum.UNAVAILABLE
            self.record_error(err_reason, err_code)
            return ConnectorStatusEnum.UNAVAILABLE
        finally:
            if close_after:
                await client.aclose()

    async def poll(self) -> List[CanonicalRawEvent]:
        """
        Polls configured data.gov.in resources with bounded retries, exponential backoff, and jitter.
        Never blocks the worker indefinitely if data.gov.in is unreachable.
        """
        if not self.is_running or not self.api_key or not self.resources:
            return []

        events: List[CanonicalRawEvent] = []
        t0 = time.time()
        self.last_attempt_at = datetime.now(timezone.utc)
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds, connect=5.0))

        for resource in self.resources:
            if not resource.enabled:
                continue

            offset = self.resource_offsets.get(resource.resource_id, 0)
            url = resource.endpoint or f"{self.api_base_url}/resource/{resource.resource_id}"
            params = {
                "api-key": self.api_key,
                "format": "json",
                "offset": offset,
                "limit": resource.limit,
            }

            resp = None
            last_exc = None

            # Bounded retry loop with exponential backoff & jitter
            for attempt in range(self.max_retries + 1):
                try:
                    resp = await client.get(url, params=params)
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < self.max_retries:
                        jitter = random.uniform(0.1, 0.5)
                        backoff = (0.5 * (2 ** attempt)) + jitter
                        await asyncio.sleep(backoff)

            if resp is None:
                err_code, err_reason = classify_datagov_exception(last_exc)
                self.is_reachable = False
                self.status = ConnectorStatusEnum.UNAVAILABLE
                self.record_error(err_reason, err_code)
                # Continue pipeline for remaining connectors without crashing
                continue

            # Process HTTP response
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception as json_err:
                    self.record_error(f"Malformed JSON response: {json_err}", "MALFORMED_RESPONSE")
                    continue

                records = data.get("records") or []
                total = int(data.get("total") or 0)
                self.is_reachable = True
                self.is_authenticated = True
                self.is_data_valid = True
                self.status = ConnectorStatusEnum.LIVE

                for rec in records:
                    if not isinstance(rec, dict):
                        continue
                    try:
                        parsed_event = self.parse_dataset_record(rec, resource)
                        if parsed_event:
                            events.append(parsed_event)
                    except Exception as parse_err:
                        logger.error("Failed to parse data.gov.in record in resource %s: %s", resource.resource_id, parse_err)

                # Update pagination offset
                new_offset = offset + len(records)
                if total > 0 and new_offset >= total:
                    new_offset = 0  # Wrap around for periodic fresh polling
                self.resource_offsets[resource.resource_id] = new_offset

                self.record_success(count=len(records), latency_ms=(time.time() - t0) * 1000)

            elif resp.status_code == 429:
                self.status = ConnectorStatusEnum.RATE_LIMITED
                self.record_error("data.gov.in rate limit exceeded (HTTP 429)", "RATE_LIMITED")
                break  # Politeness: stop current polling cycle

            elif resp.status_code in (401, 403):
                self.status = ConnectorStatusEnum.AUTH_ERROR
                self.is_authenticated = False
                self.record_error(f"data.gov.in authentication failure (HTTP {resp.status_code})", "AUTH_ERROR")

            elif resp.status_code == 404:
                self.record_error(f"Resource {resource.resource_id} not found (HTTP 404)", "INVALID_RESOURCE_ID")

            else:
                self.status = ConnectorStatusEnum.DEGRADED
                self.record_error(f"data.gov.in API returned HTTP {resp.status_code}", f"HTTP_{resp.status_code}")

        return events

    def parse(self, raw_data: Any) -> CanonicalRawEvent:
        """Default parser delegating to generic record parser."""
        default_res = self.resources[0] if self.resources else DataGovResourceConfig(resource_id="generic_ogd")
        return self.parse_dataset_record(raw_data, default_res)

    def parse_dataset_record(
        self,
        record: Dict[str, Any],
        resource: DataGovResourceConfig,
    ) -> CanonicalRawEvent:
        """
        Extracts location, timestamp, and weather measurements from an OGD dataset record,
        generating a CanonicalRawEvent with complete government dataset provenance.
        """
        loc_map = resource.location_fields
        obs_map = resource.observation_fields

        # 1. Location Extraction
        state = (
            record.get(loc_map.get("state", "state"))
            or record.get("State")
            or record.get("STATE")
            or record.get("state_name")
            or record.get("State_Name")
        )
        district = (
            record.get(loc_map.get("district", "district"))
            or record.get("District")
            or record.get("DISTRICT")
            or record.get("district_name")
            or record.get("District_Name")
        )
        city = (
            record.get(loc_map.get("city", "city"))
            or record.get("City")
            or record.get("CITY")
            or record.get("city_name")
        )
        station = (
            record.get(loc_map.get("station", "station"))
            or record.get("Station")
            or record.get("STATION")
            or record.get("station_name")
        )

        lat_raw = record.get(loc_map.get("lat", "latitude")) or record.get("lat") or record.get("latitude") or record.get("Latitude")
        lon_raw = record.get(loc_map.get("lon", "longitude")) or record.get("lon") or record.get("longitude") or record.get("Longitude")

        lat: Optional[float] = None
        lon: Optional[float] = None
        if lat_raw is not None:
            try:
                lat = float(lat_raw)
            except (ValueError, TypeError):
                lat = None
        if lon_raw is not None:
            try:
                lon = float(lon_raw)
            except (ValueError, TypeError):
                lon = None

        # 2. Timestamp Extraction
        ts_field = resource.timestamp_field
        ts_val = None
        if ts_field and ts_field in record:
            ts_val = record[ts_field]
        else:
            for candidate in ["date", "Date", "DATE", "timestamp", "Timestamp", "datetime", "observation_date", "record_date"]:
                if candidate in record:
                    ts_val = record[candidate]
                    break

        observed_at = parse_datagov_timestamp(ts_val)

        # 3. Observation Metrics Extraction
        rainfall_val = None
        for r_key in [obs_map.get("rainfall", "rainfall_mm"), "rainfall_mm", "rainfall", "Rainfall", "actual_rainfall", "actual_rainfall_mm", "rainfall_actual"]:
            if r_key in record and record[r_key] is not None and str(record[r_key]).strip() != "":
                try:
                    rainfall_val = float(str(record[r_key]).strip())
                    break
                except (ValueError, TypeError):
                    pass

        temp_val = None
        for t_key in [obs_map.get("temperature", "temperature_c"), "temperature_c", "temp_c", "temperature", "Temperature", "temp_max", "max_temp"]:
            if t_key in record and record[t_key] is not None and str(record[t_key]).strip() != "":
                try:
                    temp_val = float(str(record[t_key]).strip())
                    break
                except (ValueError, TypeError):
                    pass

        humidity_val = None
        for h_key in [obs_map.get("humidity", "humidity_pct"), "humidity_pct", "humidity", "Humidity", "rh"]:
            if h_key in record and record[h_key] is not None and str(record[h_key]).strip() != "":
                try:
                    humidity_val = float(str(record[h_key]).strip())
                    break
                except (ValueError, TypeError):
                    pass

        wind_val = None
        for w_key in [obs_map.get("wind_speed", "wind_speed_kmph"), "wind_speed_kmph", "wind_speed", "wind_speed_km_h"]:
            if w_key in record and record[w_key] is not None and str(record[w_key]).strip() != "":
                try:
                    wind_val = float(str(record[w_key]).strip())
                    break
                except (ValueError, TypeError):
                    pass

        condition_str = (
            record.get(obs_map.get("condition", "condition"))
            or record.get("weather_condition")
            or record.get("condition")
            or record.get("Weather_Condition")
            or ""
        )

        # 4. Category Classification
        if resource.category:
            category = resource.category.upper()
        elif rainfall_val is not None and rainfall_val > 0:
            category = WeatherCategory.FLOODING.value if rainfall_val >= 204.5 else WeatherCategory.RAINFALL.value
        elif temp_val is not None and temp_val >= 40.0:
            category = WeatherCategory.HEATWAVE.value
        elif wind_val is not None and wind_val >= 50.0:
            category = WeatherCategory.STRONG_WINDS.value
        elif "fog" in condition_str.lower():
            category = WeatherCategory.FOG.value
        elif "thunder" in condition_str.lower():
            category = WeatherCategory.THUNDERSTORM.value
        elif "dust" in condition_str.lower():
            category = WeatherCategory.DUST_STORM.value
        else:
            category = WeatherCategory.UNKNOWN.value

        # 5. Severity Calculation
        severity = map_datagov_severity(
            rainfall_mm=rainfall_val,
            temp_c=temp_val,
            wind_kmph=wind_val,
            default_severity=2 if category != WeatherCategory.UNKNOWN.value else 1,
        )

        # 6. Stable Record Identity & Idempotency Key
        record_id = (
            record.get("id")
            or record.get("_id")
            or record.get("record_id")
            or f"{state}_{district}_{station}_{observed_at.strftime('%Y%m%d%H%M')}"
        )
        time_bucket = observed_at.strftime("%Y%m%d%H")
        hash_input = f"datagov:{resource.resource_id}:{record_id}:{time_bucket}"
        idempotency_key = f"datagov:{resource.resource_id}:{hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:16]}"

        # 7. Descriptive Text
        loc_desc = district or state or city or "National Monitoring Point"
        text_parts = [f"Official Government Dataset Report: {resource.dataset_name} for {loc_desc}."]
        if rainfall_val is not None:
            text_parts.append(f"Precipitation: {rainfall_val} mm.")
        if temp_val is not None:
            text_parts.append(f"Temperature: {temp_val} °C.")
        if humidity_val is not None:
            text_parts.append(f"Relative Humidity: {humidity_val}%.")
        if wind_val is not None:
            text_parts.append(f"Wind: {wind_val} km/h.")
        if condition_str:
            text_parts.append(f"Condition: {condition_str}.")

        descriptive_text = " ".join(text_parts)

        # 8. Full Provenance Metadata Payload
        raw_payload = {
            "provider": "data.gov.in",
            "source_type": SourceType.GOVERNMENT_DATASET.value,
            "dataset_name": resource.dataset_name,
            "agency_name": resource.agency_name,
            "resource_id": resource.resource_id,
            "source_url": f"{self.api_base_url}/resource/{resource.resource_id}",
            "fields": record,
            "extracted_metrics": {
                "rainfall_mm": rainfall_val,
                "temperature_c": temp_val,
                "humidity_pct": humidity_val,
                "wind_speed_kmph": wind_val,
                "condition": condition_str,
            },
        }

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type=SourceType.GOVERNMENT_DATASET.value,
            external_id=f"datagov_{resource.resource_id}_{record_id}",
            text=descriptive_text,
            suggested_category=category,
            severity=severity,
            latitude=lat,
            longitude=lon,
            city=city,
            district=district,
            state=state,
            observed_at=observed_at,
            ingested_at=datetime.now(timezone.utc),
            raw_payload=raw_payload,
            is_demo=self.is_demo,
            idempotency_key=idempotency_key,
        )

    def get_admin_health_status(self) -> Dict[str, Any]:
        """
        Exposes the exact admin/source-health indication for DATA_GOV required by Phase 1:
          CONFIGURED, AUTHENTICATED, REACHABLE, DATA_VALID, LAST_SUCCESS, LAST_FAILURE, FAILURE_REASON
        """
        return {
            "CONFIGURED": bool(self.api_key and self.resources),
            "AUTHENTICATED": self.is_authenticated,
            "REACHABLE": self.is_reachable,
            "DATA_VALID": self.is_data_valid,
            "LAST_SUCCESS": self.metrics.last_successful_fetch.isoformat() if self.metrics.last_successful_fetch else None,
            "LAST_FAILURE": self.last_attempt_at.isoformat() if self.consecutive_failures > 0 and self.last_attempt_at else None,
            "FAILURE_REASON": self.last_error_message,
        }
