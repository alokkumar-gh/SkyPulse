"""
SkyPulse News Website Ingestion Layer (RSS-First)
=================================================
Discovers and ingests weather-related content from verified Indian news publishers
and official government press release RSS feeds (PIB & DD News).

Strategy Priority:
1. Official RSS/Atom feeds (PIB, DD News, Verified Indian National Publishers)
2. Public sitemap/news feeds where authorized
3. Weather relevance keyword & semantic filtering (Strictly discards non-weather press releases)

Canonical Pipeline Integration:
CanonicalRawEvent -> Normalization -> India Validation -> Idempotency/Dedup -> AI Classification -> Verification -> Source Trust -> WeatherEvent/DWEG
"""

import asyncio
import email.utils
import hashlib
import html
import logging
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.models.enums import SourceType, WeatherCategory
from connectors.base import BaseConnector, sanitize_error_message
from connectors.idempotency import idempotency_service
from connectors.normalizer import enrich_location, normalize_category, sanitize_text
from connectors.schema import (
    CanonicalRawEvent,
    ConnectorMetrics,
    ConnectorStatusEnum,
    MediaItem,
)

logger = logging.getLogger("skypulse.connectors.news_website")

CONNECTOR_NAME = "News Website & Government Press Ingestion Layer"
CONNECTOR_VERSION = "1.1.0"
DEFAULT_SOURCE_ID = "00000000-0000-0000-0000-000000000004"

# Weather relevance keywords for filtering PIB / news items
WEATHER_RELEVANCE_KEYWORDS = [
    "rain",
    "rainfall",
    "thunderstorm",
    "lightning",
    "storm",
    "cyclone",
    "flood",
    "flooding",
    "heatwave",
    "heat wave",
    "fog",
    "dense fog",
    "dust storm",
    "strong winds",
    "gale",
    "squall",
    "weather warning",
    "meteorological",
    "imd",
    "monsoon",
    "drought",
    "cloudburst",
    "landslide",
    "heavy precipitation",
    "depression",
    "deep depression",
    "cold wave",
    "frost",
    "hailstorm",
    "sea condition",
]

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ocid", "ref", "ref_src", "amp", "amp_js_v", "s", "source"
}


