"""
SkyPulse Open-Meteo Operational Weather Data Connector
======================================================
Integrates Open-Meteo (https://open-meteo.com) as a real-time, non-commercial,
free operational meteorological data source for India.

Operational Highlights:
- Connects directly to the Open-Meteo Forecast API (`https://api.open-meteo.com/v1/forecast`).
- Does NOT require an API key for free non-commercial usage.
- Queries standard WMO-standard meteorological parameters:
  - 2m Temperature & Apparent Temperature
  - Relative Humidity
  - Precipitation, Rain, Showers, Snowfall
  - WMO Weather Interpretation Codes (0-99)
  - Wind Speed & Gusts (10m)
  - Cloud Cover & Surface Pressure
- Maps observations accurately into the 7 standard SIH categories:
  RAINFALL, THUNDERSTORM, FLOODING, HEATWAVE, FOG, DUST_STORM, STRONG_WINDS.
- Zero GPS fabrication: Query coordinates are explicitly labeled as provider/monitoring grid points.
- Enters the SAME unified SkyPulse pipeline:
  CanonicalRawEvent -> Normalization -> India Validation -> Dedup -> AI/NLP -> Trust -> DWEG -> PostgreSQL -> Realtime.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.models.enums import SourceType
from connectors.base import BaseConnector
from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum

logger = logging.getLogger("skypulse.connectors.openmeteo")

# Standard WMO 4677 weather interpretation code translation
# Format: code: (Description, SIH Category)
WMO_WEATHER_CODE_MAP: Dict[int, Tuple[str, str]] = {
    0: ("Clear sky", "UNKNOWN"),
    1: ("Mainly clear", "UNKNOWN"),
    2: ("Partly cloudy", "UNKNOWN"),
    3: ("Overcast", "UNKNOWN"),
    45: ("Fog", "FOG"),
    48: ("Depositing rime fog", "FOG"),
    51: ("Light drizzle", "RAINFALL"),
    53: ("Moderate drizzle", "RAINFALL"),
    55: ("Dense drizzle", "RAINFALL"),
    56: ("Light freezing drizzle", "RAINFALL"),
    57: ("Dense freezing drizzle", "RAINFALL"),
    61: ("Slight rain", "RAINFALL"),
    63: ("Moderate rain", "RAINFALL"),
    65: ("Heavy rain", "RAINFALL"),
    66: ("Light freezing rain", "RAINFALL"),
    67: ("Heavy freezing rain", "RAINFALL"),
    71: ("Slight snowfall", "UNKNOWN"),
    73: ("Moderate snowfall", "UNKNOWN"),
    75: ("Heavy snowfall", "UNKNOWN"),
    77: ("Snow grains", "UNKNOWN"),
    80: ("Slight rain showers", "RAINFALL"),
    81: ("Moderate rain showers", "RAINFALL"),
    82: ("Violent rain showers", "RAINFALL"),
    85: ("Slight snow showers", "UNKNOWN"),
    86: ("Heavy snow showers", "UNKNOWN"),
    95: ("Thunderstorm", "THUNDERSTORM"),
    96: ("Thunderstorm with slight hail", "THUNDERSTORM"),
    99: ("Thunderstorm with heavy hail", "THUNDERSTORM"),
}

DEFAULT_INDIAN_LOCATIONS: List[Dict[str, Any]] = [
    # 28 States
    {"city": "Visakhapatnam", "district": "Visakhapatnam", "state": "Andhra Pradesh", "lat": 17.6868, "lon": 83.2185},
    {"city": "Itanagar", "district": "Papum Pare", "state": "Arunachal Pradesh", "lat": 27.0844, "lon": 93.6053},
    {"city": "Guwahati", "district": "Kamrup Metropolitan", "state": "Assam", "lat": 26.1445, "lon": 91.7362},
    {"city": "Patna", "district": "Patna", "state": "Bihar", "lat": 25.5941, "lon": 85.1376},
    {"city": "Raipur", "district": "Raipur", "state": "Chhattisgarh", "lat": 21.2514, "lon": 81.6296},
    {"city": "Panaji", "district": "North Goa", "state": "Goa", "lat": 15.4909, "lon": 73.8278},
    {"city": "Ahmedabad", "district": "Ahmedabad", "state": "Gujarat", "lat": 23.0225, "lon": 72.5714},
    {"city": "Gurugram", "district": "Gurugram", "state": "Haryana", "lat": 28.4595, "lon": 77.0266},
    {"city": "Shimla", "district": "Shimla", "state": "Himachal Pradesh", "lat": 31.1048, "lon": 77.1734},
    {"city": "Ranchi", "district": "Ranchi", "state": "Jharkhand", "lat": 23.3441, "lon": 85.3096},
    {"city": "Bengaluru", "district": "Bengaluru Urban", "state": "Karnataka", "lat": 12.9716, "lon": 77.5946},
    {"city": "Thiruvananthapuram", "district": "Thiruvananthapuram", "state": "Kerala", "lat": 8.5241, "lon": 76.9366},
    {"city": "Bhopal", "district": "Bhopal", "state": "Madhya Pradesh", "lat": 23.2599, "lon": 77.4126},
    {"city": "Mumbai", "district": "Mumbai City", "state": "Maharashtra", "lat": 19.0760, "lon": 72.8777},
    {"city": "Imphal", "district": "Imphal West", "state": "Manipur", "lat": 24.8170, "lon": 93.9368},
    {"city": "Shillong", "district": "East Khasi Hills", "state": "Meghalaya", "lat": 25.5788, "lon": 91.8933},
    {"city": "Aizawl", "district": "Aizawl", "state": "Mizoram", "lat": 23.7271, "lon": 92.7176},
    {"city": "Kohima", "district": "Kohima", "state": "Nagaland", "lat": 25.6751, "lon": 94.1086},
    {"city": "Bhubaneswar", "district": "Khurda", "state": "Odisha", "lat": 20.2961, "lon": 85.8245},
    {"city": "Amritsar", "district": "Amritsar", "state": "Punjab", "lat": 31.6340, "lon": 74.8723},
    {"city": "Jaipur", "district": "Jaipur", "state": "Rajasthan", "lat": 26.9124, "lon": 75.7873},
    {"city": "Gangtok", "district": "East Sikkim", "state": "Sikkim", "lat": 27.3389, "lon": 88.6065},
    {"city": "Chennai", "district": "Chennai", "state": "Tamil Nadu", "lat": 13.0827, "lon": 80.2707},
    {"city": "Hyderabad", "district": "Hyderabad", "state": "Telangana", "lat": 17.3850, "lon": 78.4867},
    {"city": "Agartala", "district": "West Tripura", "state": "Tripura", "lat": 23.8315, "lon": 91.2868},
    {"city": "Lucknow", "district": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8467, "lon": 80.9462},
    {"city": "Dehradun", "district": "Dehradun", "state": "Uttarakhand", "lat": 30.3165, "lon": 78.0322},
    {"city": "Kolkata", "district": "Kolkata", "state": "West Bengal", "lat": 22.5726, "lon": 88.3639},
    # 8 Union Territories
    {"city": "Port Blair", "district": "South Andaman", "state": "Andaman and Nicobar Islands", "lat": 11.6234, "lon": 92.7265},
    {"city": "Chandigarh", "district": "Chandigarh", "state": "Chandigarh", "lat": 30.7333, "lon": 76.7794},
    {"city": "Daman", "district": "Daman", "state": "Dadra and Nagar Haveli and Daman and Diu", "lat": 20.3974, "lon": 72.8328},
    {"city": "New Delhi", "district": "New Delhi", "state": "Delhi", "lat": 28.6139, "lon": 77.2090},
    {"city": "Srinagar", "district": "Srinagar", "state": "Jammu and Kashmir", "lat": 34.0837, "lon": 74.7973},
    {"city": "Leh", "district": "Leh", "state": "Ladakh", "lat": 34.1526, "lon": 77.5771},
    {"city": "Kavaratti", "district": "Lakshadweep", "state": "Lakshadweep", "lat": 10.5667, "lon": 72.6417},
    {"city": "Puducherry", "district": "Puducherry", "state": "Puducherry", "lat": 11.9416, "lon": 79.8083},
]


def map_openmeteo_wmo_code(
    wmo_code: int,
    wind_speed_kmph: float = 0.0,
    wind_gusts_kmph: float = 0.0,
    temp_c: float = 25.0,
    precip_mm: float = 0.0,
) -> Tuple[str, str]:
    """
    Translates Open-Meteo WMO code and meteorological metrics into
    (condition_description, sih_category).
    """
    desc, base_cat = WMO_WEATHER_CODE_MAP.get(wmo_code, (f"WMO Code {wmo_code}", "UNKNOWN"))

    # Priority 1: High Wind conditions
    if wind_speed_kmph >= 50.0 or wind_gusts_kmph >= 65.0:
        if base_cat == "THUNDERSTORM":
            return (f"{desc} with gale-force winds ({wind_speed_kmph:.1f} km/h)", "THUNDERSTORM")
        return (f"Strong winds / Gusts of {max(wind_speed_kmph, wind_gusts_kmph):.1f} km/h", "STRONG_WINDS")

    # Priority 2: Thunderstorm
    if base_cat == "THUNDERSTORM":
        return (desc, "THUNDERSTORM")

    # Priority 3: Rainfall & Precipitation
    if base_cat == "RAINFALL" or precip_mm > 0.5:
        return (desc if base_cat == "RAINFALL" else f"Precipitation ({precip_mm:.1f} mm)", "RAINFALL")

    # Priority 4: Fog
    if base_cat == "FOG":
        return (desc, "FOG")

    # Priority 5: Heatwave conditions (Extreme temperature with clear/dry weather)
    if temp_c >= 42.0 and precip_mm == 0.0 and wmo_code <= 3:
        return (f"Extreme heat ({temp_c:.1f}°C)", "HEATWAVE")

    return (desc, base_cat)


def infer_openmeteo_severity(
    wmo_code: int,
    temp_c: float = 25.0,
    precip_mm: float = 0.0,
    wind_speed_kmph: float = 0.0,
    wind_gusts_kmph: float = 0.0,
) -> int:
    """
    Calculates severity level (1=Low/Advisory, 2=Moderate, 3=Severe, 4=Critical)
    from Open-Meteo meteorological variables.
    """
    # Level 4: Catastrophic / Extreme Weather
    if (
        wmo_code in (96, 99)
        or precip_mm >= 75.0
        or wind_gusts_kmph >= 90.0
        or wind_speed_kmph >= 70.0
        or temp_c >= 45.0
    ):
        return 4

    # Level 3: Severe Weather
    if (
        wmo_code == 95
        or wmo_code in (65, 82)
        or precip_mm >= 35.0
        or wind_gusts_kmph >= 65.0
        or wind_speed_kmph >= 50.0
        or temp_c >= 42.0
    ):
        return 3

    # Level 2: Moderate Weather
    if (
        wmo_code in (63, 81, 45, 48)
        or precip_mm >= 10.0
        or wind_speed_kmph >= 35.0
        or wind_gusts_kmph >= 45.0
        or temp_c >= 38.0
    ):
        return 2

    # Level 1: Low / Minor Weather
    return 1


class OpenMeteoConnector(BaseConnector):
    """
    Operational weather data connector querying the Open-Meteo REST API.
    Provides free, real-time meteorological observations across Indian monitoring points.
    """

    def __init__(
        self,
        source_id: str = "00000000-0000-0000-0000-000000000008",
        name: str = "Open-Meteo Operational Weather Provider",
        base_url: Optional[str] = None,
        poll_interval_seconds: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        locations: Optional[List[Dict[str, Any]]] = None,
        enabled: Optional[bool] = None,
    ):
        super().__init__(
            source_id=source_id,
            name=name,
            source_type=SourceType.WEATHER_API.value,
            config={
                "base_url": base_url or getattr(settings, "OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast"),
                "poll_interval_seconds": poll_interval_seconds or getattr(settings, "OPEN_METEO_POLL_INTERVAL_SECONDS", 600),
            },
            is_demo=False,
        )
        self.base_url = (
            base_url
            or self.config.get("base_url")
            or getattr(settings, "OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast")
        ).rstrip("/")

        self.poll_interval = int(
            poll_interval_seconds
            or self.config.get("poll_interval_seconds")
            or getattr(settings, "OPEN_METEO_POLL_INTERVAL_SECONDS", 600)
        )
        self.timeout_seconds = float(
            timeout_seconds or getattr(settings, "OPEN_METEO_TIMEOUT_SECONDS", 15.0)
        )
        self.enabled = (
            enabled
            if enabled is not None
            else getattr(settings, "OPEN_METEO_ENABLED", True)
        )

        self.locations: List[Dict[str, Any]] = locations or self._parse_configured_locations() or DEFAULT_INDIAN_LOCATIONS
        self.consecutive_failures = 0
        self._client: Optional[httpx.AsyncClient] = None

        if not self.enabled:
            self.status = ConnectorStatusEnum.DISABLED
        else:
            self.status = ConnectorStatusEnum.HEALTHY

    def _parse_configured_locations(self) -> List[Dict[str, Any]]:
        raw = getattr(settings, "OPEN_METEO_LOCATIONS", "")
        if not raw or not isinstance(raw, str):
            return []

        parsed: List[Dict[str, Any]] = []
        for entry in raw.split(","):
            parts = [p.strip() for p in entry.split(":") if p.strip()]
            if len(parts) >= 3:
                try:
                    city = parts[0]
                    lat = float(parts[1])
                    lon = float(parts[2])
                    state = parts[3] if len(parts) >= 4 else "India"
                    district = parts[4] if len(parts) >= 5 else city
                    parsed.append({"city": city, "lat": lat, "lon": lon, "state": state, "district": district})
                except ValueError:
                    continue
        return parsed

    async def start(self) -> None:
        """Initializes the HTTP client and sets the connector state."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds, connect=8.0),
            headers={
                "User-Agent": "SkyPulse-NationalWeatherAnalytics/1.0 (+https://skypulse.gov.in)",
                "Accept": "application/json",
            },
            follow_redirects=True,
        )
        self.is_running = True

        if not self.enabled:
            self.status = ConnectorStatusEnum.DISABLED
            logger.info("OpenMeteoConnector started in DISABLED state.")
        else:
            self.status = ConnectorStatusEnum.HEALTHY
            logger.info(
                "OpenMeteoConnector initialized with %d monitored Indian locations.",
                len(self.locations),
            )

    async def stop(self) -> None:
        """Closes the HTTP client and terminates polling."""
        self.is_running = False
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("OpenMeteoConnector stopped.")

    async def health_check(self) -> ConnectorStatusEnum:
        """Performs a live connectivity health check against Open-Meteo."""
        if not self.enabled:
            self.status = ConnectorStatusEnum.DISABLED
            return ConnectorStatusEnum.DISABLED

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
                test_loc = self.locations[0] if self.locations else DEFAULT_INDIAN_LOCATIONS[0]
                params = {
                    "latitude": test_loc["lat"],
                    "longitude": test_loc["lon"],
                    "current": "temperature_2m,weather_code",
                    "timezone": "auto",
                }
                resp = await client.get(self.base_url, params=params)
                if resp.status_code == 200:
                    self.status = ConnectorStatusEnum.HEALTHY
                    return ConnectorStatusEnum.HEALTHY
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
            logger.warning("Open-Meteo health check failed: %s", e)
            self.status = ConnectorStatusEnum.DEGRADED
            return ConnectorStatusEnum.DEGRADED

    async def poll(self) -> List[CanonicalRawEvent]:
        """
        Polls Open-Meteo for real-time meteorological observations across
        all configured Indian monitoring locations. Handles partial failures gracefully.
        """
        if not self.is_running or not self.enabled:
            return []

        events: List[CanonicalRawEvent] = []
        t0 = time.time()
        client = self._client or httpx.AsyncClient(timeout=self.timeout_seconds)
        failed_count = 0

        current_params = (
            "temperature_2m,relative_humidity_2m,apparent_temperature,"
            "precipitation,rain,showers,snowfall,weather_code,cloud_cover,"
            "surface_pressure,wind_speed_10m,wind_gusts_10m"
        )

        for loc in self.locations:
            try:
                params = {
                    "latitude": loc["lat"],
                    "longitude": loc["lon"],
                    "current": current_params,
                    "timezone": "auto",
                }
                resp = await client.get(self.base_url, params=params)

                if resp.status_code == 200:
                    data = resp.json()
                    event = self.parse(data, location_info=loc)
                    if event:
                        events.append(event)
                elif resp.status_code == 429:
                    failed_count += 1
                    self.record_error("Open-Meteo rate limit exceeded (HTTP 429)")
                    self.status = ConnectorStatusEnum.DEGRADED
                    break  # Respect rate limit and pause remaining locations in current cycle
                else:
                    failed_count += 1
                    self.record_error(f"Open-Meteo returned HTTP {resp.status_code} for {loc['city']}")

            except Exception as e:
                failed_count += 1
                self.record_error(f"Error fetching Open-Meteo for {loc.get('city')}: {e}")

        # Evaluate batch status
        if events:
            self.consecutive_failures = 0
            latency_ms = (time.time() - t0) * 1000
            self.record_success(count=len(events), latency_ms=latency_ms)
            if failed_count > 0:
                self.status = ConnectorStatusEnum.DEGRADED
            else:
                self.status = ConnectorStatusEnum.HEALTHY
        else:
            if failed_count > 0:
                self.consecutive_failures += 1
                if self.consecutive_failures >= 3:
                    self.status = ConnectorStatusEnum.ERROR
                else:
                    self.status = ConnectorStatusEnum.DEGRADED

        return events

    def parse(self, raw_data: Any, location_info: Optional[Dict[str, Any]] = None) -> CanonicalRawEvent:
        """
        Transforms an Open-Meteo API response into a strictly typed CanonicalRawEvent.
        Preserves complete provider provenance and query coordinates without fabricating citizen GPS.
        """
        if not isinstance(raw_data, dict):
            raw_data = {"raw": str(raw_data)}

        loc = location_info or {}
        city = loc.get("city") or "Unknown"
        state = loc.get("state") or "India"
        district = loc.get("district") or city
        query_lat = loc.get("lat")
        query_lon = loc.get("lon")

        current = raw_data.get("current", {}) if isinstance(raw_data.get("current"), dict) else {}

        # 1. Meteorological Metrics Extraction
        temp_c = float(current.get("temperature_2m", 25.0) or 25.0)
        apparent_temp_c = float(current.get("apparent_temperature", temp_c) or temp_c)
        humidity_pct = float(current.get("relative_humidity_2m", 50.0) or 50.0)
        precip_mm = float(current.get("precipitation", 0.0) or 0.0)
        rain_mm = float(current.get("rain", 0.0) or 0.0)
        showers_mm = float(current.get("showers", 0.0) or 0.0)
        snowfall_cm = float(current.get("snowfall", 0.0) or 0.0)
        wmo_code = int(current.get("weather_code", 0) or 0)
        cloud_cover_pct = float(current.get("cloud_cover", 0.0) or 0.0)
        pressure_hpa = float(current.get("surface_pressure", 1013.25) or 1013.25)
        wind_speed_kmph = float(current.get("wind_speed_10m", 0.0) or 0.0)
        wind_gusts_kmph = float(current.get("wind_gusts_10m", wind_speed_kmph) or wind_speed_kmph)

        # 2. Condition & SIH Category Mapping
        condition_desc, category = map_openmeteo_wmo_code(
            wmo_code=wmo_code,
            wind_speed_kmph=wind_speed_kmph,
            wind_gusts_kmph=wind_gusts_kmph,
            temp_c=temp_c,
            precip_mm=precip_mm,
        )
        severity = infer_openmeteo_severity(
            wmo_code=wmo_code,
            temp_c=temp_c,
            precip_mm=precip_mm,
            wind_speed_kmph=wind_speed_kmph,
            wind_gusts_kmph=wind_gusts_kmph,
        )

        # 3. Observation Timestamp
        time_str = current.get("time") or datetime.now(timezone.utc).isoformat()
        try:
            # Parse ISO time
            if "T" in time_str:
                observed_at = datetime.fromisoformat(time_str)
                if observed_at.tzinfo is None:
                    observed_at = observed_at.replace(tzinfo=timezone.utc)
            else:
                observed_at = datetime.now(timezone.utc)
        except Exception:
            observed_at = datetime.now(timezone.utc)

        # 4. Structured Informative Narrative Text
        text = (
            f"Open-Meteo meteorological observation for {city}, {state} ({query_lat:.4f}°N, {query_lon:.4f}°E): "
            f"{condition_desc}. Temperature: {temp_c:.1f}°C (feels like {apparent_temp_c:.1f}°C), "
            f"Humidity: {humidity_pct:.0f}%, Wind: {wind_speed_kmph:.1f} km/h (gusts: {wind_gusts_kmph:.1f} km/h), "
            f"Precipitation: {precip_mm:.1f} mm, Pressure: {pressure_hpa:.1f} hPa. (WMO: {wmo_code})"
        )

        # 5. Deterministic Idempotency Key
        idemp_payload = f"{city}:{time_str}:{temp_c}:{wmo_code}:{precip_mm}:{wind_speed_kmph}"
        idemp_hash = hashlib.sha256(idemp_payload.encode("utf-8")).hexdigest()[:16]
        idempotency_key = f"openmeteo:{city.lower().replace(' ', '_')}:{idemp_hash}"
        external_id = f"openmeteo-{city.lower().replace(' ', '-')}-{time_str}"

        # 6. Provenance & Metrics Envelope
        raw_payload = {
            "provider": "Open-Meteo",
            "provider_type": "THIRD_PARTY_WEATHER_API",
            "is_official_government": False,
            "query_coordinates": {"latitude": query_lat, "longitude": query_lon},
            "model_coordinates": {
                "latitude": raw_data.get("latitude"),
                "longitude": raw_data.get("longitude"),
            },
            "elevation_m": raw_data.get("elevation"),
            "timezone": raw_data.get("timezone"),
            "wmo_code": wmo_code,
            "condition_description": condition_desc,
            "extracted_metrics": {
                "temperature_c": temp_c,
                "apparent_temperature_c": apparent_temp_c,
                "humidity_pct": humidity_pct,
                "precipitation_mm": precip_mm,
                "rain_mm": rain_mm,
                "showers_mm": showers_mm,
                "snowfall_cm": snowfall_cm,
                "cloud_cover_pct": cloud_cover_pct,
                "surface_pressure_hpa": pressure_hpa,
                "wind_speed_kmph": wind_speed_kmph,
                "wind_gusts_kmph": wind_gusts_kmph,
            },
            "raw_response": raw_data,
        }

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type=SourceType.WEATHER_API.value,
            external_id=external_id,
            text=text,
            latitude=query_lat,
            longitude=query_lon,
            city=city,
            district=district,
            state=state,
            observed_at=observed_at,
            suggested_category=category,
            severity=severity,
            raw_payload=raw_payload,
            is_india_valid=True,
            is_demo=False,
            idempotency_key=idempotency_key,
        )


openmeteo_connector = OpenMeteoConnector()
