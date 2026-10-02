"""
SkyPulse Search Discovery Ingestion Layer (Phase 1)
Discovers publicly indexed social-media posts, weather news articles, and public webpages
via pluggable search providers (DuckDuckGo, SearXNG, Google CSE, Custom).

Integrates seamlessly with:
CanonicalRawEvent -> Normalization -> India Validation -> Deduplication -> AI Classification -> Verification -> Source Trust -> WeatherEvent/DWEG
"""

import asyncio
import html
import logging
import re
import time
import urllib.parse
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, unquote, urlparse

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

logger = logging.getLogger("skypulse.connectors.search_discovery")

CONNECTOR_NAME = "Search Discovery Ingestion Layer"
CONNECTOR_VERSION = "1.0.0"
DEFAULT_SOURCE_ID = "00000000-0000-0000-0000-000000000003"

# Default India Weather Taxonomy Hashtags
DEFAULT_SEARCH_HASHTAGS = [
    "#IMD",
    "#Weather",
    "#WeatherAlert",
    "#HeavyRain",
    "#Rainfall",
    "#Thunderstorm",
    "#Flood",
    "#Heatwave",
    "#Fog",
    "#DustStorm",
    "#StrongWinds",
    "#Cyclone",
    "#Monsoon",
    "#IndiaWeather",
    "#IndianWeather",
    "#Monsoon2026",
    "#MumbaiRain",
    "#DelhiWeather",
    "#OdishaWeather",
    "#BengaluruRain",
    "#HyderabadRain",
    "#KolkataRain",
    "#ChennaiRain",
    "#FloodIndia",
    "#HeatwaveIndia",
]

# Default Indian target regions for location-aware queries
DEFAULT_SEARCH_LOCATIONS = [
    "India",
    "Mumbai",
    "Delhi",
    "Odisha",
    "Assam",
    "Bengaluru",
    "Chennai",
    "Kolkata",
    "Hyderabad",
    "Kerala",
    "Uttarakhand",
    "Himachal Pradesh",
    "Gujarat",
    "Rajasthan",
    "Bihar",
    "Goa",
    "Punjab",
    "Jammu & Kashmir",
]

# Weather category query seeds
DEFAULT_SEARCH_CATEGORIES = [
    "heavy rainfall",
    "IMD warning",
    "weather alert",
    "thunderstorm",
    "flooding",
    "heatwave alert",
    "cyclone warning",
    "dense fog",
    "cloudburst",
    "dust storm",
    "waterlogging",
]

# Known Social Media Domains (Public Search Discovery)
SOCIAL_DOMAINS_MAP = {
    "twitter.com": "X/Twitter",
    "x.com": "X/Twitter",
    "mobile.twitter.com": "X/Twitter",
    "mastodon.social": "Mastodon",
    "mstdn.social": "Mastodon",
    "mstdn.jp": "Mastodon",
    "mastodon.world": "Mastodon",
    "reddit.com": "Reddit",
    "old.reddit.com": "Reddit",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "instagram.com": "Instagram",
    "threads.net": "Threads",
    "bsky.app": "Bluesky",
    "bsky.social": "Bluesky",
    "linkedin.com": "LinkedIn",
    "t.me": "Telegram",
    "telegram.org": "Telegram",
}

# Known News & Meteorological Domains
NEWS_DOMAINS = {
    "ndtv.com",
    "indiatoday.in",
    "thehindu.com",
    "timesofindia.indiatimes.com",
    "indianexpress.com",
    "hindustantimes.com",
    "deccanherald.com",
    "livemint.com",
    "news18.com",
    "zeenews.india.com",
    "firstpost.com",
    "thewire.in",
    "scroll.in",
    "ddnews.gov.in",
    "pib.gov.in",
    "weather.com",
    "accuweather.com",
    "skymetweather.com",
    "mausam.imd.gov.in",
    "imd.gov.in",
    "aninews.in",
    "pti.in",
    "thequint.com",
    "moneycontrol.com",
    "economictimes.indiatimes.com",
}


# ==============================================================================
# Domain Models & Classification
# ==============================================================================

