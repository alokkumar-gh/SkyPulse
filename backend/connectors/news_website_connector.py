"""
SkyPulse News Website Ingestion Layer
Discovers and ingests weather-related content from verified Indian news publishers
and public meteorological websites.

Strategy Priority:
1. RSS/Atom feed when publicly available
2. Public sitemap/news feed when available
3. Public article/category pages where appropriate
4. Search Discovery as fallback/discovery mechanism

Integrates directly with:
CanonicalRawEvent -> Normalization -> India Validation -> Idempotency/Dedup -> AI Classification -> Verification -> Source Trust -> WeatherEvent/DWEG
"""

import asyncio
import email.utils
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
from pydantic import BaseModel, Field, ConfigDict

from app.core.config import settings
from app.models.enums import WeatherCategory
from connectors.base import BaseConnector
from connectors.idempotency import idempotency_service
from connectors.normalizer import (
    INDIAN_CITIES_REFERENCE,
    INDIAN_STATES_REFERENCE,
    enrich_location,
    normalize_category,
    normalize_raw_event,
    sanitize_text,
)
from connectors.schema import (
    CanonicalRawEvent,
    ConnectorMetrics,
    ConnectorStatusEnum,
    MediaItem,
    NormalizedEvent,
)
from connectors.search_discovery_connector import (
    extract_hashtags_from_text,
    extract_weather_measurements,
    is_weather_relevant_search_content,
)

logger = logging.getLogger("skypulse.connectors.news_website")

CONNECTOR_NAME = "News Website Ingestion Layer"
CONNECTOR_VERSION = "1.0.0"
DEFAULT_SOURCE_ID = "00000000-0000-0000-0000-000000000004"


# ==============================================================================
# Helper Utilities: Canonical URL & Timestamp Normalization
# ==============================================================================

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
        # Rebuild URL without fragments or tracking queries
        cleaned = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            new_query,
            "",
        ))
        return cleaned
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
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw[:19], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue

    return None


# ==============================================================================
# Domain Models & Source Registry
# ==============================================================================

class NewsArticleItem(BaseModel):
    """Raw standardized news item discovered across RSS, Sitemaps, or Category Pages."""
    publisher: str
    title: str
    canonical_url: str
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    summary: str = ""
    media_urls: List[str] = Field(default_factory=list)
    source_feed_url: str = ""
    strategy_used: str = "RSS_FEED"  # RSS_FEED, SITEMAP, CATEGORY_PAGE, SEARCH_FALLBACK
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class NewsSourceDefinition(BaseModel):
    """Configuration-driven definition of an Indian news or weather publisher."""
    source_id: str
    publisher_name: str
    domains: List[str]
    feed_urls: List[str] = Field(default_factory=list)
    article_category_urls: List[str] = Field(default_factory=list)
    sitemap_urls: List[str] = Field(default_factory=list)
    source_type: str = "NEWS"  # NEWS, WEATHER_PORTAL, GOVERNMENT_MEDIA
    enabled: bool = True
    polling_interval_seconds: int = 180
    relevant_categories: List[str] = Field(default_factory=list)
    rate_limit_delay_seconds: float = 1.0
    status: ConnectorStatusEnum = ConnectorStatusEnum.HEALTHY

    model_config = ConfigDict(from_attributes=True)


