import uuid
import random
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector
from connectors.schema import CanonicalRawEvent, MediaItem, ConnectorStatusEnum
from connectors.normalizer import INDIAN_CITIES_REFERENCE

# Detailed descriptive templates per category
DEMO_TEMPLATES = {
    "RAINFALL": [
        "Heavy monsoon downpour recorded over {city} with continuous rainfall for the past 3 hours.",
        "Moderate rain showers observed across {district}, temperature dropped to 24°C.",
        "Sudden intense cloudburst in {city}, visibility reduced to under 500 meters.",
    ],
    "THUNDERSTORM": [
        "Severe thunderstorm with frequent lightning strikes and thunderclaps reported near {city}.",
        "Squall and thunderstorm passing over {district}, gusty winds reported.",
        "Active thunderstorm cell detected over {city} with localized heavy rain.",
    ],
    "FLOODING": [
        "Low-lying streets submerged in knee-deep water near main market area of {city}.",
        "Waterlogging reported across major underpasses in {district} due to continuous rains.",
        "River water levels rising rapidly in {city}, local authorities issuing precautionary alerts.",
    ],
    "HEATWAVE": [
        "Severe heatwave conditions persisting in {city}, afternoon temperature exceeded 44.5°C.",
        "Extreme dry heat and loo winds blowing across {district}, citizens advised to stay indoors.",
        "Heat index reached dangerous levels in {city} with high humidity and soaring temperatures.",
    ],
    "FOG": [
        "Dense radiation fog enveloped {city} during morning hours, airport runway visibility dropped below 150m.",
        "Shallow to moderate fog blanketed {district} leading to slow morning traffic.",
        "Heavy winter fog reducing visibility on highways around {city}.",
    ],
    "DUST_STORM": [
        "Blinding dust storm swept across {city} reducing visibility and darkening the sky.",
        "Strong dust winds and hazy conditions observed in {district}.",
        "High-velocity dust squall impacted transportation in {city}.",
    ],
    "STRONG_WINDS": [
        "Gale force winds up to 75 km/h recorded in coastal areas of {city}.",
        "Strong winds caused minor tree branch fall and power fluctuations in {district}.",
        "Squally winds gusting up to 60 km/h across {city}.",
    ],
}


class DemoConnector(BaseConnector):
    """
    Synthetic Indian weather stream generator for hackathon demonstrations,
    stress testing, and continuous simulation.
    Generates all 7 problem statement weather categories with realistic spatial distributions.
    """

    def __init__(
        self,
        source_id: Optional[str] = None,
        name: str = "Demo Synthetic Weather Stream",
        scenario: str = "mixed_national",
        rate_seconds: int = 10,
    ):
        super().__init__(
            source_id=source_id or str(uuid.uuid4()),
            name=name,
            source_type="DEMO",
            config={"scenario": scenario, "rate_seconds": rate_seconds},
            is_demo=True,
        )
        self.scenario = scenario
        self.rate_seconds = rate_seconds
        self.status = ConnectorStatusEnum.DEMO
        self._last_event: Optional[CanonicalRawEvent] = None

    def parse(self, raw_data: Any) -> CanonicalRawEvent:
        if isinstance(raw_data, CanonicalRawEvent):
            return raw_data
        return CanonicalRawEvent(**raw_data)

    async def poll(self) -> List[CanonicalRawEvent]:
        """Generate a batch of events according to the configured scenario."""
        t0 = time.time()
        events: List[CanonicalRawEvent] = []

        if self.scenario == "burst":
            # Generate a burst of 10 events
            for _ in range(10):
                events.append(self._generate_single_event())
        elif self.scenario == "storm_cluster":
            # Clustered events around Mumbai or Kolkata
            anchor_city = random.choice(["mumbai", "kolkata"])
            for _ in range(5):
                cat = random.choice(["THUNDERSTORM", "RAINFALL", "STRONG_WINDS"])
                events.append(self._generate_single_event(city_key=anchor_city, forced_category=cat))
        elif self.scenario == "flood_cluster":
            # Clustered flood events
            anchor_city = random.choice(["guwahati", "kochi", "mumbai"])
            for _ in range(5):
                events.append(self._generate_single_event(city_key=anchor_city, forced_category="FLOODING"))
        else:
            # Normal or mixed_national: 1 to 3 events across India
            count = random.randint(1, 3)
            for _ in range(count):
                # 10% chance of generating a duplicate of the last event to test idempotency
                if self._last_event and random.random() < 0.10:
                    events.append(self._create_duplicate(self._last_event))
                else:
                    events.append(self._generate_single_event())

        latency_ms = (time.time() - t0) * 1000
        self.record_success(len(events), latency_ms)
        if events:
            self._last_event = events[-1]
        return events

    def _generate_single_event(
        self,
        city_key: Optional[str] = None,
        forced_category: Optional[str] = None,
    ) -> CanonicalRawEvent:
        if not city_key or city_key not in INDIAN_CITIES_REFERENCE:
            city_key = random.choice(list(INDIAN_CITIES_REFERENCE.keys()))
        ref = INDIAN_CITIES_REFERENCE[city_key]

        category = forced_category or random.choice(list(DEMO_TEMPLATES.keys()))
        template = random.choice(DEMO_TEMPLATES[category])
        text = template.format(city=ref["city"], district=ref["district"])

        # Jitter coordinates slightly (+/- 0.05 deg, ~5 km)
        lat = round(ref["lat"] + random.uniform(-0.04, 0.04), 4)
        lon = round(ref["lon"] + random.uniform(-0.04, 0.04), 4)

        severity_map = {
            "RAINFALL": random.choice([1, 2, 3]),
            "THUNDERSTORM": random.choice([2, 3]),
            "FLOODING": random.choice([2, 3, 4]),
            "HEATWAVE": random.choice([2, 3]),
            "FOG": random.choice([1, 2]),
            "DUST_STORM": random.choice([2, 3]),
            "STRONG_WINDS": random.choice([2, 3, 4]),
        }
        severity = severity_map.get(category, 2)

        media = []
        if random.random() < 0.3:
            media.append(
                MediaItem(
                    media_type="IMAGE",
                    url=f"/media/demo/weather_{category.lower()}_{uuid.uuid4().hex[:6]}.jpg",
                    mime_type="image/jpeg",
                )
            )

        now = datetime.now(timezone.utc)
        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type="DEMO",
            external_id=f"demo-{uuid.uuid4().hex[:12]}",
            observed_at=now,
            ingested_at=now,
            text=text,
            latitude=lat,
            longitude=lon,
            city=ref["city"],
            district=ref["district"],
            state=ref["state"],
            suggested_category=category,
            severity=severity,
            media=media,
            raw_payload={"demo": True, "scenario": self.scenario, "city_key": city_key},
            is_demo=True,
        )

    def _create_duplicate(self, original: CanonicalRawEvent) -> CanonicalRawEvent:
        """Create a duplicate event with identical content and location to test idempotency."""
        now = datetime.now(timezone.utc)
        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type="DEMO",
            external_id=original.external_id,  # Same external id
            observed_at=original.observed_at,
            ingested_at=now,
            text=original.text,
            latitude=original.latitude,
            longitude=original.longitude,
            city=original.city,
            district=original.district,
            state=original.state,
            suggested_category=original.suggested_category,
            severity=original.severity,
            media=original.media,
            raw_payload=original.raw_payload,
            is_demo=True,
        )