class SearchResult(BaseModel):
    """Raw result item returned by any search discovery provider."""
    title: str
    url: str
    snippet: str = ""
    published_at: Optional[datetime] = None
    author: Optional[str] = None
    source_domain: Optional[str] = None
    source_name: Optional[str] = None
    media_urls: List[str] = Field(default_factory=list)
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


def classify_source_url(url: str) -> Tuple[str, str, str]:
    """
    Classifies a discovered URL into source_type and source_platform.
    Returns: (source_type, source_platform, domain)
    source_type is one of: "SOCIAL", "NEWS", "WEB"
    """
    if not url:
        return "WEB", "Unknown", ""

    try:
        parsed = urlparse(url)
        domain = (parsed.netloc or "").lower().split(":")[0]
        if domain.startswith("www."):
            domain = domain[4:]
    except Exception:
        return "WEB", "Unknown", ""

    # 1. Check Social Platforms
    for soc_domain, platform in SOCIAL_DOMAINS_MAP.items():
        if domain == soc_domain or domain.endswith("." + soc_domain):
            return "SOCIAL", platform, domain

    # Check mastodon fediverse pattern
    if "mastodon" in domain or domain.endswith(".social"):
        return "SOCIAL", "Mastodon", domain

    # 2. Check Known News Domains
    for news_domain in NEWS_DOMAINS:
        if domain == news_domain or domain.endswith("." + news_domain):
            return "NEWS", "NewsMedia", domain

    # News-like subpaths or terms
    path_lower = (parsed.path or "").lower()
    if any(k in path_lower for k in ("/news/", "/weather-news/", "/india-news/", "/cities/")):
        return "NEWS", "NewsMedia", domain

    return "WEB", "PublicWeb", domain


def extract_weather_measurements(text: str) -> Dict[str, Any]:
    """Extracts numerical weather measurements (rainfall, temp, wind, pressure) from text."""
    if not text:
        return {}

    measurements: Dict[str, Any] = {}

    # Rainfall: e.g., "120 mm", "5.5 cm", "4 inches"
    rain_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(mm|cm|inches|inch)\b", text, re.IGNORECASE)
    if rain_match:
        measurements["rainfall"] = {
            "value": float(rain_match.group(1)),
            "unit": rain_match.group(2).lower(),
            "raw": rain_match.group(0),
        }

    # Temperature: e.g., "44°C", "42 deg C", "104 °F"
    temp_match = re.search(r"\b(-?\d+(?:\.\d+)?)\s*(?:°\s*C|deg\s*C|degrees\s*celsius|°\s*F|deg\s*F)\b", text, re.IGNORECASE)
    if temp_match:
        measurements["temperature"] = {
            "value": float(temp_match.group(1)),
            "raw": temp_match.group(0),
        }

    # Wind Speed: e.g., "75 km/h", "90 kmph", "45 knots"
    wind_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(km\/h|kmph|mph|knots|kts)\b", text, re.IGNORECASE)
    if wind_match:
        measurements["wind_speed"] = {
            "value": float(wind_match.group(1)),
            "unit": wind_match.group(2).lower(),
            "raw": wind_match.group(0),
        }

    # Pressure: e.g., "998 hPa", "1002 mb"
    pres_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(hpa|mb|mbar)\b", text, re.IGNORECASE)
    if pres_match:
        measurements["pressure"] = {
            "value": float(pres_match.group(1)),
            "unit": pres_match.group(2).lower(),
            "raw": pres_match.group(0),
        }

    return measurements


def extract_hashtags_from_text(text: str) -> List[str]:
    """Extracts hashtags from text preserving original casing."""
    if not text:
        return []
    matches = re.findall(r"#([A-Za-z0-9_]+)", text)
    seen = set()
    result = []
    for m in matches:
        tag = f"#{m}"
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            result.append(tag)
    return result


