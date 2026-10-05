"""
SkyPulse IndianAPI Third-Party Weather Ingestion Connector
==========================================================
Integrates with IndianAPI (https://weather.indianapi.in) REST endpoints for Indian cities.
Collects third-party current weather observations with strict diagnostic classification.

Diagnostic Error Classification:
  - 200 -> LIVE / HEALTHY
  - 401 / 403 -> AUTH_ERROR
  - 404 -> INVALID_ENDPOINT_OR_LOCATION
  - 429 -> RATE_LIMITED
  - 5xx -> UPSTREAM_ERROR
  - timeout -> TIMEOUT
  - connection error -> NETWORK_ERROR
  - invalid JSON -> INVALID_RESPONSE

Source Attribution & Trust Policy:
  - source_type: WEATHER_API
  - source_name: INDIANAPI
  - provider_name: IndianAPI
  - is_official_government: False (Third-Party Meteorological Aggregator)
  - official_organization: False
  - imd_official: False
  - NOT represented as an official IMD direct source.
"""

import asyncio
import hashlib
import json
import logging
import random
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.core.config import settings
from app.models.enums import SourceType, WeatherCategory
from connectors.base import BaseConnector, sanitize_error_message
from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum

logger = logging.getLogger("skypulse.connectors.indianapi")

DEFAULT_INDIANAPI_CITIES = [
    "New Delhi",
    "Mumbai",
    "Kolkata",
    "Chennai",
    "Bengaluru",
    "Hyderabad",
    "Bhubaneswar",
    "Guwahati",
    "Ahmedabad",
    "Jaipur",
    "Patna",
    "Lucknow",
]