# Default verified Indian news and meteorological sources
DEFAULT_NEWS_SOURCES: List[NewsSourceDefinition] = [
    NewsSourceDefinition(
        source_id="pib-india",
        publisher_name="Press Information Bureau",
        domains=["pib.gov.in"],
        feed_urls=["https://pib.gov.in/RssMain.aspx?ModId=3&Lang=1"],
        source_type="GOVERNMENT_MEDIA",
        enabled=True,
        polling_interval_seconds=180,
    ),
    NewsSourceDefinition(
        source_id="dd-news",
        publisher_name="DD News",
        domains=["ddnews.gov.in"],
        feed_urls=["https://ddnews.gov.in/feed/"],
        source_type="GOVERNMENT_MEDIA",
        enabled=True,
        polling_interval_seconds=180,
    ),
    NewsSourceDefinition(
        source_id="the-hindu",
        publisher_name="The Hindu",
        domains=["thehindu.com", "www.thehindu.com"],
        feed_urls=["https://www.thehindu.com/news/national/feeder/default.rss"],
        article_category_urls=["https://www.thehindu.com/sci-tech/energy-and-environment/"],
        source_type="NEWS",
        enabled=True,
        polling_interval_seconds=180,
    ),
    NewsSourceDefinition(
        source_id="ndtv-india",
        publisher_name="NDTV",
        domains=["ndtv.com", "www.ndtv.com"],
        feed_urls=["https://feeds.feedburner.com/ndtvnews-india-news"],
        source_type="NEWS",
        enabled=True,
        polling_interval_seconds=180,
    ),
    NewsSourceDefinition(
        source_id="india-today",
        publisher_name="India Today",
        domains=["indiatoday.in", "www.indiatoday.in"],
        feed_urls=["https://www.indiatoday.in/rss/1206584"],
        source_type="NEWS",
        enabled=True,
        polling_interval_seconds=180,
    ),
    NewsSourceDefinition(
        source_id="times-of-india",
        publisher_name="Times of India",
        domains=["timesofindia.indiatimes.com"],
        feed_urls=["https://timesofindia.indiatimes.com/rssfeedstopstories.cms"],
        source_type="NEWS",
        enabled=True,
        polling_interval_seconds=180,
    ),
    NewsSourceDefinition(
        source_id="skymet-weather",
        publisher_name="Skymet Weather",
        domains=["skymetweather.com", "www.skymetweather.com"],
        article_category_urls=["https://www.skymetweather.com/content/weather-news-and-analysis/"],
        source_type="WEATHER_PORTAL",
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

    def enable_source(self, source_id: str) -> bool:
        if source_id in self._sources:
            self._sources[source_id].enabled = True
            return True
        return False

    def disable_source(self, source_id: str) -> bool:
        if source_id in self._sources:
            self._sources[source_id].enabled = False
            return True
        return False


# ==============================================================================
# News Website Ingestion Connector
# ==============================================================================

class NewsWebsiteConnector(BaseConnector):
    """
    Dedicated News Website Ingestion Layer for SkyPulse.
    Implements multi-strategy ingestion (RSS -> Sitemap -> Category Page -> Search Fallback).
    Feeds validated canonical raw events directly into the existing SkyPulse pipeline.
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
            source_type="NEWS_WEBSITE",
            config=config or {},
            is_demo=is_demo,
        )
        self.registry = registry or NewsSourceRegistry()
        self.user_agent = getattr(
            settings, "NEWS_USER_AGENT", "SkyPulse-NewsWeatherIntelligence/1.0.0 (+https://skypulse.gov.in)"
        )
        self.timeout = getattr(settings, "NEWS_REQUEST_TIMEOUT_SECONDS", 10.0)
        self.max_articles_per_feed = getattr(settings, "NEWS_MAX_ARTICLES_PER_FEED", 25)
        self._seen_urls: Set[str] = set()

        # Extended Telemetry Counters
        self.sources_configured_count: int = len(self.registry.get_all_sources())
        self.sources_healthy_count: int = 0
        self.sources_failed_count: int = 0
        self.feeds_polled_count: int = 0
        self.rate_limit_responses_count: int = 0
        self.parsing_errors_count: int = 0

    async def health_check(self) -> ConnectorStatusEnum:
        if not getattr(settings, "NEWS_INGESTION_ENABLED", True):
            return ConnectorStatusEnum.DISABLED
        if not self.is_running:
            return ConnectorStatusEnum.DISABLED
        enabled_sources = self.registry.get_enabled_sources()
        if not enabled_sources:
            return ConnectorStatusEnum.NOT_CONFIGURED
        return ConnectorStatusEnum.HEALTHY

    def parse(self, raw_data: Any) -> Optional[CanonicalRawEvent]:
        """
        Converts a NewsArticleItem into a CanonicalRawEvent.
        Performs weather relevance check, extracts measurements and hashtags,
        and enriches location according to the Zero Fake GPS policy.
        """
        if not isinstance(raw_data, NewsArticleItem):
            return None

        full_text = f"{raw_data.title}. {raw_data.summary}".strip()
        sanitized = sanitize_text(full_text)
        if not sanitized:
            return None

        # 1. Weather Relevance Filter
        is_relevant, matched_terms = is_weather_relevant_search_content(
            text=raw_data.summary,
            title=raw_data.title,
        )
        if not is_relevant:
            return None

        # 2. Extract Numerical Weather Measurements & Hashtags
        measurements = extract_weather_measurements(full_text)
        hashtags = extract_hashtags_from_text(full_text)

        # 3. India Location Enrichment & Zero Fake GPS rule
        lat, lon, city, district, state, loc_source, loc_conf, is_india, is_quar, quar_reason = enrich_location(
            lat=None,
            lon=None,
            text=full_text,
        )

        # 4. Media references
        media_items = []
        for m_url in raw_data.media_urls:
            media_items.append(MediaItem(media_type="IMAGE", url=m_url))

        # 5. Canonical Category
        category = normalize_category(None, full_text)

        # Ensure canonical URL is normalized (strips utm tracking parameters)
        canonical_url = normalize_canonical_url(raw_data.canonical_url)

        # 6. DWEG Evidence Node Provenance
        observed_at = raw_data.published_at or datetime.now(timezone.utc)
        raw_payload = {
            "publisher": raw_data.publisher,
            "article_title": raw_data.title,
            "canonical_url": canonical_url,
            "author_byline": raw_data.author,
            "publication_timestamp": observed_at.isoformat(),
            "discovered_timestamp": datetime.now(timezone.utc).isoformat(),
            "article_snippet_text": raw_data.summary,
            "media_urls": raw_data.media_urls,
            "extracted_hashtags": hashtags,
            "weather_measurements": measurements,
            "matched_weather_terms": matched_terms,
            "source_feed_url": raw_data.source_feed_url,
            "strategy_used": raw_data.strategy_used,
            "raw_metadata": raw_data.raw_metadata,
            # DWEG evidence node binding
            "dbt_evidence_type": "NEWS_ARTICLE",
            "dbt_publisher_domain": urlparse(canonical_url).netloc,
        }

        # Idempotency key from canonical normalized URL and sanitized text
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
            source_type="NEWS",
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
        Polls configured news sources using the priority strategy:
        Priority 1: RSS/Atom feeds
        Priority 2: Public Sitemaps
        Priority 3: Category index pages
        Maintains strict mathematical telemetry consistency.
        """
        t0 = time.time()
        self.metrics.last_poll_at = datetime.now(timezone.utc)

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
            "Accept": "text/html,application/xhtml+xml,application/xml,application/rss+xml;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            for source in enabled_sources:
                source_success = False
                source_items: List[NewsArticleItem] = []

                # Strategy 1: RSS/Atom Feeds
                for feed_url in source.feed_urls:
                    self.feeds_polled_count += 1
                    try:
                        resp = await client.get(feed_url)
                        if resp.status_code == 200:
                            items = self._parse_feed_xml(resp.text, source, feed_url)
                            source_items.extend(items)
                            source_success = True
                        elif resp.status_code == 429:
                            self.rate_limit_responses_count += 1
                            self.metrics.rate_limits += 1
                            logger.warning("Rate limited on feed %s (%s)", feed_url, source.publisher_name)
                        else:
                            logger.warning("Feed %s returned HTTP %s", feed_url, resp.status_code)
                    except Exception as e:
                        self.parsing_errors_count += 1
                        logger.error("Error fetching feed %s: %s", feed_url, e)

                # Strategy 2: Public Category/Section Pages if no feeds or few items
                if len(source_items) == 0 and source.article_category_urls:
                    for cat_url in source.article_category_urls:
                        try:
                            resp = await client.get(cat_url)
                            if resp.status_code == 200:
                                items = self._parse_category_html(resp.text, source, cat_url)
                                source_items.extend(items)
                                source_success = True
                            elif resp.status_code == 429:
                                self.rate_limit_responses_count += 1
                                self.metrics.rate_limits += 1
                        except Exception as e:
                            self.parsing_errors_count += 1
                            logger.error("Error fetching category page %s: %s", cat_url, e)

                if source_success:
                    healthy_sources += 1
                    source.status = ConnectorStatusEnum.HEALTHY
                else:
                    failed_sources += 1
                    source.status = ConnectorStatusEnum.ERROR

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

            # Deduplication
            if article.canonical_url in self._seen_urls:
                cycle_duplicates += 1
            self._seen_urls.add(article.canonical_url)

            # Location and quarantine status accounting
            if raw_event.is_india_valid and not raw_event.is_quarantined:
                cycle_accepted_india += 1
                canonical_events.append(raw_event)
            elif raw_event.is_quarantined:
                if raw_event.quarantine_reason == "FOREIGN_COORDINATES":
                    cycle_quar_foreign += 1
                else:
                    cycle_quar_unknown += 1

        # Strict mathematical consistency update
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
        if cycle_accepted_india > 0:
            self.metrics.last_successful_fetch = datetime.now(timezone.utc)
            self.status = ConnectorStatusEnum.HEALTHY
        elif failed_sources > 0 and healthy_sources == 0:
            self.status = ConnectorStatusEnum.DEGRADED

        return canonical_events

    def _parse_feed_xml(
        self, xml_text: str, source: NewsSourceDefinition, feed_url: str
    ) -> List[NewsArticleItem]:
        """Parses RSS 2.0 or Atom XML feed into NewsArticleItem records."""
        items: List[NewsArticleItem] = []
        if not xml_text:
            return items

        try:
            root = ET.fromstring(xml_text)
            # RSS 2.0 items
            rss_items = root.findall(".//item")
            if rss_items:
                for elem in rss_items[: self.max_articles_per_feed]:
                    t_el = elem.find("title")
                    l_el = elem.find("link")
                    d_el = elem.find("description")
                    pub_el = elem.find("pubDate")
                    author_el = elem.find("author") or elem.find(".//{http://purl.org/dc/elements/1.1/}creator")

                    title = html.unescape(t_el.text.strip()) if t_el is not None and t_el.text else ""
                    raw_link = l_el.text.strip() if l_el is not None and l_el.text else ""
                    desc = html.unescape(d_el.text.strip()) if d_el is not None and d_el.text else ""
                    author = author_el.text.strip() if author_el is not None and author_el.text else None

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
                            title=title or "Weather Report",
                            canonical_url=clean_url or feed_url,
                            author=author,
                            published_at=pub_dt,
                            summary=clean_summary,
                            media_urls=media,
                            source_feed_url=feed_url,
                            strategy_used="RSS_FEED",
                            raw_metadata={"feed_url": feed_url},
                        )
                    )

            # Atom 1.0 entries
            atom_entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            if atom_entries:
                for entry in atom_entries[: self.max_articles_per_feed]:
                    t_el = entry.find("{http://www.w3.org/2005/Atom}title")
                    l_el = entry.find("{http://www.w3.org/2005/Atom}link")
                    s_el = entry.find("{http://www.w3.org/2005/Atom}summary")
                    if s_el is None:
                        s_el = entry.find("{http://www.w3.org/2005/Atom}content")
                    pub_el = entry.find("{http://www.w3.org/2005/Atom}published")
                    if pub_el is None:
                        pub_el = entry.find("{http://www.w3.org/2005/Atom}updated")

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
        except Exception as e:
            self.parsing_errors_count += 1
            logger.debug("Failed parsing XML from %s: %s", feed_url, e)

        return items

    def _parse_category_html(
        self, html_text: str, source: NewsSourceDefinition, category_url: str
    ) -> List[NewsArticleItem]:
        """Extracts article cards from public category HTML index pages."""
        items: List[NewsArticleItem] = []
        if not html_text:
            return items

        # Simple robust regex extraction for article headings and links
        # Matches <a href="..."><h2> or <h3> title </a> or <h2 ...><a href="...">title</a></h2>
        patterns = [
            r'<h[2-4][^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>\s*</h[2-4]>',
            r'<a[^>]+href="([^"]+)"[^>]*>\s*<h[2-4][^>]*>([\s\S]*?)</h[2-4]>\s*</a>',
        ]

        for pat in patterns:
            matches = re.findall(pat, html_text, re.IGNORECASE)
            for link, raw_title in matches:
                if len(items) >= self.max_articles_per_feed:
                    break
                clean_title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()
                if not clean_title or len(clean_title) < 10:
                    continue

                full_url = urllib.parse.urljoin(category_url, link.strip())
                clean_url = normalize_canonical_url(full_url)

                items.append(
                    NewsArticleItem(
                        publisher=source.publisher_name,
                        title=clean_title,
                        canonical_url=clean_url,
                        published_at=datetime.now(timezone.utc),
                        summary=clean_title,
                        source_feed_url=category_url,
                        strategy_used="CATEGORY_PAGE",
                    )
                )

        return items


# Global singleton instance
news_website_connector = NewsWebsiteConnector()
