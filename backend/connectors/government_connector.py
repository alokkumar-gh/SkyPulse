import time
import logging
from typing import Any, Dict, List, Optional
import httpx

from connectors.base import BaseConnector
from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum

logger = logging.getLogger("skypulse.connectors.government")


class GovernmentFeedConnector(BaseConnector):
    """
    Ingests official bulletins and advisories from government agencies (e.g. IMD, NDMA).
    Handles structured JSON/GeoJSON advisories and respects official source attribution.
    """

    def __init__(
        self,
        source_id: str,
        name: str = "IMD Official Bulletins",
        feed_url: Optional[str] = None,
        agency_name: str = "India Meteorological Department",
    ):
        super().__init__(
            source_id=source_id,
            name=name,
            source_type="GOVERNMENT_API",
            config={"feed_url": feed_url, "agency": agency_name},
            is_demo=False,
        )
        self.feed_url = feed_url
        self.agency_name = agency_name
        self.status = ConnectorStatusEnum.HEALTHY if feed_url else ConnectorStatusEnum.NOT_CONFIGURED

    async def poll(self) -> List[CanonicalRawEvent]:
        if not self.feed_url:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return []

        t0 = time.time()
        events: List[CanonicalRawEvent] = []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.feed_url)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("advisories", data.get("features", []))
                    for item in items:
                        events.append(self.parse(item))
                    self.record_success(len(events), (time.time() - t0) * 1000)
                else:
                    self.record_error(f"Government feed HTTP {resp.status_code}")
        except Exception as e:
            self.record_error(e)

        return events

    def parse(self, raw_data: Dict[str, Any]) -> CanonicalRawEvent:
        ext_id = raw_data.get("id", raw_data.get("bulletin_id", "gov-adv-001"))
        headline = raw_data.get("headline", raw_data.get("title", "Official Weather Warning"))
        description = raw_data.get("description", headline)
        severity_str = raw_data.get("severity", "MODERATE").upper()

        sev_map = {"MINOR": 1, "MODERATE": 2, "SEVERE": 3, "EXTREME": 4}
        severity = sev_map.get(severity_str, 2)

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type="GOVERNMENT_API",
            external_id=str(ext_id),
            text=f"[{self.agency_name}] {headline}. {description}",
            latitude=raw_data.get("latitude"),
            longitude=raw_data.get("longitude"),
            city=raw_data.get("city"),
            district=raw_data.get("district"),
            state=raw_data.get("state"),
            suggested_category=raw_data.get("hazard_type", "UNKNOWN"),
            severity=severity,
            raw_payload=raw_data,
            is_demo=False,
        )