def extract_numeric_value(val: Any) -> Optional[float]:
    """Extracts float number from strings with units (e.g. '30°C', '0mm', '12 km/h', '75%')."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, dict):
        # e.g., humidity: {"morning": 75, "evening": 65}
        vals = [v for v in val.values() if isinstance(v, (int, float))]
        if vals:
            return float(sum(vals) / len(vals))
        return None

    s = str(val).strip()
    match = re.search(r"[-+]?\d*\.?\d+", s)
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return None
    return None


def parse_indianapi_city_and_station(city_raw: str) -> Tuple[str, Optional[str]]:
    """Splits city strings like 'Chennai-meenambakkam' into ('Chennai', 'meenambakkam')."""
    if not city_raw:
        return ("Unknown", None)
    parts = city_raw.strip().split("-", 1)
    city = parts[0].strip().title()
    station = parts[1].strip() if len(parts) > 1 else None
    return (city, station)


def map_condition_to_sih_category(
    condition_text: str,
    rainfall_mm: Optional[float] = None,
    temp_c: Optional[float] = None,
    wind_kmph: Optional[float] = None,
) -> str:
    """Maps weather observations and condition text to canonical SIH categories."""
    c = (condition_text or "").lower()

    # 1. Extreme and compound conditions first
    if "thunder" in c or "storm" in c or "lightning" in c:
        return WeatherCategory.THUNDERSTORM.value
    if rainfall_mm is not None and rainfall_mm >= 204.5 or "flood" in c or "inundat" in c:
        return WeatherCategory.FLOODING.value
    if temp_c is not None and temp_c >= 40.0 or "heat" in c or "hot" in c:
        return WeatherCategory.HEATWAVE.value
    if "dust" in c or "sand" in c:
        return WeatherCategory.DUST_STORM.value
    if wind_kmph is not None and wind_kmph >= 45.0 or "wind" in c or "gale" in c or "squall" in c:
        return WeatherCategory.STRONG_WINDS.value
    if "fog" in c or "mist" in c or "haze" in c:
        return WeatherCategory.FOG.value

    # 2. General rainfall
    if rainfall_mm is not None and rainfall_mm > 0 or "rain" in c or "drizzle" in c or "shower" in c:
        return WeatherCategory.RAINFALL.value

    return WeatherCategory.UNKNOWN.value


def infer_indianapi_severity(
    rainfall_mm: Optional[float] = None,
    temp_c: Optional[float] = None,
    wind_kmph: Optional[float] = None,
    category: str = "UNKNOWN",
) -> int:
    """Calculates standard SkyPulse 1-4 severity scale from observed meteorological values."""
    if rainfall_mm is not None:
        if rainfall_mm >= 204.5:
            return 4
        if rainfall_mm >= 115.6:
            return 3
        if rainfall_mm >= 64.5:
            return 2

    if temp_c is not None:
        if temp_c >= 45.0:
            return 4
        if temp_c >= 42.0:
            return 3
        if temp_c >= 40.0:
            return 2

    if wind_kmph is not None:
        if wind_kmph >= 90.0:
            return 4
        if wind_kmph >= 60.0:
            return 3
        if wind_kmph >= 40.0:
            return 2

    return 2 if category != WeatherCategory.UNKNOWN.value else 1


def classify_indianapi_exception(exc: Exception) -> Tuple[str, str]:
    """Classifies client exception into standardized diagnostic category and message."""
    msg = str(exc)
    msg_lower = msg.lower()

    if isinstance(exc, httpx.ConnectError) or "connection refused" in msg_lower:
        return "NETWORK_ERROR", f"TCP connection error to IndianAPI: {msg}"
    if isinstance(exc, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException)):
        return "TIMEOUT", f"Timeout awaiting IndianAPI response: {msg}"
    if isinstance(exc, json.JSONDecodeError):
        return "INVALID_RESPONSE", f"Invalid JSON response from IndianAPI: {msg}"

    return "UPSTREAM_ERROR", sanitize_error_message(msg)


class IndianAPIWeatherConnector(BaseConnector):
    """
    Third-party weather data ingestion connector for IndianAPI (https://weather.indianapi.in).
    Collects city weather observations, applies unit parsing, and produces CanonicalRawEvents
    with explicit third-party provenance.
    """

    def __init__(
        self,
        source_id: str = "00000000-0000-0000-0000-000000000007",
        name: str = "IndianAPI Third-Party Weather Provider",
        source_type: str = SourceType.WEATHER_API.value,
        config: Optional[Dict[str, Any]] = None,
        is_demo: bool = False,
        api_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        target_cities: Optional[List[str]] = None,
        poll_interval_seconds: Optional[int] = None,
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
            or getattr(settings, "INDIANAPI_BASE_URL", "https://weather.indianapi.in")
            or "https://weather.indianapi.in"
        ).rstrip("/")
        self.api_key = (
            api_key
            or self.config.get("api_key")
            or getattr(settings, "INDIANAPI_API_KEY", "")
            or ""
        )
        self.poll_interval = int(
            poll_interval_seconds
            or self.config.get("poll_interval_seconds")
            or getattr(settings, "INDIANAPI_POLL_INTERVAL_SECONDS", 600)
            or 600
        )
        self.timeout_seconds = float(
            self.config.get("timeout_seconds")
            or getattr(settings, "INDIANAPI_TIMEOUT_SECONDS", 10.0)
            or 10.0
        )
        self.max_retries = int(
            self.config.get("max_retries")
            or getattr(settings, "INDIANAPI_MAX_RETRIES", 2)
            or 2
        )
        self.target_cities = (
            target_cities
            or self.config.get("target_cities")
            or self._parse_configured_cities()
            or DEFAULT_INDIANAPI_CITIES
        )
        self._client: Optional[httpx.AsyncClient] = None

        # Assess initial configuration status
        if not self.api_key or not self.api_key.strip():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
        else:
            self.status = ConnectorStatusEnum.DEGRADED  # Marked LIVE only on real success

    def _parse_configured_cities(self) -> List[str]:
        raw = getattr(settings, "INDIANAPI_CITIES", "")
        if isinstance(raw, str) and raw.strip():
            return [c.strip() for c in raw.split(",") if c.strip()]
        if isinstance(raw, list):
            return raw
        return []

    async def start(self) -> None:
        """Initializes HTTP client and sets operational status."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds, connect=5.0),
            headers={
                "User-Agent": "SkyPulse-NationalWeatherAnalytics/1.0 (ThirdPartyIngestion)",
                "Accept": "application/json",
            },
            follow_redirects=True,
        )
        self.is_running = True

        if not self.api_key or not self.api_key.strip():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            logger.info("IndianAPIWeatherConnector started in NOT_CONFIGURED state (missing INDIANAPI_API_KEY).")
        else:
            logger.info("IndianAPIWeatherConnector started with %d target cities.", len(self.target_cities))

    async def stop(self) -> None:
        """Closes HTTP client and stops polling."""
        self.is_running = False
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("IndianAPIWeatherConnector stopped.")

    async def health_check(self) -> ConnectorStatusEnum:
        """Evaluates health of the IndianAPI integration with live diagnostic classification."""
        if not self.api_key or not self.api_key.strip():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return ConnectorStatusEnum.NOT_CONFIGURED

        if not self.is_running:
            return ConnectorStatusEnum.DISABLED

        self.last_attempt_at = datetime.now(timezone.utc)
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds, connect=5.0))
        close_after = self._client is None

        try:
            test_city = self.target_cities[0] if self.target_cities else "New Delhi"
            url = f"{self.api_base_url}/india/weather"
            headers = {"x-api-key": self.api_key}
            params = {"city": test_city}

            resp = await client.get(url, headers=headers, params=params)

            if resp.status_code == 200:
                self.status = ConnectorStatusEnum.LIVE
                self.is_reachable = True
                self.is_authenticated = True
                self.consecutive_failures = 0
                self.last_error_code = None
                self.last_error_message = None
                return ConnectorStatusEnum.LIVE
            elif resp.status_code in (401, 403):
                self.status = ConnectorStatusEnum.AUTH_ERROR
                self.is_reachable = True
                self.is_authenticated = False
                self.record_error(f"IndianAPI authentication error (HTTP {resp.status_code})", "AUTH_ERROR")
                return ConnectorStatusEnum.AUTH_ERROR
            elif resp.status_code == 404:
                self.status = ConnectorStatusEnum.DEGRADED
                self.is_reachable = True
                self.record_error(f"IndianAPI endpoint or test city '{test_city}' not found (HTTP 404)", "INVALID_ENDPOINT_OR_LOCATION")
                return ConnectorStatusEnum.DEGRADED
            elif resp.status_code == 429:
                self.status = ConnectorStatusEnum.RATE_LIMITED
                self.is_reachable = True
                self.record_error("IndianAPI rate limited (HTTP 429)", "RATE_LIMITED")
                return ConnectorStatusEnum.RATE_LIMITED
            elif resp.status_code >= 500:
                self.status = ConnectorStatusEnum.DEGRADED
                self.is_reachable = True
                # Upstream server error (e.g. 500 list index out of range)
                self.record_error(f"IndianAPI upstream error (HTTP {resp.status_code}): {sanitize_error_message(resp.text)}", "UPSTREAM_ERROR")
                return ConnectorStatusEnum.DEGRADED
            else:
                self.status = ConnectorStatusEnum.DEGRADED
                self.record_error(f"IndianAPI unexpected status (HTTP {resp.status_code})", f"HTTP_{resp.status_code}")
                return ConnectorStatusEnum.DEGRADED

        except Exception as exc:
            err_code, err_reason = classify_indianapi_exception(exc)
            self.is_reachable = False
            self.status = ConnectorStatusEnum.DEGRADED
            self.record_error(err_reason, err_code)
            return ConnectorStatusEnum.DEGRADED
        finally:
            if close_after:
                await client.aclose()

    async def poll(self) -> List[CanonicalRawEvent]:
        """Polls IndianAPI current weather observations across target cities with bounded retries."""
        if not self.is_running or not self.api_key or not self.api_key.strip():
            return []

        events: List[CanonicalRawEvent] = []
        t0 = time.time()
        self.last_attempt_at = datetime.now(timezone.utc)
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds, connect=5.0))

        for city in self.target_cities:
            url = f"{self.api_base_url}/india/weather"
            headers = {"x-api-key": self.api_key}
            params = {"city": city}

            resp = None
            last_exc = None

            for attempt in range(self.max_retries + 1):
                try:
                    resp = await client.get(url, headers=headers, params=params)
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < self.max_retries:
                        jitter = random.uniform(0.1, 0.4)
                        backoff = (0.4 * (2 ** attempt)) + jitter
                        await asyncio.sleep(backoff)

            if resp is None:
                err_code, err_reason = classify_indianapi_exception(last_exc)
                self.record_error(f"Failed querying city '{city}': {err_reason}", err_code)
                continue

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    event = self.parse(data, requested_city=city)
                    if event:
                        events.append(event)
                    self.status = ConnectorStatusEnum.LIVE
                    self.is_reachable = True
                    self.is_authenticated = True
                except Exception as json_err:
                    self.record_error(f"Invalid JSON from IndianAPI for '{city}': {json_err}", "INVALID_RESPONSE")

            elif resp.status_code == 429:
                self.status = ConnectorStatusEnum.RATE_LIMITED
                self.record_error("IndianAPI rate limit exceeded (HTTP 429)", "RATE_LIMITED")
                break  # Politeness: halt current cycle

            elif resp.status_code in (401, 403):
                self.status = ConnectorStatusEnum.AUTH_ERROR
                self.is_authenticated = False
                self.record_error(f"IndianAPI authentication failure (HTTP {resp.status_code})", "AUTH_ERROR")
                break

            elif resp.status_code == 404:
                logger.debug("City '%s' not found in IndianAPI index (HTTP 404)", city)

            elif resp.status_code >= 500:
                self.status = ConnectorStatusEnum.DEGRADED
                self.record_error(f"IndianAPI upstream error (HTTP {resp.status_code}) for city '{city}'", "UPSTREAM_ERROR")

            else:
                self.record_error(f"IndianAPI returned HTTP {resp.status_code} for city '{city}'", f"HTTP_{resp.status_code}")

        latency_ms = (time.time() - t0) * 1000
        if events:
            self.record_success(count=len(events), latency_ms=latency_ms)

        return events

    def parse(self, raw_data: Any, requested_city: Optional[str] = None) -> CanonicalRawEvent:
        """
        Parses IndianAPI JSON payload into a typed CanonicalRawEvent.
        Preserves strict third-party source trust rules.
        """
        if not isinstance(raw_data, dict):
            raw_data = {"raw": str(raw_data)}

        # Handle nested weather object vs flat object
        weather_obj = raw_data.get("weather", {}) if isinstance(raw_data.get("weather"), dict) else {}
        current_obj = weather_obj.get("current", {}) if isinstance(weather_obj.get("current"), dict) else {}

        # 1. City & Station Extraction
        city_raw = raw_data.get("city") or raw_data.get("location") or requested_city or "Unknown"
        city_name, station_name = parse_indianapi_city_and_station(str(city_raw))
        state = raw_data.get("state") or raw_data.get("region")

        # 2. Observation Metrics Extraction
        temp_val = extract_numeric_value(current_obj.get("temperature") or raw_data.get("temperature") or raw_data.get("temp_c"))
        humidity_val = extract_numeric_value(current_obj.get("humidity") or raw_data.get("humidity") or raw_data.get("humidity_pct"))
        rainfall_val = extract_numeric_value(current_obj.get("rainfall") or raw_data.get("rainfall") or raw_data.get("precip_mm"))
        wind_val = extract_numeric_value(current_obj.get("wind_speed") or current_obj.get("wind") or raw_data.get("wind_speed") or raw_data.get("wind_kph"))
        wind_dir = current_obj.get("wind_direction") or raw_data.get("wind_direction") or raw_data.get("wind_dir")

        condition_desc = (
            current_obj.get("description")
            or current_obj.get("condition")
            or raw_data.get("description")
            or raw_data.get("condition")
            or ""
        )

        # 3. Categorization & Severity
        category = map_condition_to_sih_category(
            condition_text=condition_desc,
            rainfall_mm=rainfall_val,
            temp_c=temp_val,
            wind_kmph=wind_val,
        )
        severity = infer_indianapi_severity(
            rainfall_mm=rainfall_val,
            temp_c=temp_val,
            wind_kmph=wind_val,
            category=category,
        )

        # 4. Timestamp Extraction
        now_utc = datetime.now(timezone.utc)
        time_bucket = now_utc.strftime("%Y%m%d%H")
        city_slug = re.sub(r"[^a-zA-Z0-9]+", "_", city_name.lower()).strip("_")

        # 5. Descriptive Text (Strictly third-party provenance statement)
        text_parts = [f"IndianAPI weather data for {city_name}"]
        if station_name:
            text_parts.append(f"[{station_name} station]")
        text_parts.append(f": {condition_desc or 'Current observations'}.")
        if temp_val is not None:
            text_parts.append(f"Temperature: {temp_val}°C.")
        if humidity_val is not None:
            text_parts.append(f"Humidity: {humidity_val}%.")
        if rainfall_val is not None:
            text_parts.append(f"Rainfall: {rainfall_val} mm.")
        if wind_val is not None:
            text_parts.append(f"Wind Speed: {wind_val} km/h.")
        if wind_dir:
            text_parts.append(f"Wind Direction: {wind_dir}.")

        descriptive_text = " ".join(text_parts)

        # 6. Idempotency Key
        hash_input = f"indianapi:{city_slug}:{time_bucket}:{category}:{temp_val}:{rainfall_val}"
        idempotency_key = f"indianapi:{city_slug}:{hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:16]}"
        external_id = f"indianapi_{city_slug}_{time_bucket}"

        # 7. Complete Provenance Metadata Payload
        raw_payload = {
            "provider": "IndianAPI",
            "provider_name": "IndianAPI",
            "source_type": SourceType.WEATHER_API.value,
            "source_name": "INDIANAPI",
            "is_official_government": False,
            "official_organization": False,
            "imd_official": False,
            "license": "Third-Party Developer API (https://indianapi.in/weather-api)",
            "endpoint": "/india/weather",
            "city": city_name,
            "station": station_name,
            "state": state,
            "fields": raw_data,
            "extracted_metrics": {
                "temperature_c": temp_val,
                "humidity_pct": humidity_val,
                "rainfall_mm": rainfall_val,
                "wind_speed_kmph": wind_val,
                "wind_direction": wind_dir,
                "condition": condition_desc,
            },
        }

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type=SourceType.WEATHER_API.value,
            external_id=external_id,
            text=descriptive_text,
            suggested_category=category,
            severity=severity,
            latitude=None,  # Zero fake GPS
            longitude=None,  # Zero fake GPS
            city=city_name,
            district=city_name,
            state=state,
            observed_at=now_utc,
            ingested_at=now_utc,
            raw_payload=raw_payload,
            is_demo=self.is_demo,
            idempotency_key=idempotency_key,
        )


# Singleton instance for orchestrator registration
indianapi_weather_connector = IndianAPIWeatherConnector()
