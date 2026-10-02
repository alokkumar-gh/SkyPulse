import time
import logging
from typing import Any, Dict, List, Optional
import httpx

from connectors.base import BaseConnector
from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum
from app.core.config import settings

logger = logging.getLogger("skypulse.connectors.weather_api")


class WeatherAPIConnector(BaseConnector):
    """
    Real-world connector integrating with WeatherAPI.com REST endpoints.
    Requires a valid WEATHERAPI_KEY. Gracefully marks status as NOT_CONFIGURED
    if the key is absent.
    """

    BASE_URL = "http://api.weatherapi.com/v1"

    def __init__(
        self,
        source_id: str,
        name: str = "WeatherAPI.com Connector",
        api_key: Optional[str] = None,
        target_cities: Optional[List[str]] = None,
    ):
        super().__init__(
            source_id=source_id,
            name=name,
            source_type="WEATHER_API",
            config={"target_cities": target_cities or ["New Delhi", "Mumbai", "Bengaluru", "Kolkata"]},
            is_demo=False,
        )
        self.api_key = api_key or settings.WEATHERAPI_KEY
        self.target_cities = target_cities or ["New Delhi", "Mumbai", "Bengaluru", "Kolkata"]

        if not self.api_key or not self.api_key.strip():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
        else:
            self.status = ConnectorStatusEnum.HEALTHY

    async def poll(self) -> List[CanonicalRawEvent]:
        if not self.api_key or not self.api_key.strip():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return []

        events: List[CanonicalRawEvent] = []
        t0 = time.time()

        async with httpx.AsyncClient(timeout=10.0) as client:
            for city in self.target_cities:
                try:
                    url = f"{self.BASE_URL}/current.json"
                    params = {"key": self.api_key, "q": city, "aqi": "no"}
                    resp = await client.get(url, params=params)

                    if resp.status_code == 200:
                        raw = resp.json()
                        event = self.parse(raw)
                        events.append(event)
                    elif resp.status_code in (401, 403):
                        self.record_error("Authentication failed: Invalid WeatherAPI Key")
                        self.status = ConnectorStatusEnum.ERROR
                        break
                    else:
                        self.record_error(f"HTTP {resp.status_code} fetching weather for {city}")
                except Exception as e:
                    self.record_error(e)

        latency_ms = (time.time() - t0) * 1000
        if events:
            self.record_success(len(events), latency_ms)
        return events

    def parse(self, raw_data: Dict[str, Any]) -> CanonicalRawEvent:
        loc = raw_data.get("location", {})
        curr = raw_data.get("current", {})
        condition = curr.get("condition", {})

        condition_text = condition.get("text", "")
        temp_c = curr.get("temp_c", "")
        humidity = curr.get("humidity", "")
        wind_kph = curr.get("wind_kph", "")

        text = (
            f"Observed {condition_text} in {loc.get('name')}. "
            f"Temperature: {temp_c}°C, Humidity: {humidity}%, Wind: {wind_kph} km/h."
        )

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type="WEATHER_API",
            external_id=f"weatherapi-{loc.get('name')}-{curr.get('last_updated_epoch')}",
            text=text,
            latitude=loc.get("lat"),
            longitude=loc.get("lon"),
            city=loc.get("name"),
            state=loc.get("region"),
            suggested_category=self._map_condition_to_category(condition_text),
            severity=self._infer_severity(curr),
            raw_payload=raw_data,
            is_demo=False,
        )

    def _map_condition_to_category(self, condition: str) -> str:
        c = condition.lower()
        if "rain" in c or "drizzle" in c or "shower" in c:
            return "RAINFALL"
        if "thunder" in c or "storm" in c:
            return "THUNDERSTORM"
        if "fog" in c or "mist" in c:
            return "FOG"
        if "snow" in c or "blizzard" in c:
            return "SNOWFALL"
        if "wind" in c or "gale" in c:
            return "STRONG_WINDS"
        return "UNKNOWN"

    def _infer_severity(self, curr: Dict[str, Any]) -> int:
        temp = curr.get("temp_c", 25)
        wind = curr.get("wind_kph", 10)
        precip = curr.get("precip_mm", 0)

        if temp > 43 or wind > 70 or precip > 50:
            return 3
        if temp > 38 or wind > 40 or precip > 20:
            return 2
        return 1
