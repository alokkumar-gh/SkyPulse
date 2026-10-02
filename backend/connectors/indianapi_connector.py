"""
SkyPulse IndianAPI Third-Party Weather Ingestion Connector
==========================================================
Integrates with IndianAPI (https://weather.indianapi.in) REST endpoints for Indian cities.
Collects third-party current weather observations and forecasts.

Source Attribution:
  - source_type: WEATHER_API
  - provider: IndianAPI
  - is_official_government: False (Third-Party Meteorological Aggregator)
  - license: Commercial / Free-Tier Developer API
"""

import re
import time
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
import httpx

from connectors.base import BaseConnector
from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum
from app.core.config import settings
from app.models.enums import WeatherCategory, SourceType

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


def parse_indianapi_city_and_station(city_raw: str) -> tuple[str, Optional[str]]:
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
    """Maps weather observations and condition text to the 7 canonical SIH categories."""
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


class IndianAPIWeatherConnector(BaseConnector):
    """
    Third-party weather data ingestion connector for IndianAPI (https://weather.indianapi.in).
    Collects city weather observations, applies unit parsing, and produces CanonicalRawEvents
    with explicit third-party provenance.
    """

    def __init__(
        self,
        source_id: str = "00000000-0000-0000-0000-000000000007",
        name: str = "IndianAPI Weather Connector",
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
        )
        self.target_cities = (
            target_cities
            or self.config.get("target_cities")
            or self._parse_configured_cities()
            or DEFAULT_INDIANAPI_CITIES
        )
        self.consecutive_failures = 0
        self._client: Optional[httpx.AsyncClient] = None

        # Assess initial configuration status
        if not self.api_key or not self.api_key.strip():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
        else:
            self.status = ConnectorStatusEnum.HEALTHY

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
            timeout=httpx.Timeout(15.0, connect=8.0),
            headers={
                "User-Agent": "SkyPulse-NationalWeatherBigDataAnalytics/1.0 (ThirdPartyIngestion)",
                "Accept": "application/json",
            },
            follow_redirects=True,
        )
        self.is_running = True

        if not self.api_key or not self.api_key.strip():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            logger.info("IndianAPIWeatherConnector started in NOT_CONFIGURED state (missing INDIANAPI_API_KEY).")
        else:
            self.status = ConnectorStatusEnum.HEALTHY
            logger.info("IndianAPIWeatherConnector started with %d target cities.", len(self.target_cities))

    async def stop(self) -> None:
        """Closes HTTP client and stops polling."""
        self.is_running = False
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("IndianAPIWeatherConnector stopped.")

    async def health_check(self) -> ConnectorStatusEnum:
        """Evaluates health of the IndianAPI integration."""
        if not self.api_key or not self.api_key.strip():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return ConnectorStatusEnum.NOT_CONFIGURED

        if not self.is_running:
            return ConnectorStatusEnum.DISABLED

        if self.consecutive_failures >= 3:
            self.status = ConnectorStatusEnum.ERROR
            return ConnectorStatusEnum.ERROR
        elif self.consecutive_failures > 0:
            self.status = ConnectorStatusEnum.DEGRADED
            return ConnectorStatusEnum.DEGRADED

        try:
            client = self._client or httpx.AsyncClient(timeout=8.0)
            close_after = self._client is None
            try:
                # Test with first configured city
                test_city = self.target_cities[0] if self.target_cities else "New Delhi"
                url = f"{self.api_base_url}/india/weather"
                headers = {"x-api-key": self.api_key}
                params = {"city": test_city}
                resp = await client.get(url, headers=headers, params=params)

                if resp.status_code == 200:
                    self.status = ConnectorStatusEnum.HEALTHY
                    return ConnectorStatusEnum.HEALTHY
                elif resp.status_code in (401, 403):
                    self.status = ConnectorStatusEnum.ERROR
                    return ConnectorStatusEnum.ERROR
                elif resp.status_code == 429:
                    self.status = ConnectorStatusEnum.DEGRADED
                    return ConnectorStatusEnum.DEGRADED
                else:
                    self.status = ConnectorStatusEnum.DEGRADED
                    return ConnectorStatusEnum.DEGRADED
            finally:
                if close_after:
                    await client.aclose()
        except Exception as e:
            logger.warning("IndianAPI health check failed: %s", e)
            self.status = ConnectorStatusEnum.DEGRADED
            return ConnectorStatusEnum.DEGRADED

    async def poll(self) -> List[CanonicalRawEvent]:
        """Polls IndianAPI current weather observations across target cities."""
        if not self.is_running or not self.api_key or not self.api_key.strip():
            return []

        events: List[CanonicalRawEvent] = []
        t0 = time.time()
        client = self._client or httpx.AsyncClient(timeout=15.0)

        for city in self.target_cities:
            try:
                url = f"{self.api_base_url}/india/weather"
                headers = {"x-api-key": self.api_key}
                params = {"city": city}

                resp = await client.get(url, headers=headers, params=params)

                if resp.status_code == 200:
                    data = resp.json()
                    event = self.parse(data, requested_city=city)
                    if event:
                        events.append(event)
                    self.consecutive_failures = 0

                elif resp.status_code == 429:
                    self.consecutive_failures += 1
                    self.record_error("IndianAPI rate limit exceeded (HTTP 429)")
                    self.status = ConnectorStatusEnum.DEGRADED
                    break  # Politeness: stop current cycle on rate limit

                elif resp.status_code in (401, 403):
                    self.consecutive_failures += 1
                    self.status = ConnectorStatusEnum.ERROR
                    self.record_error(f"IndianAPI authentication failure (HTTP {resp.status_code})")
                    break

                elif resp.status_code == 404:
                    logger.debug("City '%s' not found in IndianAPI index (HTTP 404)", city)

                else:
                    self.consecutive_failures += 1
                    self.record_error(f"IndianAPI returned HTTP {resp.status_code} for city '{city}'")

            except Exception as e:
                self.consecutive_failures += 1
                self.record_error(f"Error polling IndianAPI for city '{city}': {e}")

        latency_ms = (time.time() - t0) * 1000
        if events:
            self.record_success(count=len(events), latency_ms=latency_ms)

        return events

    def parse(self, raw_data: Any, requested_city: Optional[str] = None) -> CanonicalRawEvent:
        """Parses IndianAPI JSON payload into a typed CanonicalRawEvent."""
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

        # 5. Descriptive Text
        text_parts = [f"Third-Party Weather Observation (IndianAPI) for {city_name}"]
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

        descriptive_text = " ".join(text_parts)

        # 6. Idempotency Key (Prevents duplicate events on same hour for same city)
        hash_input = f"indianapi:{city_slug}:{time_bucket}:{category}:{temp_val}:{rainfall_val}"
        idempotency_key = f"indianapi:{city_slug}:{hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:16]}"
        external_id = f"indianapi_{city_slug}_{time_bucket}"

        # 7. Complete Provenance Metadata Payload
        raw_payload = {
            "provider": "IndianAPI",
            "source_type": SourceType.WEATHER_API.value,
            "is_official_government": False,
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
            latitude=None,  # No fabricated GPS coordinates
            longitude=None,  # No fabricated GPS coordinates
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