def is_weather_relevant_search_content(text: str, title: str = "", query: str = "") -> Tuple[bool, List[str]]:
    """Determines if discovered text/title is relevant to weather monitoring."""
    combined = f"{title} {text} {query}".lower()
    matched = []

    keywords = [
        "rain", "rainfall", "heavy rain", "monsoon", "flood", "flooding", "waterlogging",
        "thunderstorm", "lightning", "cyclone", "heatwave", "heat wave", "temperature",
        "fog", "dense fog", "smog", "dust storm", "sandstorm", "strong winds", "squall",
        "cloudburst", "imd", "weather alert", "weather forecast", "hailstorm", "snowfall"
    ]

    for kw in keywords:
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, combined):
            matched.append(kw)

    # Check hashtags
    for tag in DEFAULT_SEARCH_HASHTAGS:
        if tag.lower() in combined:
            matched.append(tag)

    return (len(matched) > 0, list(set(matched)))


# ==============================================================================
# Query Registry & Generation
# ==============================================================================

class SearchQueryRegistry:
    """Configurable registry generating rich location-aware weather queries."""

    def __init__(
        self,
        hashtags: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        custom_queries: Optional[List[str]] = None,
    ):
        self.hashtags = hashtags or list(DEFAULT_SEARCH_HASHTAGS)
        self.locations = locations or list(DEFAULT_SEARCH_LOCATIONS)
        self.categories = categories or list(DEFAULT_SEARCH_CATEGORIES)
        self.custom_queries = custom_queries or []

    def get_all_queries(self) -> List[str]:
        """
        Builds a comprehensive list of search queries:
        1. Standalone Weather Hashtags (e.g. #IMD, #Monsoon2026)
        2. Hashtag + Location combinations (e.g. #Rainfall Odisha, #Flood Assam)
        3. Category + Location phrases (e.g. "heavy rainfall" Mumbai, "IMD warning" India)
        4. User-defined custom queries
        """
        queries: List[str] = []
        seen: Set[str] = set()

        def add_q(q: str):
            clean = " ".join(q.strip().split())
            if clean and clean.lower() not in seen:
                seen.add(clean.lower())
                queries.append(clean)

        # 1. Custom queries first
        for q in self.custom_queries:
            add_q(q)

        # 2. Standalone hashtags
        for ht in self.hashtags:
            add_q(ht)

        # 3. Location-aware hashtag queries (e.g., #Rainfall Odisha, #Flood Assam)
        key_action_hashtags = ["#Rainfall", "#Flood", "#HeavyRain", "#Thunderstorm", "#Heatwave", "#Cyclone", "#WeatherAlert"]
        for ht in key_action_hashtags:
            for loc in self.locations:
                add_q(f"{ht} {loc}")

        # 4. Location-aware quoted category queries (e.g. "heavy rainfall" Mumbai, "IMD warning" India)
        for cat in self.categories:
            for loc in self.locations:
                add_q(f'"{cat}" {loc}')

        return queries


# ==============================================================================
# Search Provider Interface & Implementations
# ==============================================================================

