import time
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

from connectors.base import BaseConnector
from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum

logger = logging.getLogger("skypulse.connectors.rss")


class RSSFeedConnector(BaseConnector):
    """
    Standardized RSS/Atom weather alert feed connector.
    Parses XML syndication feeds from authorized news agencies and meteorological portals.
    """

    def __init__(
        self,
        source_id: str,
        name: str = "Weather Alerts RSS Feed",
        feed_url: Optional[str] = None,
    ):
        super().__init__(
            source_id=source_id,
            name=name,
            source_type="RSS_FEED",
            config={"feed_url": feed_url},
            is_demo=False,
        )
        self.feed_url = feed_url
        self.status = ConnectorStatusEnum.HEALTHY if feed_url else ConnectorStatusEnum.NOT_CONFIGURED

    async def poll(self) -> List[CanonicalRawEvent]:
        if not self.feed_url:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return []

        t0 = time.time()
        events: List[CanonicalRawEvent] = []

        headers = {"User-Agent": "SkyPulse-WeatherAnalytics/1.0 (+https://skypulse.gov.in)"}
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                resp = await client.get(self.feed_url)
                if resp.status_code == 200:
                    events = self._parse_feed_xml(resp.text)
                    self.record_success(len(events), (time.time() - t0) * 1000)
                else:
                    self.record_error(f"RSS Feed HTTP status {resp.status_code}")
        except Exception as e:
            self.record_error(e)

        return events

    def _parse_feed_xml(self, xml_text: str) -> List[CanonicalRawEvent]:
        events = []
        try:
            root = ET.fromstring(xml_text)
            # Find channel items (RSS 2.0)
            items = root.findall(".//item")
            if not items:
                # Atom feed fallback
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

            for item in items:
                event = self.parse(item)
                if event:
                    events.append(event)
        except Exception as e:
            logger.error("XML parse error on RSS feed: %s", e)
            self.record_error(e)

        return events

    def parse(self, item_elem: Any) -> Optional[CanonicalRawEvent]:
        title = ""
        description = ""
        guid = ""

        # RSS 2.0 tags
        t_el = item_elem.find("title")
        if t_el is not None and t_el.text:
            title = t_el.text.strip()

        d_el = item_elem.find("description")
        if d_el is not None and d_el.text:
            description = d_el.text.strip()

        g_el = item_elem.find("guid")
        if g_el is not None and g_el.text:
            guid = g_el.text.strip()

        if not title and not description:
            return None

        clean_text = f"{title}. {description}".strip(". ")

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type="RSS_FEED",
            external_id=guid or f"rss-{abs(hash(clean_text))}",
            text=clean_text,
            raw_payload={"title": title, "description": description, "guid": guid},
            is_demo=False,
        )
