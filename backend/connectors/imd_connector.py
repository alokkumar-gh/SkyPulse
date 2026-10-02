"""
SkyPulse IMD Government Weather Data Ingestion Connector
=========================================================
Connects to official India Meteorological Department (IMD) data feeds,
normalizes government weather bulletins, nowcasts, AWS/ARG observations,
district rainfall, and color-coded warnings into the SkyPulse canonical pipeline.

Source Attribution:
  - source_type: GOVERNMENT_API
  - agency_name: India Meteorological Department (IMD)
  - high-trust government provenance (no synthetic/fake data fallback)
"""

import re
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
import httpx

from connectors.base import BaseConnector
from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum
from app.core.config import settings
from app.models.enums import WeatherCategory

logger = logging.getLogger("skypulse.connectors.imd")

# IST is UTC+05:30
IST_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


def parse_imd_timestamp(ts_val: Any) -> datetime:
    """
    Parses various IMD timestamp representations (IST or UTC) to UTC datetime.
    Falls back to current UTC datetime if unparseable.
    """
    if not ts_val:
        return datetime.now(timezone.utc)

    if isinstance(ts_val, datetime):
        if ts_val.tzinfo is None:
            return ts_val.replace(tzinfo=timezone.utc)
        return ts_val.astimezone(timezone.utc)

    if isinstance(ts_val, (int, float)):
        # Epoch seconds or milliseconds
        if ts_val > 1e11:  # ms
            ts_val = ts_val / 1000.0
        return datetime.fromtimestamp(ts_val, tz=timezone.utc)

    s = str(ts_val).strip()
    is_ist = False
    if "IST" in s:
        is_ist = True
        s = s.replace("IST", "").strip()

    # Common formats
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
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(s.replace("Z", "+0000"), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IST_TIMEZONE if is_ist else timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue

    # ISO fallback
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST_TIMEZONE if is_ist else timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    return datetime.now(timezone.utc)


def map_warning_color_to_severity(color_str: Optional[str]) -> int:
    """
    Maps standard IMD color-coded warning levels to SkyPulse 1-4 severity scale:
      - RED (Warning / Take Action) -> 4 (Extreme)
      - ORANGE (Alert / Be Prepared) -> 3 (Severe)
      - YELLOW (Watch / Be Updated) -> 2 (Moderate)
      - GREEN (No Warning / No Action) -> 1 (Minor)
    """
    if not color_str:
        return 2
    c = color_str.strip().upper()
    if re.search(r"\b(NO WARNING|NO ACTION|GREEN)\b", c):
        return 1
    if re.search(r"\b(RED|EXTREME|TAKE ACTION)\b", c):
        return 4
    if re.search(r"\b(ORANGE|AMBER|BE PREPARED|SEVERE)\b", c):
        return 3
    if re.search(r"\b(YELLOW|BE UPDATED|WATCH|MODERATE)\b", c):
        return 2
    return 2



def map_rainfall_to_severity(rainfall_mm: float) -> int:
    """
    Maps 24h rainfall amount (mm) to severity based on IMD classification:
      - >= 204.5 mm: Extremely Heavy -> Severity 4
      - 115.6 - 204.4 mm: Very Heavy -> Severity 3
      - 64.5 - 115.5 mm: Heavy -> Severity 2
      - < 64.5 mm: Light / Moderate -> Severity 1
    """
    if rainfall_mm >= 204.5:
        return 4
    if rainfall_mm >= 115.6:
        return 3
    if rainfall_mm >= 64.5:
        return 2
    return 1


class IMDConnector(BaseConnector):
    """
    Official India Meteorological Department (IMD) Multi-Feed Ingestion Connector.
    Supports:
      1. Current Weather observations (station reports)
      2. District Nowcasts (3-hour severe weather warnings)
      3. District Warnings (daily color-coded hazard alerts)
      4. District Rainfall (accumulated rainfall and departures)
      5. State Rainfall summaries
      6. AWS/ARG automated weather station telemetry
      7. City Forecasts (multi-day forecasts with semantic distinction)
      8. River Basin QPF (Quantitative Precipitation Forecast)
      9. RSS Feeds (Severe weather bulletin alerts)
    """

    def __init__(
        self,
        source_id: str = "00000000-0000-0000-0000-000000000002",
        name: str = "India Meteorological Department",
        api_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        poll_interval_seconds: int = 300,
        enabled_feeds: Optional[List[str]] = None,
    ):
        base_url = api_base_url or settings.IMD_API_BASE_URL
        key = api_key or settings.IMD_API_KEY
        interval = poll_interval_seconds or settings.IMD_POLL_INTERVAL_SECONDS

        config = {
            "api_base_url": base_url,
            "api_key": key,
            "poll_interval_seconds": interval,
            "agency": "India Meteorological Department",
            "enabled_feeds": enabled_feeds or [
                "current_weather",
                "district_nowcast",
                "district_warnings",
                "district_rainfall",
                "state_rainfall",
                "aws_observations",
                "city_forecast",
                "river_basin_qpf",
            ],
        }

        super().__init__(
            source_id=source_id,
            name=name,
            source_type="GOVERNMENT_API",
            config=config,
            is_demo=False,
        )

        self.api_base_url = (base_url or "").rstrip("/")
        self.api_key = key
        self.poll_interval_seconds = interval
        self.enabled_feeds = config["enabled_feeds"]
        self.agency_name = "India Meteorological Department (IMD)"

        # Initial status
        if not self.api_base_url and not settings.IMD_ENABLED:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
        else:
            self.status = ConnectorStatusEnum.HEALTHY

    async def health_check(self) -> ConnectorStatusEnum:
        """Inspect connectivity and availability of IMD endpoint."""
        if not self.api_base_url:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return ConnectorStatusEnum.NOT_CONFIGURED
        if not self.is_running:
            return ConnectorStatusEnum.DISABLED


        try:
            headers = {}
            if self.api_key:
                headers["X-API-KEY"] = self.api_key
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{self.api_base_url}/health", headers=headers)
                if res.status_code in (200, 204):
                    self.status = ConnectorStatusEnum.HEALTHY
                elif res.status_code in (401, 403):
                    self.status = ConnectorStatusEnum.ERROR
                    self.record_error(f"IMD Authentication failed: HTTP {res.status_code}")
                else:
                    self.status = ConnectorStatusEnum.DEGRADED
        except Exception as e:
            self.status = ConnectorStatusEnum.ERROR
            self.record_error(f"IMD Health check connection failure: {e}")

        return self.status

    async def poll(self) -> List[CanonicalRawEvent]:
        """
        Polls configured IMD feeds.
        Returns a consolidated list of standardized CanonicalRawEvent envelopes.
        """
        if not self.api_base_url:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return []

        t0 = time.time()
        all_events: List[CanonicalRawEvent] = []
        errors: List[str] = []

        headers = {
            "User-Agent": "SkyPulse-NationalWeatherAnalytics/1.0",
            "Accept": "application/json, text/xml",
        }
        if self.api_key:
            headers["X-API-KEY"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=20.0) as client:
            for feed in self.enabled_feeds:
                try:
                    events = await self._poll_feed(client, feed, headers)
                    all_events.extend(events)
                except httpx.HTTPStatusError as e:
                    errors.append(f"Feed '{feed}' HTTP {e.response.status_code}")
                except Exception as e:
                    errors.append(f"Feed '{feed}' error: {e}")

        latency = (time.time() - t0) * 1000
        if errors:
            combined_err = "; ".join(errors)
            self.record_error(combined_err)
            if all_events:
                self.status = ConnectorStatusEnum.DEGRADED
        else:
            self.record_success(len(all_events), latency)

        return all_events

    async def _poll_feed(
        self,
        client: httpx.AsyncClient,
        feed_name: str,
        headers: Dict[str, str],
    ) -> List[CanonicalRawEvent]:
        """Polls a specific IMD sub-feed endpoint and dispatches to appropriate parser."""
        endpoint_map = {
            "current_weather": "/api/current-weather",
            "district_nowcast": "/api/nowcast/district",
            "district_warnings": "/api/warnings/district",
            "district_rainfall": "/api/rainfall/district",
            "state_rainfall": "/api/rainfall/state",
            "aws_observations": "/api/aws/observations",
            "city_forecast": "/api/forecast/city",
            "river_basin_qpf": "/api/qpf/river-basin",
            "rss_feed": "/rss/bulletins",
        }

        path = endpoint_map.get(feed_name, f"/api/{feed_name.replace('_', '-')}")
        url = f"{self.api_base_url}{path}"

        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            resp.raise_for_status()

        events: List[CanonicalRawEvent] = []
        data = resp.json()

        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = (
                data.get("data")
                or data.get("items")
                or data.get("records")
                or data.get("features")
                or data.get("stations")
                or data.get("districts")
                or [data]
            )

        parser_dispatch = {
            "current_weather": self.parse_current_weather,
            "district_nowcast": self.parse_district_nowcast,
            "district_warnings": self.parse_district_warning,
            "district_rainfall": self.parse_district_rainfall,
            "state_rainfall": self.parse_state_rainfall,
            "aws_observations": self.parse_aws_observation,
            "city_forecast": self.parse_city_forecast,
            "river_basin_qpf": self.parse_river_basin_qpf,
        }

        parser = parser_dispatch.get(feed_name, self.parse)
        for raw_item in items:
            try:
                ev = parser(raw_item)
                if ev:
                    events.append(ev)
            except Exception as pe:
                logger.warning("Failed to parse IMD %s item: %s", feed_name, pe)

        return events

    # -------------------------------------------------------------------------
    # PARSER IMPLEMENTATIONS
    # -------------------------------------------------------------------------

    def parse(self, raw_data: Any) -> CanonicalRawEvent:
        """Generic fallback parser for unstructured or bulletin items."""
        return self.parse_current_weather(raw_data)

    def parse_current_weather(self, raw_data: Dict[str, Any]) -> CanonicalRawEvent:
        """
        Parses official IMD current weather surface station observation.
        Includes temperature, humidity, pressure, visibility, rainfall, wind.
        """
        station_id = raw_data.get("station_id") or raw_data.get("station_code") or raw_data.get("id") or "IMD-OBS"
        station_name = raw_data.get("station_name") or raw_data.get("station") or raw_data.get("city") or "IMD Station"
        district = raw_data.get("district") or raw_data.get("district_name")
        state = raw_data.get("state") or raw_data.get("state_name")
        observed_at = parse_imd_timestamp(raw_data.get("observed_at") or raw_data.get("timestamp") or raw_data.get("time"))

        temp_c = raw_data.get("temperature_c") or raw_data.get("temp_c") or raw_data.get("temperature")
        humidity = raw_data.get("humidity_pct") or raw_data.get("relative_humidity") or raw_data.get("humidity")
        wind_speed_kmh = raw_data.get("wind_speed_kmh") or raw_data.get("wind_speed")
        wind_dir = raw_data.get("wind_direction") or raw_data.get("wind_dir")
        pressure_hpa = raw_data.get("pressure_hpa") or raw_data.get("pressure")
        rainfall_24h_mm = float(raw_data.get("rainfall_24h_mm") or raw_data.get("rainfall_mm") or raw_data.get("rainfall") or 0.0)
        weather_condition = raw_data.get("weather_condition") or raw_data.get("condition") or "Fair"

        # Determine category & severity
        category = WeatherCategory.RAINFALL.value if rainfall_24h_mm > 0 else WeatherCategory.UNKNOWN.value
        if "THUNDER" in str(weather_condition).upper():
            category = WeatherCategory.THUNDERSTORM.value
        elif "HEAT" in str(weather_condition).upper() or (temp_c and float(temp_c) >= 42.0):
            category = WeatherCategory.HEATWAVE.value
        elif "FOG" in str(weather_condition).upper():
            category = WeatherCategory.FOG.value
        elif "WIND" in str(weather_condition).upper() or (wind_speed_kmh and float(wind_speed_kmh) >= 50.0):
            category = WeatherCategory.STRONG_WINDS.value

        severity = map_rainfall_to_severity(rainfall_24h_mm) if rainfall_24h_mm > 0 else 1
        if category == WeatherCategory.HEATWAVE.value and temp_c and float(temp_c) >= 45.0:
            severity = 4

        # Compose descriptive text
        text_parts = [f"[{self.agency_name}] Official Observation at {station_name}"]
        if district and state:
            text_parts.append(f"({district}, {state})")
        text_parts.append(f": Condition: {weather_condition}.")
        if temp_c is not None:
            text_parts.append(f"Temp: {temp_c}°C.")
        if humidity is not None:
            text_parts.append(f"Humidity: {humidity}%.")
        if rainfall_24h_mm > 0:
            text_parts.append(f"24h Rainfall: {rainfall_24h_mm:.1f} mm.")
        if wind_speed_kmh is not None:
            text_parts.append(f"Wind: {wind_speed_kmh} km/h {wind_dir or ''}.")
        if pressure_hpa is not None:
            text_parts.append(f"Pressure: {pressure_hpa} hPa.")

        text = " ".join(text_parts)
        ext_id = f"imd_obs_{station_id}_{int(observed_at.timestamp())}"
        idempotency_key = f"imd:obs:{station_id}:{observed_at.strftime('%Y%m%d%H%M')}"

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type="GOVERNMENT_API",
            external_id=ext_id,
            observed_at=observed_at,
            ingested_at=datetime.now(timezone.utc),
            text=text,
            latitude=raw_data.get("latitude") or raw_data.get("lat"),
            longitude=raw_data.get("longitude") or raw_data.get("lon"),
            city=station_name,
            district=district,
            state=state,
            suggested_category=category,
            severity=severity,
            raw_payload={
                "data_type": "OBSERVATION",
                "station_id": station_id,
                "station_name": station_name,
                "temperature_c": temp_c,
                "humidity_pct": humidity,
                "rainfall_24h_mm": rainfall_24h_mm,
                "wind_speed_kmh": wind_speed_kmh,
                "wind_direction": wind_dir,
                "pressure_hpa": pressure_hpa,
                "weather_condition": weather_condition,
                "raw": raw_data,
            },
            is_demo=False,
            idempotency_key=idempotency_key,
        )

    def parse_district_nowcast(self, raw_data: Dict[str, Any]) -> CanonicalRawEvent:
        """
        Parses IMD District Nowcast (3-hour mesoscale warning).
        Extracts district, state, weather phenomena, and warning level.
        """
        district = raw_data.get("district") or raw_data.get("district_name") or "Unknown District"
        state = raw_data.get("state") or raw_data.get("state_name") or "India"
        phenomena = raw_data.get("phenomena") or raw_data.get("hazard") or raw_data.get("description") or "Thunderstorm with rain"
        valid_from = parse_imd_timestamp(raw_data.get("valid_from") or raw_data.get("issue_time"))
        valid_until = parse_imd_timestamp(raw_data.get("valid_until") or raw_data.get("valid_upto"))
        severity_level = raw_data.get("severity") or raw_data.get("warning_level") or "MODERATE"
        severity = map_warning_color_to_severity(str(severity_level))

        # Categorize
        phenomena_upper = str(phenomena).upper()
        if "THUNDER" in phenomena_upper or "LIGHTNING" in phenomena_upper:
            category = WeatherCategory.THUNDERSTORM.value
        elif "HEAVY RAIN" in phenomena_upper or "DOWNPOUR" in phenomena_upper or "SQUALL" in phenomena_upper:
            category = WeatherCategory.RAINFALL.value
        elif "HAIL" in phenomena_upper:
            category = WeatherCategory.HAILSTORM.value
        elif "GUSTY" in phenomena_upper or "SQUALL" in phenomena_upper or "WIND" in phenomena_upper:
            category = WeatherCategory.STRONG_WINDS.value
        elif "DUST" in phenomena_upper:
            category = WeatherCategory.DUST_STORM.value
        else:
            category = WeatherCategory.RAINFALL.value

        text = (
            f"[{self.agency_name}] District Nowcast Warning for {district}, {state}: "
            f"{phenomena}. Severity: {severity_level}. Valid until {valid_until.strftime('%H:%M UTC')}."
        )

        ext_id = f"imd_nowcast_{district}_{int(valid_from.timestamp())}"
        idempotency_key = f"imd:nowcast:{district}:{valid_from.strftime('%Y%m%d%H%M')}_{valid_until.strftime('%Y%m%d%H%M')}"

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type="GOVERNMENT_API",
            external_id=ext_id,
            observed_at=valid_from,
            ingested_at=datetime.now(timezone.utc),
            text=text,
            latitude=raw_data.get("latitude") or raw_data.get("lat"),
            longitude=raw_data.get("longitude") or raw_data.get("lon"),
            city=district,
            district=district,
            state=state,
            suggested_category=category,
            severity=severity,
            raw_payload={
                "data_type": "NOWCAST",
                "phenomena": phenomena,
                "severity_level": severity_level,
                "valid_from": valid_from.isoformat(),
                "valid_until": valid_until.isoformat(),
                "raw": raw_data,
            },
            is_demo=False,
            idempotency_key=idempotency_key,
        )

    def parse_district_warning(self, raw_data: Dict[str, Any]) -> CanonicalRawEvent:
        """
        Parses IMD Daily Color-Coded District Warnings (Green / Yellow / Orange / Red).
        """
        district = raw_data.get("district") or raw_data.get("district_name") or "District"
        state = raw_data.get("state") or raw_data.get("state_name") or "State"
        color = raw_data.get("color") or raw_data.get("warning_color") or raw_data.get("level") or "YELLOW"
        warning_type = raw_data.get("warning_type") or raw_data.get("hazard") or "Heavy Rainfall Warning"
        description = raw_data.get("description") or raw_data.get("warning_text") or warning_type
        warning_date = parse_imd_timestamp(raw_data.get("date") or raw_data.get("valid_date") or raw_data.get("timestamp"))

        severity = map_warning_color_to_severity(color)

        w_upper = str(warning_type).upper()
        if "CYCLONE" in w_upper:
            category = WeatherCategory.CYCLONE.value
        elif "HEAT" in w_upper:
            category = WeatherCategory.HEATWAVE.value
        elif "THUNDER" in w_upper:
            category = WeatherCategory.THUNDERSTORM.value
        elif "FOG" in w_upper:
            category = WeatherCategory.FOG.value
        elif "DUST" in w_upper:
            category = WeatherCategory.DUST_STORM.value
        elif "WIND" in w_upper:
            category = WeatherCategory.STRONG_WINDS.value
        elif "HAIL" in w_upper:
            category = WeatherCategory.HAILSTORM.value
        else:
            category = WeatherCategory.RAINFALL.value

        text = (
            f"[{self.agency_name}] Color-Coded Warning ({color.upper()}) for {district}, {state}: "
            f"{warning_type}. {description}"
        )

        ext_id = f"imd_warn_{district}_{color}_{warning_date.strftime('%Y%m%d')}"
        idempotency_key = f"imd:warn:{district}:{warning_date.strftime('%Y%m%d')}:{w_upper[:20]}"

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type="GOVERNMENT_API",
            external_id=ext_id,
            observed_at=warning_date,
            ingested_at=datetime.now(timezone.utc),
            text=text,
            latitude=raw_data.get("latitude") or raw_data.get("lat"),
            longitude=raw_data.get("longitude") or raw_data.get("lon"),
            city=district,
            district=district,
            state=state,
            suggested_category=category,
            severity=severity,
            raw_payload={
                "data_type": "WARNING",
                "warning_color": color.upper(),
                "warning_type": warning_type,
                "description": description,
                "raw": raw_data,
            },
            is_demo=False,
            idempotency_key=idempotency_key,
        )

    def parse_district_rainfall(self, raw_data: Dict[str, Any]) -> CanonicalRawEvent:
        """
        Parses IMD District Rainfall Summary (accumulated rainfall and departure from normal).
        """
        district = raw_data.get("district") or raw_data.get("district_name") or "District"
        state = raw_data.get("state") or raw_data.get("state_name") or "State"
        actual_mm = float(raw_data.get("actual_rainfall_mm") or raw_data.get("actual_mm") or raw_data.get("rainfall_mm") or 0.0)
        normal_mm = float(raw_data.get("normal_rainfall_mm") or raw_data.get("normal_mm") or 0.0)
        departure_pct = float(raw_data.get("departure_pct") or raw_data.get("departure") or 0.0)
        category_desc = raw_data.get("category") or raw_data.get("departure_category") or "Normal"
        obs_date = parse_imd_timestamp(raw_data.get("date") or raw_data.get("observed_at"))

        severity = map_rainfall_to_severity(actual_mm)

        text = (
            f"[{self.agency_name}] 24h District Rainfall Report for {district}, {state}: "
            f"{actual_mm:.1f} mm (Normal: {normal_mm:.1f} mm, Departure: {departure_pct:+.1f}% - {category_desc})."
        )

        ext_id = f"imd_rain_{district}_{obs_date.strftime('%Y%m%d')}"
        idempotency_key = f"imd:rain:district:{district}:{obs_date.strftime('%Y%m%d')}"

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type="GOVERNMENT_API",
            external_id=ext_id,
            observed_at=obs_date,
            ingested_at=datetime.now(timezone.utc),
            text=text,
            latitude=raw_data.get("latitude") or raw_data.get("lat"),
            longitude=raw_data.get("longitude") or raw_data.get("lon"),
            city=district,
            district=district,
            state=state,
            suggested_category=WeatherCategory.RAINFALL.value,
            severity=severity,
            raw_payload={
                "data_type": "OBSERVATION",
                "metric": "RAINFALL",
                "actual_rainfall_mm": actual_mm,
                "normal_rainfall_mm": normal_mm,
                "departure_pct": departure_pct,
                "departure_category": category_desc,
                "raw": raw_data,
            },
            is_demo=False,
            idempotency_key=idempotency_key,
        )

    def parse_state_rainfall(self, raw_data: Dict[str, Any]) -> CanonicalRawEvent:
        """
        Parses IMD State-Level Rainfall Summary.
        """
        state = raw_data.get("state") or raw_data.get("state_name") or "India"
        actual_mm = float(raw_data.get("actual_rainfall_mm") or raw_data.get("actual_mm") or 0.0)
        normal_mm = float(raw_data.get("normal_rainfall_mm") or raw_data.get("normal_mm") or 0.0)
        departure_pct = float(raw_data.get("departure_pct") or 0.0)
        obs_date = parse_imd_timestamp(raw_data.get("date") or raw_data.get("timestamp"))

        severity = map_rainfall_to_severity(actual_mm)

        text = (
            f"[{self.agency_name}] State Daily Rainfall Summary for {state}: "
            f"{actual_mm:.1f} mm (Normal: {normal_mm:.1f} mm, Departure: {departure_pct:+.1f}%)."
        )

        ext_id = f"imd_state_rain_{state}_{obs_date.strftime('%Y%m%d')}"
        idempotency_key = f"imd:rain:state:{state}:{obs_date.strftime('%Y%m%d')}"

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type="GOVERNMENT_API",
            external_id=ext_id,
            observed_at=obs_date,
            ingested_at=datetime.now(timezone.utc),
            text=text,
            state=state,
            suggested_category=WeatherCategory.RAINFALL.value,
            severity=severity,
            raw_payload={
                "data_type": "OBSERVATION",
                "spatial_level": "STATE",
                "actual_rainfall_mm": actual_mm,
                "normal_rainfall_mm": normal_mm,
                "departure_pct": departure_pct,
                "raw": raw_data,
            },
            is_demo=False,
            idempotency_key=idempotency_key,
        )

    def parse_aws_observation(self, raw_data: Dict[str, Any]) -> CanonicalRawEvent:
        """
        Parses IMD Automatic Weather Station (AWS) / Automatic Rain Gauge (ARG) telemetry.
        """
        station_id = raw_data.get("station_id") or raw_data.get("station_code") or "AWS-001"
        station_name = raw_data.get("station_name") or station_id
        district = raw_data.get("district")
        state = raw_data.get("state")
        obs_time = parse_imd_timestamp(raw_data.get("timestamp") or raw_data.get("time"))

        temp = raw_data.get("temperature") or raw_data.get("temp")
        rain_1h = float(raw_data.get("rain_1h_mm") or raw_data.get("rain_1h") or 0.0)
        rain_24h = float(raw_data.get("rain_24h_mm") or raw_data.get("rain_24h") or 0.0)
        wind_speed = raw_data.get("wind_speed_kmh") or raw_data.get("wind_speed")
        wind_dir = raw_data.get("wind_direction")
        humidity = raw_data.get("humidity")
        pressure = raw_data.get("pressure")

        category = WeatherCategory.RAINFALL.value if (rain_1h > 0 or rain_24h > 0) else WeatherCategory.UNKNOWN.value
        severity = map_rainfall_to_severity(rain_24h if rain_24h > 0 else rain_1h * 5)

        text_parts = [f"[{self.agency_name}] AWS Station Telemetry: {station_name} ({station_id})"]
        if temp is not None:
            text_parts.append(f"Temp: {temp}°C.")
        if humidity is not None:
            text_parts.append(f"Humidity: {humidity}%.")
        if rain_1h > 0:
            text_parts.append(f"1h Rain: {rain_1h:.1f} mm.")
        if rain_24h > 0:
            text_parts.append(f"24h Rain: {rain_24h:.1f} mm.")
        if wind_speed is not None:
            text_parts.append(f"Wind: {wind_speed} km/h {wind_dir or ''}.")
        if pressure is not None:
            text_parts.append(f"Pressure: {pressure} hPa.")

        text = " ".join(text_parts)
        ext_id = f"imd_aws_{station_id}_{int(obs_time.timestamp())}"
        idempotency_key = f"imd:aws:{station_id}:{obs_time.strftime('%Y%m%d%H%M')}"

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type="GOVERNMENT_API",
            external_id=ext_id,
            observed_at=obs_time,
            ingested_at=datetime.now(timezone.utc),
            text=text,
            latitude=raw_data.get("latitude") or raw_data.get("lat"),
            longitude=raw_data.get("longitude") or raw_data.get("lon"),
            city=station_name,
            district=district,
            state=state,
            suggested_category=category,
            severity=severity,
            raw_payload={
                "data_type": "OBSERVATION",
                "sensor_type": "AWS",
                "station_id": station_id,
                "temperature": temp,
                "humidity": humidity,
                "rain_1h_mm": rain_1h,
                "rain_24h_mm": rain_24h,
                "wind_speed_kmh": wind_speed,
                "pressure": pressure,
                "raw": raw_data,
            },
            is_demo=False,
            idempotency_key=idempotency_key,
        )

    def parse_city_forecast(self, raw_data: Dict[str, Any]) -> CanonicalRawEvent:
        """
        Parses IMD 7-day City Weather Forecast.
        Crucial semantic distinction: marked as FORECAST (not an observation).
        """
        city = raw_data.get("city") or raw_data.get("city_name") or "City"
        state = raw_data.get("state")
        forecast_date = parse_imd_timestamp(raw_data.get("forecast_date") or raw_data.get("date"))
        max_temp = raw_data.get("max_temp_c") or raw_data.get("max_temp")
        min_temp = raw_data.get("min_temp_c") or raw_data.get("min_temp")
        forecast_weather = raw_data.get("forecast") or raw_data.get("weather_prediction") or "Partly Cloudy"

        # Categorize
        fw_upper = str(forecast_weather).upper()
        if "THUNDER" in fw_upper:
            category = WeatherCategory.THUNDERSTORM.value
        elif "RAIN" in fw_upper or "SHOWER" in fw_upper:
            category = WeatherCategory.RAINFALL.value
        elif "HEAT" in fw_upper or (max_temp and float(max_temp) >= 42.0):
            category = WeatherCategory.HEATWAVE.value
        elif "FOG" in fw_upper:
            category = WeatherCategory.FOG.value
        else:
            category = WeatherCategory.UNKNOWN.value

        text = (
            f"[{self.agency_name}] Official Forecast for {city} on {forecast_date.strftime('%d-%b-%Y')}: "
            f"{forecast_weather}. Max Temp: {max_temp}°C, Min Temp: {min_temp}°C."
        )

        ext_id = f"imd_fcst_{city}_{forecast_date.strftime('%Y%m%d')}"
        idempotency_key = f"imd:forecast:{city}:{forecast_date.strftime('%Y%m%d')}"

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type="GOVERNMENT_API",
            external_id=ext_id,
            observed_at=forecast_date,
            ingested_at=datetime.now(timezone.utc),
            text=text,
            latitude=raw_data.get("latitude") or raw_data.get("lat"),
            longitude=raw_data.get("longitude") or raw_data.get("lon"),
            city=city,
            district=city,
            state=state,
            suggested_category=category,
            severity=1,
            raw_payload={
                "data_type": "FORECAST",
                "city": city,
                "forecast_weather": forecast_weather,
                "max_temp_c": max_temp,
                "min_temp_c": min_temp,
                "raw": raw_data,
            },
            is_demo=False,
            idempotency_key=idempotency_key,
        )

    def parse_river_basin_qpf(self, raw_data: Dict[str, Any]) -> CanonicalRawEvent:
        """
        Parses IMD Quantitative Precipitation Forecast (QPF) by River Sub-Basin.
        """
        basin_name = raw_data.get("basin_name") or raw_data.get("sub_basin") or "River Basin"
        state = raw_data.get("state")
        qpf_range = raw_data.get("qpf_range_mm") or raw_data.get("qpf_category") or "11-25 mm"
        valid_date = parse_imd_timestamp(raw_data.get("date") or raw_data.get("valid_date"))

        text = (
            f"[{self.agency_name}] Hydrological QPF Forecast for {basin_name} Sub-Basin: "
            f"Expected Precipitation: {qpf_range}."
        )

        ext_id = f"imd_qpf_{basin_name}_{valid_date.strftime('%Y%m%d')}"
        idempotency_key = f"imd:qpf:{basin_name}:{valid_date.strftime('%Y%m%d')}"

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type="GOVERNMENT_API",
            external_id=ext_id,
            observed_at=valid_date,
            ingested_at=datetime.now(timezone.utc),
            text=text,
            latitude=raw_data.get("latitude") or raw_data.get("lat"),
            longitude=raw_data.get("longitude") or raw_data.get("lon"),
            city=basin_name,
            district=basin_name,
            state=state,
            suggested_category=WeatherCategory.RAINFALL.value,
            severity=2,
            raw_payload={
                "data_type": "FORECAST",
                "hydrological_type": "QPF",
                "basin_name": basin_name,
                "qpf_range": qpf_range,
                "raw": raw_data,
            },
            is_demo=False,
            idempotency_key=idempotency_key,
        )