class BaseSearchProvider(ABC):
    """Abstract interface for public search discovery providers."""

    def __init__(self, provider_id: str, name: str, config: Optional[Dict[str, Any]] = None):
        self.provider_id = provider_id
        self.name = name
        self.config = config or {}

    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Execute a search query and return normalized SearchResult items."""
        pass

    @abstractmethod
    async def health_check(self) -> ConnectorStatusEnum:
        """Validate connectivity and configuration."""
        pass


class DuckDuckGoSearchProvider(BaseSearchProvider):
    """
    Zero-cost public search provider using DuckDuckGo public HTML interface.
    No API key required. Handles 429 rate limit backoff and redirect sanitization.
    """

    def __init__(
        self,
        provider_id: str = "ddg-public",
        name: str = "DuckDuckGo Public Search",
        user_agent: Optional[str] = None,
        timeout: float = 10.0,
    ):
        super().__init__(provider_id=provider_id, name=name)
        self.user_agent = user_agent or getattr(
            settings, "SEARCH_DISCOVERY_USER_AGENT", "SkyPulse-SearchDiscovery/1.0.0 (+https://skypulse.gov.in)"
        )
        self.timeout = timeout
        self.base_url = "https://html.duckduckgo.com/html/"
        self._last_rate_limited: Optional[float] = None
        self._backoff_duration: float = 60.0

    async def health_check(self) -> ConnectorStatusEnum:
        if self._last_rate_limited:
            if time.time() - self._last_rate_limited < self._backoff_duration:
                return ConnectorStatusEnum.DEGRADED
        return ConnectorStatusEnum.HEALTHY

    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        if self._last_rate_limited and (time.time() - self._last_rate_limited < self._backoff_duration):
            logger.warning("DuckDuckGo provider in backoff period (%s remaining)", int(self._backoff_duration - (time.time() - self._last_rate_limited)))
            return []

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        data = {"q": query, "b": ""}

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.post(self.base_url, data=data, headers=headers)

                if resp.status_code == 429:
                    self._last_rate_limited = time.time()
                    logger.warning("DuckDuckGo returned 429 Too Many Requests; backing off for %ss", self._backoff_duration)
                    return []

                if resp.status_code != 200:
                    logger.warning("DuckDuckGo HTTP status %s for query '%s'", resp.status_code, query)
                    return []

                return self._parse_html(resp.text, max_results)
        except Exception as e:
            logger.error("DuckDuckGo search error for query '%s': %s", query, e)
            return []

    def _parse_html(self, html_text: str, max_results: int) -> List[SearchResult]:
        """Extracts search results from DuckDuckGo HTML output."""
        results: List[SearchResult] = []
        if not html_text:
            return results

        # Regex block extraction for results
        # DuckDuckGo HTML results are typically structured in <div class="result ..."> or <div class="results_links ...">
        result_blocks = re.findall(
            r'(<div class="result\s+results_links[^"]*"[\s\S]*?</div>\s*</div>\s*</div>|<div class="result[^"]*"[\s\S]*?</div>\s*</div>)',
            html_text,
            re.IGNORECASE,
        )

        if not result_blocks:
            # Fallback block splitter on `<a class="result__url"` or `<a class="result__snippet"`
            result_blocks = re.split(r'<div class="result\b', html_text)[1:]

        for block in result_blocks:
            if len(results) >= max_results:
                break

            # 1. Extract URL & Title
            # <a class="result__snippet" ... href="..."> or <a class="result__url" ... href="..."> or <a class="result__a" ... href="...">
            link_match = re.search(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', block, re.IGNORECASE)
            if not link_match:
                link_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*class="result__url"[^>]*>([\s\S]*?)</a>', block, re.IGNORECASE)

            if not link_match:
                continue

            raw_url = link_match.group(1).strip()
            raw_title = link_match.group(2).strip()

            # Clean DDG redirect URL (//duckduckgo.com/l/?uddg=http%3A%2F%2F...&rut=...)
            clean_url = self._unwrap_ddg_url(raw_url)
            if not clean_url.startswith("http"):
                continue

            # Strip HTML tags from title
            clean_title = html.unescape(re.sub(r"<[^>]+>", "", raw_title)).strip()

            # 2. Extract Snippet
            snippet_match = re.search(r'<a[^>]+class="result__snippet"[^>]*>([\s\S]*?)</a>', block, re.IGNORECASE)
            if not snippet_match:
                snippet_match = re.search(r'<div class="result__snippet"[^>]*>([\s\S]*?)</div>', block, re.IGNORECASE)

            clean_snippet = ""
            if snippet_match:
                clean_snippet = html.unescape(re.sub(r"<[^>]+>", "", snippet_match.group(1))).strip()

            if not clean_title and not clean_snippet:
                continue

            parsed_url = urlparse(clean_url)
            domain = (parsed_url.netloc or "").lower().split(":")[0]

            results.append(
                SearchResult(
                    title=clean_title or "Weather Update",
                    url=clean_url,
                    snippet=clean_snippet,
                    source_domain=domain,
                    source_name=domain,
                    published_at=datetime.now(timezone.utc),
                    raw_metadata={"raw_html_block": block[:500]},
                )
            )

        return results

    @staticmethod
    def _unwrap_ddg_url(raw_url: str) -> str:
        """Unwraps DuckDuckGo redirect link to canonical destination URL."""
        if "uddg=" in raw_url:
            parsed = urllib.parse.urlparse(raw_url)
            qs = parse_qs(parsed.query)
            if "uddg" in qs and qs["uddg"]:
                return qs["uddg"][0]
        return raw_url


class SearXNGSearchProvider(BaseSearchProvider):
    """
    Zero-cost public or self-hosted SearXNG metasearch provider.
    Supports JSON output format (format=json).
    """

    def __init__(
        self,
        provider_id: str = "searxng-provider",
        name: str = "SearXNG Metasearch",
        base_url: Optional[str] = None,
        timeout: float = 10.0,
    ):
        super().__init__(provider_id=provider_id, name=name)
        self.base_url = (base_url or getattr(settings, "SEARXNG_BASE_URL", "") or "").rstrip("/")
        self.timeout = timeout

    async def health_check(self) -> ConnectorStatusEnum:
        if not self.base_url:
            return ConnectorStatusEnum.NOT_CONFIGURED
        return ConnectorStatusEnum.HEALTHY

    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        if not self.base_url:
            return []

        endpoint = f"{self.base_url}/search"
        params = {"q": query, "format": "json", "language": "en-IN"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(endpoint, params=params)
                if resp.status_code != 200:
                    logger.warning("SearXNG HTTP %s for query '%s'", resp.status_code, query)
                    return []

                data = resp.json()
                results: List[SearchResult] = []
                for item in data.get("results", [])[:max_results]:
                    url = item.get("url")
                    title = item.get("title")
                    content = item.get("content") or item.get("snippet", "")
                    if not url or not title:
                        continue

                    media = []
                    if item.get("img_src"):
                        media.append(item.get("img_src"))

                    results.append(
                        SearchResult(
                            title=html.unescape(title).strip(),
                            url=url,
                            snippet=html.unescape(content).strip(),
                            source_name=item.get("engine"),
                            source_domain=urlparse(url).netloc,
                            media_urls=media,
                            raw_metadata=item,
                        )
                    )
                return results
        except Exception as e:
            logger.error("SearXNG search error: %s", e)
            return []


class GoogleCSESearchProvider(BaseSearchProvider):
    """
    Google Custom Search Engine (CSE) provider.
    Optional; returns NOT_CONFIGURED when api_key or cx are missing.
    """

    def __init__(
        self,
        provider_id: str = "google-cse",
        name: str = "Google Custom Search",
        api_key: Optional[str] = None,
        cx: Optional[str] = None,
        timeout: float = 10.0,
    ):
        super().__init__(provider_id=provider_id, name=name)
        self.api_key = api_key or getattr(settings, "GOOGLE_CSE_API_KEY", "")
        self.cx = cx or getattr(settings, "GOOGLE_CSE_CX", "")
        self.timeout = timeout

    async def health_check(self) -> ConnectorStatusEnum:
        if not self.api_key or not self.cx:
            return ConnectorStatusEnum.NOT_CONFIGURED
        return ConnectorStatusEnum.HEALTHY

    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        if not self.api_key or not self.cx:
            return []

        url = "https://www.googleapis.com/customsearch/v1"
        params = {"key": self.api_key, "cx": self.cx, "q": query, "num": min(max_results, 10)}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning("Google CSE HTTP %s for query '%s'", resp.status_code, query)
                    return []

                data = resp.json()
                results: List[SearchResult] = []
                for item in data.get("items", []):
                    link = item.get("link")
                    title = item.get("title")
                    snippet = item.get("snippet", "")
                    if not link or not title:
                        continue

                    media = []
                    pagemap = item.get("pagemap", {})
                    for cse_img in pagemap.get("cse_image", []):
                        if cse_img.get("src"):
                            media.append(cse_img.get("src"))

                    results.append(
                        SearchResult(
                            title=title,
                            url=link,
                            snippet=snippet,
                            source_domain=urlparse(link).netloc,
                            media_urls=media,
                            raw_metadata=item,
                        )
                    )
                return results
        except Exception as e:
            logger.error("Google CSE error: %s", e)
            return []


class CustomSearchProvider(BaseSearchProvider):
    """Extensible custom search provider for user endpoints and deterministic test suites."""

    def __init__(
        self,
        provider_id: str = "custom-provider",
        name: str = "Custom Search Provider",
        handler: Optional[Any] = None,
    ):
        super().__init__(provider_id=provider_id, name=name)
        self.handler = handler

    async def health_check(self) -> ConnectorStatusEnum:
        return ConnectorStatusEnum.HEALTHY

    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        if self.handler and callable(self.handler):
            res = self.handler(query, max_results)
            if asyncio.iscoroutine(res):
                return await res
            return res
        return []


# ==============================================================================
# Search Discovery Connector Implementation
# ==============================================================================

class SearchDiscoveryConnector(BaseConnector):
    """
    Main SkyPulse Search Discovery Ingestion Connector (Phase 1).
    Discovers publicly indexed weather posts, news articles, and web content.
    Feeds events into the canonical normalization and intelligence pipeline.
    """

    def __init__(
        self,
        source_id: str = DEFAULT_SOURCE_ID,
        name: str = CONNECTOR_NAME,
        provider: Optional[BaseSearchProvider] = None,
        query_registry: Optional[SearchQueryRegistry] = None,
        config: Optional[Dict[str, Any]] = None,
        is_demo: bool = False,
    ):
        super().__init__(
            source_id=source_id,
            name=name,
            source_type="SEARCH_DISCOVERY",
            config=config or {},
            is_demo=is_demo,
        )
        self.query_registry = query_registry or SearchQueryRegistry()
        self.provider = provider or self._init_default_provider()
        self.max_results_per_query = getattr(settings, "SEARCH_DISCOVERY_MAX_RESULTS_PER_QUERY", 10)
        self._query_cursor = 0
        self._seen_urls: Set[str] = set()

    def _init_default_provider(self) -> BaseSearchProvider:
        """Initializes configured search discovery provider from settings."""
        prov_type = getattr(settings, "SEARCH_DISCOVERY_PROVIDER", "duckduckgo").lower()

        if prov_type == "searxng":
            return SearXNGSearchProvider(
                base_url=getattr(settings, "SEARXNG_BASE_URL", ""),
                timeout=getattr(settings, "SEARCH_DISCOVERY_REQUEST_TIMEOUT_SECONDS", 10.0),
            )
        elif prov_type == "google_cse":
            return GoogleCSESearchProvider(
                api_key=getattr(settings, "GOOGLE_CSE_API_KEY", ""),
                cx=getattr(settings, "GOOGLE_CSE_CX", ""),
                timeout=getattr(settings, "SEARCH_DISCOVERY_REQUEST_TIMEOUT_SECONDS", 10.0),
            )
        else:
            return DuckDuckGoSearchProvider(
                user_agent=getattr(settings, "SEARCH_DISCOVERY_USER_AGENT", None),
                timeout=getattr(settings, "SEARCH_DISCOVERY_REQUEST_TIMEOUT_SECONDS", 10.0),
            )

    def set_provider(self, provider: BaseSearchProvider) -> None:
        """Switch active search discovery provider at runtime."""
        self.provider = provider
        logger.info("Search discovery provider set to '%s'", provider.name)

    def set_custom_queries(self, queries: List[str]) -> None:
        """Update custom search queries dynamically."""
        self.query_registry.custom_queries = queries

    async def health_check(self) -> ConnectorStatusEnum:
        if not getattr(settings, "SEARCH_DISCOVERY_ENABLED", True):
            return ConnectorStatusEnum.DISABLED
        if not self.is_running:
            return ConnectorStatusEnum.DISABLED
        if not self.provider:
            return ConnectorStatusEnum.NOT_CONFIGURED
        prov_health = await self.provider.health_check()
        self.status = prov_health
        return self.status

    def parse(self, raw_data: Any) -> Optional[CanonicalRawEvent]:
        """
        Converts a SearchResult and associated query into a CanonicalRawEvent envelope.
        Performs weather relevance check and India location extraction (zero fake GPS!).
        """
        if not isinstance(raw_data, tuple) or len(raw_data) != 2:
            if isinstance(raw_data, SearchResult):
                result = raw_data
                query = ""
            else:
                return None
        else:
            result, query = raw_data

        full_text = f"{result.title}. {result.snippet}".strip()
        sanitized = sanitize_text(full_text)
        if not sanitized:
            return None

        # 1. Weather Relevance Filter
        is_relevant, matched_terms = is_weather_relevant_search_content(
            text=result.snippet,
            title=result.title,
            query=query,
        )
        if not is_relevant:
            return None

        # 2. Classify Source Type (SOCIAL vs NEWS vs WEB)
        source_type, platform, domain = classify_source_url(result.url)

        # 3. Extract Hashtags & Numerical Measurements
        hashtags = extract_hashtags_from_text(full_text)
        measurements = extract_weather_measurements(full_text)

        # 4. India Location Enrichment & Zero Fake GPS rule
        lat, lon, city, district, state, loc_source, loc_conf, is_india, is_quar, quar_reason = enrich_location(
            lat=None,
            lon=None,
            text=full_text,
        )

        # 5. Media references
        media_items = []
        for m_url in result.media_urls:
            media_items.append(MediaItem(media_type="IMAGE", url=m_url))

        # 6. Canonical Category
        category = normalize_category(None, full_text)

        # 7. Rich Provenance Payload
        raw_payload = {
            "discovery_provider": self.provider.name,
            "search_query": query,
            "discovery_timestamp": datetime.now(timezone.utc).isoformat(),
            "original_url": result.url,
            "source_domain": domain,
            "source_type": source_type,
            "source_platform": platform,
            "weather_measurements": measurements,
            "extracted_hashtags": hashtags,
            "matched_weather_terms": matched_terms,
            "title": result.title,
            "snippet": result.snippet,
            "raw_result_metadata": result.raw_metadata,
        }

        # Canonical idempotency key based on URL and text content
        idempotency_key = idempotency_service.compute_key(
            source_id=self.source_id,
            external_id=result.url,
            text=sanitized,
            observed_at=result.published_at or datetime.now(timezone.utc),
            latitude=lat,
            longitude=lon,
        )

        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type=source_type,
            external_id=result.url,
            observed_at=result.published_at or datetime.now(timezone.utc),
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
        Polls configured search queries in round-robin batches.
        Deduplicates discovered URLs and maintains strict mathematical telemetry invariants.
        """
        t0 = time.time()
        self.metrics.last_poll_at = datetime.now(timezone.utc)

        if not getattr(settings, "SEARCH_DISCOVERY_ENABLED", True):
            self.status = ConnectorStatusEnum.DISABLED
            return []

        if not self.provider:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return []

        all_queries = self.query_registry.get_all_queries()
        if not all_queries:
            return []

        # Select a batch of queries to execute during this polling cycle
        batch_size = 3
        selected_queries = []
        for _ in range(min(batch_size, len(all_queries))):
            selected_queries.append(all_queries[self._query_cursor % len(all_queries)])
            self._query_cursor += 1

        raw_records_batch: List[Tuple[SearchResult, str]] = []

        for q in selected_queries:
            try:
                results = await self.provider.search(q, max_results=self.max_results_per_query)
                for r in results:
                    raw_records_batch.append((r, q))
            except Exception as e:
                self.metrics.errors += 1
                self.metrics.last_error = str(e)
                self.metrics.last_error_at = datetime.now(timezone.utc)
                logger.error("Error executing search query '%s': %s", q, e)

        # Mathematical telemetry tracking
        cycle_fetched = len(raw_records_batch)
        cycle_weather_rel = 0
        cycle_accepted_india = 0
        cycle_quar_foreign = 0
        cycle_quar_unknown = 0
        cycle_rejected_non_weather = 0
        cycle_duplicates = 0

        canonical_events: List[CanonicalRawEvent] = []

        for item in raw_records_batch:
            result, query = item
            raw_event = self.parse(item)

            if raw_event is None:
                cycle_rejected_non_weather += 1
                continue

            cycle_weather_rel += 1

            # Check duplication across URL or idempotency key
            if result.url in self._seen_urls:
                cycle_duplicates += 1
            self._seen_urls.add(result.url)

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

        return canonical_events


# Global search discovery connector instance
search_discovery_connector = SearchDiscoveryConnector()