def normalize_canonical_url(url: str) -> str:
    """Strips query tracking parameters and fragment identifiers to prevent duplicate records."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        qs = parse_qs(parsed.query)
        cleaned_qs = {k: v for k, v in qs.items() if k.lower() not in TRACKING_PARAMS}
        new_query = urlencode(cleaned_qs, doseq=True)
        return urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            new_query,
            "",
        ))
    except Exception:
        return url.strip()


def parse_publication_timestamp(raw_date_str: Optional[str]) -> Optional[datetime]:
    """Parses RFC 822/2822, ISO 8601, and common date formats into UTC datetime."""
    if not raw_date_str:
        return None

    raw = raw_date_str.strip()
    # 1. Try RFC 822 / RFC 2822 (e.g., 'Tue, 02 Oct 2026 10:30:00 +0530')
    try:
        dt = email.utils.parsedate_to_datetime(raw)
        if dt:
            return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # 2. Try ISO 8601
    try:
        iso_clean = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_clean)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # 3. Common fallback format patterns
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%d %b %Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw[:19], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue

    return None


def is_weather_relevant(title: str, summary: str) -> Tuple[bool, List[str]]:
    """
    Checks if an article's title or summary contains explicit meteorological/weather content.
    Returns (is_relevant, matched_keywords).
    """
    text = f"{title} {summary}".lower()
    matched = []
    for kw in WEATHER_RELEVANCE_KEYWORDS:
        # Match whole words or clean prefixes
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            matched.append(kw)

    return (len(matched) > 0, matched)


def sanitize_rss_xml(xml_text: str) -> str:
    """Cleans up XML text, removes BOMs, fixes unescaped ampersands, and handles entities."""
    if not xml_text:
        return ""
    # Strip UTF-8/UTF-16 BOM and whitespace
    cleaned = xml_text.lstrip("\ufeff\ufffe \t\r\n")
    # Fix naked ampersands that are not valid entities
    cleaned = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", cleaned)
    return cleaned


class NewsArticleItem(BaseModel):
    """Raw standardized news item discovered across official RSS feeds or public pages."""
    publisher: str
    title: str
    canonical_url: str
    author: Optional[str] = None
    department: Optional[str] = None
    published_at: Optional[datetime] = None
    summary: str = ""
    media_urls: List[str] = Field(default_factory=list)
    source_feed_url: str = ""
    strategy_used: str = "RSS_FEED"
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class NewsSourceDefinition(BaseModel):
    """Configuration-driven definition of an Indian news or weather publisher."""
    source_id: str
    publisher_name: str
    domains: List[str]
    feed_urls: List[str] = Field(default_factory=list)
    article_category_urls: List[str] = Field(default_factory=list)
    source_type: str = "NEWS"  # NEWS, GOVERNMENT_MEDIA, WEATHER_PORTAL
    is_required: bool = False  # If false, errors keep it optional/degraded
    enabled: bool = True
    polling_interval_seconds: int = 180
    status: ConnectorStatusEnum = ConnectorStatusEnum.HEALTHY

    model_config = ConfigDict(from_attributes=True)


# Official RSS feeds for PIB, DD News, and verified Indian publishers
DEFAULT_NEWS_SOURCES: List[NewsSourceDefinition] = [
    NewsSourceDefinition(
        source_id="pib-india",
        publisher_name="Press Information Bureau (PIB)",
        domains=["pib.gov.in", "www.pib.gov.in"],
        feed_urls=[
            "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&reg=3",
            "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1",
            "https://pib.gov.in/RssMain.aspx?ModId=1&Lang=1",
        ],
        source_type="GOVERNMENT_MEDIA",
        is_required=True,
        enabled=True,
        polling_interval_seconds=180,
    ),
    NewsSourceDefinition(
        source_id="dd-news",
        publisher_name="DD News",
        domains=["ddnews.gov.in"],
        feed_urls=[
            "https://ddnews.gov.in/feed/",
            "https://ddnews.gov.in/en/feed/",
        ],
        source_type="GOVERNMENT_MEDIA",
        is_required=False,  # Optional: connection resets on ddnews will not fail the pipeline
        enabled=True,
        polling_interval_seconds=300,
    ),
    NewsSourceDefinition(
        source_id="the-hindu",
        publisher_name="The Hindu",
        domains=["thehindu.com", "www.thehindu.com"],
        feed_urls=["https://www.thehindu.com/news/national/feeder/default.rss"],
        source_type="NEWS",
        is_required=False,
        enabled=True,
        polling_interval_seconds=180,
    ),
    NewsSourceDefinition(
        source_id="ndtv-india",
        publisher_name="NDTV",
        domains=["ndtv.com", "www.ndtv.com"],
        feed_urls=["https://feeds.feedburner.com/ndtvnews-india-news"],
        source_type="NEWS",
        is_required=False,
        enabled=True,
        polling_interval_seconds=180,
    ),
    NewsSourceDefinition(
        source_id="times-of-india",
        publisher_name="Times of India",
        domains=["timesofindia.indiatimes.com"],
        feed_urls=["https://timesofindia.indiatimes.com/rssfeedstopstories.cms"],
        source_type="NEWS",
        is_required=False,
        enabled=True,
        polling_interval_seconds=180,
    ),
]


class NewsSourceRegistry:
    """Registry managing configurable Indian news/weather sources and adapters."""

    def __init__(self, initial_sources: Optional[List[NewsSourceDefinition]] = None):
        self._sources: Dict[str, NewsSourceDefinition] = {}
        for s in (initial_sources or DEFAULT_NEWS_SOURCES):
            self.register_source(s)

    def register_source(self, source: NewsSourceDefinition) -> None:
        self._sources[source.source_id] = source

    def get_source(self, source_id: str) -> Optional[NewsSourceDefinition]:
        return self._sources.get(source_id)

    def get_all_sources(self) -> List[NewsSourceDefinition]:
        return list(self._sources.values())

    def get_enabled_sources(self) -> List[NewsSourceDefinition]:
        return [s for s in self._sources.values() if s.enabled]


class NewsWebsiteConnector(BaseConnector):
    """
    Dedicated RSS-first News Website & Government Press Ingestion Layer for SkyPulse.
    Ingests official PIB RSS releases, parses XML with robust sanitization,
    and applies strict weather relevance filtering before canonical normalization.
    """

    def __init__(
        self,
        source_id: str = DEFAULT_SOURCE_ID,
        name: str = CONNECTOR_NAME,
        registry: Optional[NewsSourceRegistry] = None,
        config: Optional[Dict[str, Any]] = None,
        is_demo: bool = False,
    ):
        super().__init__(
            source_id=source_id,
            name=name,
            source_type=SourceType.GOVERNMENT_DATASET.value,  # PIB is Government Media
            config=config or {},
            is_demo=is_demo,
        )
        self.registry = registry or NewsSourceRegistry()
        self.user_agent = getattr(
            settings, "NEWS_USER_AGENT", "SkyPulse-NationalWeatherAnalytics/1.0 (+https://skypulse.gov.in)"
        )
        self.timeout = getattr(settings, "NEWS_REQUEST_TIMEOUT_SECONDS", 10.0)
        self.max_articles_per_feed = getattr(settings, "NEWS_MAX_ARTICLES_PER_FEED", 25)
        self._seen_urls: Set[str] = set()

        # Telemetry
        self.sources_configured_count: int = len(self.registry.get_all_sources())
        self.sources_healthy_count: int = 0
        self.sources_failed_count: int = 0
        self.feeds_polled_count: int = 0
        self.pib_rss_reachable: bool = False
        self.pib_xml_valid: bool = False
        self.weather_items_found: int = 0

    async def health_check(self) -> ConnectorStatusEnum:
        if not getattr(settings, "NEWS_INGESTION_ENABLED", True):
            self.status = ConnectorStatusEnum.DISABLED
            return ConnectorStatusEnum.DISABLED
        if not self.is_running:
            return ConnectorStatusEnum.DISABLED

        enabled_sources = self.registry.get_enabled_sources()
        if not enabled_sources:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return ConnectorStatusEnum.NOT_CONFIGURED

        if self.consecutive_failures >= 3:
            self.status = ConnectorStatusEnum.UNAVAILABLE
        elif self.consecutive_failures > 0:
            self.status = ConnectorStatusEnum.DEGRADED
        else:
            self.status = ConnectorStatusEnum.HEALTHY

        return self.status

    def parse(self, raw_data: Any) -> Optional[CanonicalRawEvent]:
        """
        Converts a NewsArticleItem into a CanonicalRawEvent IF AND ONLY IF it is weather-relevant.
        Preserves government/news attribution and sets proper source provenance.
        """
        if not isinstance(raw_data, NewsArticleItem):
            return None

        full_text = f"{raw_data.title}. {raw_data.summary}".strip()
        sanitized = sanitize_text(full_text)
        if not sanitized:
            return None

        # 1. Weather Relevance Filter (Mandatory Phase 3 Requirement)
        is_relevant, matched_keywords = is_weather_relevant(
            title=raw_data.title,
            summary=raw_data.summary,
        )
        if not is_relevant:
            # Reject non-weather press releases / articles
            return None

        self.weather_items_found += 1

        # 2. India Location Extraction & Zero Fake GPS
        lat, lon, city, district, state, loc_source, loc_conf, is_india, is_quar, quar_reason = enrich_location(
            lat=None,
            lon=None,
            text=full_text,
        )

        # 3. Media Items
        media_items = [MediaItem(media_type="IMAGE", url=u) for u in raw_data.media_urls]

        # 4. Canonical Category
        category = normalize_category(None, full_text)

        # 5. Canonical URL
        canonical_url = normalize_canonical_url(raw_data.canonical_url)
        observed_at = raw_data.published_at or datetime.now(timezone.utc)

        # 6. Provenance & Source Trust
        is_pib = "PIB" in raw_data.publisher or "Press Information Bureau" in raw_data.publisher
        source_type_val = SourceType.GOVERNMENT_DATASET.value if is_pib else SourceType.RSS_FEED.value


        raw_payload = {
            "publisher": raw_data.publisher,
            "department": raw_data.department,
            "article_title": raw_data.title,
            "canonical_url": canonical_url,
            "author_byline": raw_data.author,
            "publication_timestamp": observed_at.isoformat(),
            "discovered_timestamp": datetime.now(timezone.utc).isoformat(),
            "article_snippet_text": raw_data.summary,
            "media_urls": raw_data.media_urls,
            "matched_weather_keywords": matched_keywords,
            "source_feed_url": raw_data.source_feed_url,
            "strategy_used": raw_data.strategy_used,
            "is_official_government": is_pib,
            "dbt_evidence_type": "OFFICIAL_PRESS_RELEASE" if is_pib else "NEWS_ARTICLE",
        }

        # Idempotency key from URL and sanitized text
        idempotency_key = idempotency_service.compute_key(
            source_id=self.source_id,
            external_id=canonical_url,
            text=sanitized,
            observed_at=observed_at,
            latitude=lat,
            longitude=lon,
        )

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type=source_type_val,
            external_id=canonical_url,
            observed_at=observed_at,
            ingested_at=datetime.now(timezone.utc),
            text=sanitized,
            latitude=lat,
            longitude=lon,
            city=city,
            district=district,
            state=state,
            location_source=loc_source,
            location_confidence=loc_conf,
            is_india_valid=is_india,
            is_quarantined=is_quar,
            quarantine_reason=quar_reason,
            suggested_category=category,
            severity=2,
            media=media_items,
            raw_payload=raw_payload,
            is_demo=self.is_demo,
            idempotency_key=idempotency_key,
        )

    async def poll(self) -> List[CanonicalRawEvent]:
        """
        Polls configured official RSS feeds with bounded backoff and non-blocking failure handling.
        """
        t0 = time.time()
        self.metrics.last_poll_at = datetime.now(timezone.utc)
        self.last_attempt_at = datetime.now(timezone.utc)

        if not getattr(settings, "NEWS_INGESTION_ENABLED", True):
            self.status = ConnectorStatusEnum.DISABLED
            return []

        enabled_sources = self.registry.get_enabled_sources()
        self.sources_configured_count = len(self.registry.get_all_sources())

        if not enabled_sources:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return []

        discovered_articles: List[NewsArticleItem] = []
        healthy_sources = 0
        failed_sources = 0

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            for source in enabled_sources:
                source_success = False
                source_items: List[NewsArticleItem] = []

                for feed_url in source.feed_urls:
                    self.feeds_polled_count += 1
                    try:
                        resp = await client.get(feed_url)
                        if resp.status_code == 200:
                            items, xml_valid = self._parse_feed_xml(resp.text, source, feed_url)
                            if source.source_id == "pib-india":
                                self.pib_rss_reachable = True
                                self.pib_xml_valid = xml_valid
                            source_items.extend(items)
                            source_success = True
                            break  # Success on primary feed for this source
                        elif resp.status_code == 429:
                            self.metrics.rate_limits += 1
                            logger.warning("Rate limit HTTP 429 on %s", feed_url)
                        elif resp.status_code in (401, 403):
                            logger.warning("Access HTTP %s on %s (skipping scraping bypass)", resp.status_code, feed_url)
                        else:
                            logger.debug("Feed %s returned HTTP %s", feed_url, resp.status_code)
                    except Exception as e:
                        clean_err = sanitize_error_message(str(e))
                        logger.debug("Error fetching feed %s: %s", feed_url, clean_err)

                if source_success:
                    healthy_sources += 1
                    source.status = ConnectorStatusEnum.HEALTHY
                else:
                    failed_sources += 1
                    source.status = ConnectorStatusEnum.DEGRADED

                discovered_articles.extend(source_items)

        self.sources_healthy_count = healthy_sources
        self.sources_failed_count = failed_sources

        # Process through canonical pipeline & update telemetry
        cycle_fetched = len(discovered_articles)
        cycle_weather_rel = 0
        cycle_accepted_india = 0
        cycle_quar_foreign = 0
        cycle_quar_unknown = 0
        cycle_rejected_non_weather = 0
        cycle_duplicates = 0

        canonical_events: List[CanonicalRawEvent] = []

        for article in discovered_articles:
            raw_event = self.parse(article)
            if raw_event is None:
                cycle_rejected_non_weather += 1
                continue

            cycle_weather_rel += 1

            if article.canonical_url in self._seen_urls:
                cycle_duplicates += 1
            self._seen_urls.add(article.canonical_url)

            if raw_event.is_india_valid and not raw_event.is_quarantined:
                cycle_accepted_india += 1
                canonical_events.append(raw_event)
            elif raw_event.is_quarantined:
                if raw_event.quarantine_reason == "FOREIGN_COORDINATES":
                    cycle_quar_foreign += 1
                else:
                    cycle_quar_unknown += 1

        self.metrics.records_fetched += cycle_fetched
        self.metrics.rejected_non_weather += cycle_rejected_non_weather
        self.metrics.weather_relevant += cycle_weather_rel
        self.metrics.accepted_india += cycle_accepted_india
        self.metrics.accepted_for_pipeline += cycle_accepted_india
        self.metrics.records_accepted += cycle_accepted_india
        self.metrics.quarantined_foreign += cycle_quar_foreign
        self.metrics.quarantined_unknown_location += cycle_quar_unknown
        self.metrics.duplicates += cycle_duplicates

        latency = (time.time() - t0) * 1000
        self.metrics.processing_latency_ms = round(latency, 2)

        if healthy_sources > 0:
            self.consecutive_failures = 0
            self.is_reachable = True
            self.status = ConnectorStatusEnum.HEALTHY
            if cycle_accepted_india > 0:
                self.record_success(count=cycle_accepted_india, latency_ms=latency)
        else:
            self.consecutive_failures += 1
            self.status = ConnectorStatusEnum.DEGRADED
            self.record_error("No configured RSS feeds were reachable this cycle", "FEEDS_UNREACHABLE")

        return canonical_events

    def _parse_feed_xml(
        self, xml_text: str, source: NewsSourceDefinition, feed_url: str
    ) -> Tuple[List[NewsArticleItem], bool]:
        """Parses RSS 2.0 or Atom XML feed with sanitization. Returns (items, is_valid_xml)."""
        items: List[NewsArticleItem] = []
        if not xml_text:
            return items, False

        try:
            sanitized_xml = sanitize_rss_xml(xml_text)
            root = ET.fromstring(sanitized_xml.encode("utf-8"))

            # RSS 2.0 items
            rss_items = root.findall(".//item")
            if rss_items:
                for elem in rss_items[: self.max_articles_per_feed]:
                    t_el = elem.find("title")
                    l_el = elem.find("link")
                    d_el = elem.find("description")
                    pub_el = elem.find("pubDate")
                    author_el = elem.find("author") or elem.find(".//{http://purl.org/dc/elements/1.1/}creator")
                    cat_el = elem.find("category")

                    title = html.unescape(t_el.text.strip()) if t_el is not None and t_el.text else ""
                    raw_link = l_el.text.strip() if l_el is not None and l_el.text else ""
                    desc = html.unescape(d_el.text.strip()) if d_el is not None and d_el.text else ""
                    author = author_el.text.strip() if author_el is not None and author_el.text else None
                    dept = cat_el.text.strip() if cat_el is not None and cat_el.text else None

                    if not title and not desc:
                        continue

                    # Media attachments
                    media = []
                    enc = elem.find("enclosure")
                    if enc is not None and enc.get("url"):
                        media.append(enc.get("url"))
                    media_content = elem.find(".//{http://search.yahoo.com/mrss/}content")
                    if media_content is not None and media_content.get("url"):
                        media.append(media_content.get("url"))

                    clean_url = normalize_canonical_url(raw_link)
                    pub_dt = parse_publication_timestamp(pub_el.text if pub_el is not None else None)

                    # Strip HTML tags from summary
                    clean_summary = re.sub(r"<[^>]+>", " ", desc)
                    clean_summary = " ".join(clean_summary.split())

                    items.append(
                        NewsArticleItem(
                            publisher=source.publisher_name,
                            title=title or "Official Press Release",
                            canonical_url=clean_url or feed_url,
                            author=author,
                            department=dept,
                            published_at=pub_dt,
                            summary=clean_summary,
                            media_urls=media,
                            source_feed_url=feed_url,
                            strategy_used="RSS_FEED",
                            raw_metadata={"feed_url": feed_url, "department": dept},
                        )
                    )
                return items, True

            # Atom 1.0 entries
            atom_entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            if atom_entries:
                for entry in atom_entries[: self.max_articles_per_feed]:
                    t_el = entry.find("{http://www.w3.org/2005/Atom}title")
                    l_el = entry.find("{http://www.w3.org/2005/Atom}link")
                    s_el = entry.find("{http://www.w3.org/2005/Atom}summary") or entry.find("{http://www.w3.org/2005/Atom}content")
                    pub_el = entry.find("{http://www.w3.org/2005/Atom}published") or entry.find("{http://www.w3.org/2005/Atom}updated")

                    title = html.unescape(t_el.text.strip()) if t_el is not None and t_el.text else ""
                    raw_link = l_el.get("href", "") if l_el is not None else ""
                    summary = html.unescape(s_el.text.strip()) if s_el is not None and s_el.text else ""

                    if not title and not summary:
                        continue

                    clean_url = normalize_canonical_url(raw_link)
                    pub_text = pub_el.text.strip() if pub_el is not None and pub_el.text else None
                    pub_dt = parse_publication_timestamp(pub_text)
                    clean_summary = " ".join(re.sub(r"<[^>]+>", " ", summary).split())

                    items.append(
                        NewsArticleItem(
                            publisher=source.publisher_name,
                            title=title or "Weather Update",
                            canonical_url=clean_url or feed_url,
                            published_at=pub_dt,
                            summary=clean_summary,
                            source_feed_url=feed_url,
                            strategy_used="ATOM_FEED",
                        )
                    )
                return items, True

        except Exception as e:
            logger.debug("Failed parsing XML from %s: %s", feed_url, e)

        return items, False


# Global singleton instance
news_website_connector = NewsWebsiteConnector()
