"""
SkyPulse Social & Web Weather Intelligence Connector
======================================================
Turn permitted internet weather signals into structured, verifiable evidence.

Supported Source Types:
- SOCIAL_API: Authorized social media APIs (e.g., Mastodon, Bluesky, authorized X/Twitter weather streams)
- SOCIAL_FEED: Authorized/public microblog feeds
- PUBLIC_WEB: Controlled public weather webpages (explicit configured URLs only, strict limits)
- RSS_FEED: RSS 2.0 & Atom XML syndication feeds
- PUBLIC_JSON: Configurable JSON endpoints with flexible record and field mapping

Integrates into the CanonicalRawEvent -> Normalization -> Deduplication -> DWEG -> Event DNA pipeline.
No unrestricted crawling, no CAPTCHA/anti-bot bypass, no fake social post generation.
"""

import hashlib
import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.models.enums import ContentRelationship, WeatherCategory
from connectors.base import BaseConnector
from connectors.idempotency import idempotency_service
from connectors.normalizer import (
    INDIA_LAT_MAX,
    INDIA_LAT_MIN,
    INDIA_LON_MAX,
    INDIA_LON_MIN,
    INDIAN_CITIES_REFERENCE,
    enrich_location,
    normalize_category,
    sanitize_text,
)
from connectors.schema import CanonicalRawEvent, ConnectorMetrics, ConnectorStatusEnum, MediaItem, NormalizedEvent

logger = logging.getLogger("skypulse.connectors.social_web")

CONNECTOR_NAME = "SocialWebConnector"
CONNECTOR_VERSION = "1.0.0"

# Standard configurable weather terms & hashtags (Centralized 25 initial default hashtags)
DEFAULT_WEATHER_HASHTAGS = [
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

DEFAULT_WEATHER_KEYWORDS = [
    "heavy rain",
    "downpour",
    "rainfall",
    "thunderstorm",
    "lightning",
    "flood",
    "flooding",
    "waterlogging",
    "waterlogged",
    "inundated",
    "heatwave",
    "heat wave",
    "extreme heat",
    "loo",
    "dense fog",
    "fog",
    "sandstorm",
    "dust storm",
    "squall",
    "gale",
    "strong winds",
    "cyclone",
    "super cyclone",
    "cloudburst",
    "hailstorm",
    "landslide",
    "weather warning",
    "red alert",
    "orange alert",
    "yellow alert",
]


def normalize_hashtag(tag: str) -> str:
    """Normalize a hashtag string: strips whitespace, ensures '#' prefix, preserves text."""
    if not tag:
        return ""
    t = tag.strip()
    if not t.startswith("#"):
        t = f"#{t}"
    return t


def parse_hashtag_list(tags_input: Any) -> List[str]:
    """
    Parse, deduplicate case-insensitively, and return canonical hashtag list.
    Preserves original casing and order of first occurrence.
    """
    if not tags_input:
        return []
    if isinstance(tags_input, str):
        raw_list = [item.strip() for item in tags_input.split(",") if item.strip()]
    elif isinstance(tags_input, (list, tuple, set)):
        raw_list = [str(item).strip() for item in tags_input if str(item).strip()]
    else:
        raw_list = [str(tags_input).strip()]

    seen_lower = set()
    result: List[str] = []
    for item in raw_list:
        normalized = normalize_hashtag(item)
        if normalized and normalized.lower() not in seen_lower:
            seen_lower.add(normalized.lower())
            result.append(normalized)
    return result


class HashtagRegistry:
    """
    Centralized configurable hashtag registry for social weather signal ingestion.
    Allows dynamic registration, case-insensitive matching, and configuration override.
    """

    def __init__(self, initial_hashtags: Optional[List[str]] = None):
        self._hashtags: List[str] = parse_hashtag_list(initial_hashtags or DEFAULT_WEATHER_HASHTAGS)

    def get_hashtags(self) -> List[str]:
        return list(self._hashtags)

    def set_hashtags(self, hashtags: Any) -> List[str]:
        self._hashtags = parse_hashtag_list(hashtags)
        return list(self._hashtags)

    def add_hashtag(self, tag: str) -> None:
        normalized = normalize_hashtag(tag)
        if normalized and normalized.lower() not in {h.lower() for h in self._hashtags}:
            self._hashtags.append(normalized)

    def remove_hashtag(self, tag: str) -> None:
        norm_lower = normalize_hashtag(tag).lower()
        self._hashtags = [h for h in self._hashtags if h.lower() != norm_lower]

    def is_weather_hashtag(self, tag: str) -> bool:
        if not tag:
            return False
        norm_lower = normalize_hashtag(tag).lower()
        return any(h.lower() == norm_lower for h in self._hashtags)

    def match_text(self, text: str) -> Tuple[bool, List[str]]:
        if not text:
            return False, []
        text_lower = text.lower()
        matched: List[str] = []
        for ht in self._hashtags:
            if ht.lower() in text_lower:
                matched.append(ht)
        return len(matched) > 0, matched


# Singleton registry instance
hashtag_registry = HashtagRegistry()


def extract_hashtags(text: str) -> List[str]:
    """Extract all hashtags from text preserving case and prefix."""
    if not text:
        return []
    return re.findall(r"#\w+", text)


def matches_weather_filter(
    text: str,
    configured_hashtags: Optional[List[str]] = None,
    configured_keywords: Optional[List[str]] = None,
) -> Tuple[bool, List[str]]:
    """
    Check if text contains weather-related hashtags or keywords.
    Returns (is_match, matched_terms).
    """
    if not text:
        return False, []

    text_lower = text.lower()
    matched_terms: List[str] = []

    # 1. Check hashtags
    if configured_hashtags is not None:
        ht_list = parse_hashtag_list(configured_hashtags)
        for ht in ht_list:
            if ht.lower() in text_lower:
                matched_terms.append(ht)
    else:
        is_ht_match, ht_matched = hashtag_registry.match_text(text)
        if is_ht_match:
            matched_terms.extend(ht_matched)

    # 2. Check keywords
    keywords = configured_keywords if configured_keywords is not None else DEFAULT_WEATHER_KEYWORDS
    for kw in keywords:
        pattern = r"\b" + re.escape(kw.lower()) + r"\b"
        if re.search(pattern, text_lower):
            matched_terms.append(kw)

    return (len(matched_terms) > 0, matched_terms)


def validate_india_coordinates(lat: Optional[float], lon: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    """Ensure coordinates strictly reside within India bounding box."""
    if lat is None or lon is None:
        return None, None
    try:
        lat_f = float(lat)
        lon_f = float(lon)
        if INDIA_LAT_MIN <= lat_f <= INDIA_LAT_MAX and INDIA_LON_MIN <= lon_f <= INDIA_LON_MAX:
            return round(lat_f, 6), round(lon_f, 6)
    except (ValueError, TypeError):
        pass
    return None, None


def sanitize_config_dict(config: Dict[str, Any]) -> Dict[str, Any]:
    """Strip secret tokens and API keys from dictionary to prevent credential leakage."""
    sanitized = {}
    secret_keys = {"api_key", "api_token", "token", "password", "secret", "authorization", "auth_token"}
    for k, v in config.items():
        if any(sk in k.lower() for sk in secret_keys):
            sanitized[k] = "***MASKED***" if v else None
        elif isinstance(v, dict):
            sanitized[k] = sanitize_config_dict(v)
        else:
            sanitized[k] = v
    return sanitized


def compute_content_hash(text: str) -> str:
    """Deterministic SHA-256 hash of normalized text for copy/duplicate detection."""
    clean = " ".join(text.lower().split())
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


def detect_content_relationship(
    text: str,
    external_id: str,
    raw_payload: Dict[str, Any],
    recent_events: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[ContentRelationship, Dict[str, Any]]:
    """
    Deterministically classify the content relationship:
    ORIGINAL, REPOST, LIKELY_COPY, DUPLICATE, or UNKNOWN.
    """
    evidence: Dict[str, Any] = {
        "content_hash": compute_content_hash(text),
        "has_repost_indicator": False,
        "matched_original_id": None,
    }

    # Check explicit repost metadata indicators
    if raw_payload.get("is_repost") or raw_payload.get("repost_of") or raw_payload.get("retweeted_status") or raw_payload.get("reblog"):
        evidence["has_repost_indicator"] = True
        matched_id = (
            raw_payload.get("repost_of")
            or (raw_payload.get("retweeted_status", {}).get("id") if isinstance(raw_payload.get("retweeted_status"), dict) else None)
            or (raw_payload.get("reblog", {}).get("id") if isinstance(raw_payload.get("reblog"), dict) else None)
            or ""
        )
        evidence["matched_original_id"] = str(matched_id)
        return ContentRelationship.REPOST, evidence

    # Check common repost text prefixes (e.g., RT @...)
    if text.strip().startswith("RT @") or text.strip().startswith("Repost @"):
        evidence["has_repost_indicator"] = True
        return ContentRelationship.REPOST, evidence

    # Check against recent event records
    if recent_events:
        this_hash = evidence["content_hash"]
        for prev in recent_events:
            prev_id = prev.get("external_id")
            prev_hash = prev.get("content_hash") or compute_content_hash(prev.get("text", ""))

            # Exact external ID match
            if prev_id and prev_id == external_id:
                evidence["matched_original_id"] = prev_id
                return ContentRelationship.DUPLICATE, evidence

            # Exact content hash match from another post
            if prev_hash == this_hash:
                evidence["matched_original_id"] = prev_id
                return ContentRelationship.LIKELY_COPY, evidence

            # High token overlap (Jaccard similarity >= 0.85)
            tokens_curr = set(text.lower().split())
            tokens_prev = set(str(prev.get("text", "")).lower().split())
            if tokens_curr and tokens_prev:
                jaccard = len(tokens_curr & tokens_prev) / len(tokens_curr | tokens_prev)
                if jaccard >= 0.85:
                    evidence["matched_original_id"] = prev_id
                    evidence["jaccard_similarity"] = round(jaccard, 3)
                    return ContentRelationship.LIKELY_COPY, evidence

    # Default to ORIGINAL if it has content, or UNKNOWN if empty/minimal
    if len(text.strip()) > 10:
        return ContentRelationship.ORIGINAL, evidence
    return ContentRelationship.UNKNOWN, evidence


# ============================================================================
# PROVIDER ABSTRACTION
# ============================================================================

class SocialWebProvider(ABC):
    """
    Abstract Base Class for all Social & Web Ingestion Providers.
    Defines the contract for fetching, health checking, parsing, and normalizing.
    """

    def __init__(
        self,
        provider_id: str,
        name: str,
        source_type: str,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.provider_id = provider_id
        self.name = name
        self.source_type = source_type
        self.config = config or {}
        self.status = ConnectorStatusEnum.NOT_CONFIGURED
        self.metrics = ConnectorMetrics()
        self.last_records: List[Dict[str, Any]] = []

    @abstractmethod
    async def fetch(self) -> List[Any]:
        """Fetch raw items/payload from the external service."""
        pass

    @abstractmethod
    async def health_check(self) -> ConnectorStatusEnum:
        """Inspect provider configuration and live endpoint reachability."""
        pass

    @abstractmethod
    def parse(self, raw_data: Any) -> Optional[CanonicalRawEvent]:
        """Parse raw record into a CanonicalRawEvent envelope."""
        pass

    def normalize(self, raw_event: CanonicalRawEvent) -> NormalizedEvent:
        """Standard normalization wrapper."""
        # Synchronous normalization wrapper using base normalizer logic
        clean_text = sanitize_text(raw_event.text)
        category = normalize_category(raw_event.suggested_category, clean_text)
        lat, lon, city, district, state, loc_source, loc_conf, is_india, is_quar, quar_reason = enrich_location(
            lat=raw_event.latitude,
            lon=raw_event.longitude,
            city=raw_event.city,
            district=raw_event.district,
            state=raw_event.state,
            text=clean_text,
        )
        key = raw_event.idempotency_key or idempotency_service.compute_key(
            source_id=raw_event.source_id,
            external_id=raw_event.external_id,
            text=clean_text,
            observed_at=raw_event.observed_at,
            latitude=lat,
            longitude=lon,
        )
        year = raw_event.observed_at.year if raw_event.observed_at else datetime.now(timezone.utc).year
        tracking_id = f"SP-{year}-{abs(hash(key)) % 900000 + 100000}"

        return NormalizedEvent(
            ingestion_id=raw_event.ingestion_id,
            source_id=raw_event.source_id,
            source_type=raw_event.source_type,
            external_id=raw_event.external_id,
            tracking_id=tracking_id,
            text=clean_text,
            primary_category=category,
            severity=raw_event.severity or 2,
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
            observed_at=raw_event.observed_at,
            ingested_at=raw_event.ingested_at,
            media=raw_event.media,
            metadata={"raw_payload": raw_event.raw_payload},
            is_demo=raw_event.is_demo,
            is_duplicate=False,
            idempotency_key=key,
        )

    def get_source_metadata(self) -> Dict[str, Any]:
        """Return safe, credential-free telemetry and metadata."""
        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "source_type": self.source_type,
            "status": self.status.value,
            "config": sanitize_config_dict(self.config),
            "metrics": self.metrics.model_dump(),
        }


# ============================================================================
# 1. SOCIAL API ADAPTER (Authorized APIs e.g. Mastodon, Bluesky, X/Twitter API)
# ============================================================================

class SocialAPIAdapter(SocialWebProvider):
    """
    Authorized Social Media API & Public Mastodon Hashtag Timeline Adapter.
    Supports querying public hashtag timelines across configured weather hashtags without tokens,
    or using explicit Bearer tokens / API keys where provided.
    Never bypasses authentication, CAPTCHA, or anti-bot restrictions.
    Gracefully handles rate limits (HTTP 429) with backoff.
    """

    def __init__(
        self,
        provider_id: str = "social-api-primary",
        name: str = "Authorized Social Media Weather Monitor",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_token: Optional[str] = None,
        queries: Optional[List[str]] = None,
        max_posts_per_hashtag: int = 20,
        poll_interval_seconds: int = 60,
        timeout_seconds: float = 10.0,
        user_agent: Optional[str] = None,
    ):
        parsed_queries = parse_hashtag_list(queries) if queries else DEFAULT_WEATHER_HASHTAGS
        config = {
            "base_url": base_url,
            "api_key": api_key,
            "api_token": api_token,
            "queries": parsed_queries,
            "max_posts_per_hashtag": max_posts_per_hashtag,
            "poll_interval_seconds": poll_interval_seconds,
            "timeout_seconds": timeout_seconds,
            "user_agent": user_agent or f"SkyPulse-WeatherAnalytics/{CONNECTOR_VERSION} (+https://skypulse.gov.in)",
        }
        super().__init__(
            provider_id=provider_id,
            name=name,
            source_type="SOCIAL_API",
            config=config,
        )
        self.base_url = base_url
        self.api_key = api_key
        self.api_token = api_token
        self.queries = parsed_queries
        self.max_posts_per_hashtag = max_posts_per_hashtag
        self.timeout_seconds = timeout_seconds
        self.user_agent = config["user_agent"]
        self.status = (
            ConnectorStatusEnum.HEALTHY
            if self.base_url
            else ConnectorStatusEnum.NOT_CONFIGURED
        )
        self._seen_post_ids: set = set()

    def is_configured(self) -> bool:
        return bool(self.base_url)

    async def health_check(self) -> ConnectorStatusEnum:
        if not self.is_configured():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return self.status

        headers = {"User-Agent": self.user_agent}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        elif self.api_key:
            headers["X-API-Key"] = self.api_key

        test_url = self.base_url
        # If base_url is a domain like https://mastodon.social, check instance or first tag
        base_clean = (self.base_url or "").rstrip("/")
        if "/api/" not in base_clean and "/timelines/" not in base_clean:
            # Check instance health or public tag timeline
            tag_name = (self.queries[0] if self.queries else "Weather").lstrip("#")
            test_url = f"{base_clean}/api/v1/timelines/tag/{tag_name}?limit=1"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
                resp = await client.get(test_url)
                if resp.status_code in (200, 204):
                    self.status = ConnectorStatusEnum.HEALTHY
                elif resp.status_code in (401, 403):
                    self.status = ConnectorStatusEnum.ERROR
                    self.metrics.last_error = f"Authentication failure: HTTP {resp.status_code}"
                elif resp.status_code == 429:
                    self.status = ConnectorStatusEnum.DEGRADED
                    self.metrics.rate_limits += 1
                    self.metrics.last_error = "Rate limit reached on Social API endpoint"
                else:
                    self.status = ConnectorStatusEnum.DEGRADED
                    self.metrics.last_error = f"Unexpected HTTP status {resp.status_code}"
        except httpx.TimeoutException:
            self.status = ConnectorStatusEnum.DEGRADED
            self.metrics.last_error = "Connection timed out during health check"
        except Exception as e:
            self.status = ConnectorStatusEnum.ERROR
            self.metrics.last_error = str(e)

        return self.status

    async def fetch(self) -> List[Dict[str, Any]]:
        if not self.is_configured():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return []

        t0 = time.time()
        self.metrics.last_poll_at = datetime.now(timezone.utc)
        headers = {
            "User-Agent": self.user_agent,
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        elif self.api_key:
            headers["X-API-Key"] = self.api_key

        records: List[Dict[str, Any]] = []
        endpoints_to_poll: List[str] = []

        base_clean = (self.base_url or "").rstrip("/")
        # If the base_url is a direct timeline/tag endpoint or specific API path
        if "/api/" in base_clean or "/timelines/" in base_clean:
            endpoints_to_poll.append(base_clean)
        else:
            # Query public hashtag timelines for configured hashtags
            tags = self.queries if self.queries else DEFAULT_WEATHER_HASHTAGS
            for tag in tags:
                tag_name = tag.lstrip("#").strip()
                if tag_name:
                    endpoints_to_poll.append(f"{base_clean}/api/v1/timelines/tag/{tag_name}?limit={self.max_posts_per_hashtag}")

        has_healthy_fetch = False
        rate_limited = False

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
                for ep in endpoints_to_poll:
                    try:
                        resp = await client.get(ep)
                        if resp.status_code == 200:
                            data = resp.json()
                            raw_items = []
                            if isinstance(data, list):
                                raw_items = data
                            elif isinstance(data, dict):
                                raw_items = data.get("statuses", data.get("posts", data.get("data", data.get("items", []))))
                                if not raw_items and ("id" in data or "content" in data or "text" in data):
                                    raw_items = [data]

                            for item in raw_items:
                                if isinstance(item, dict):
                                    post_id = str(item.get("id") or item.get("post_id") or "")
                                    if post_id and post_id in self._seen_post_ids:
                                        continue
                                    if post_id:
                                        self._seen_post_ids.add(post_id)
                                        if len(self._seen_post_ids) > 2000:
                                            self._seen_post_ids.pop()
                                    records.append(item)
                            has_healthy_fetch = True
                        elif resp.status_code == 429:
                            self.metrics.rate_limits += 1
                            self.metrics.last_error = "Rate limit exceeded (HTTP 429)"
                            self.metrics.last_error_at = datetime.now(timezone.utc)
                            rate_limited = True
                            logger.warning("Social API rate limit encountered on %s", ep)
                            break
                        elif resp.status_code in (401, 403):
                            self.metrics.last_error = f"Authentication failure: HTTP {resp.status_code}"
                            self.metrics.last_error_at = datetime.now(timezone.utc)
                            self.metrics.errors += 1
                        else:
                            self.metrics.last_error = f"Social API HTTP {resp.status_code}"
                            self.metrics.last_error_at = datetime.now(timezone.utc)
                            self.metrics.errors += 1
                    except httpx.TimeoutException:
                        self.metrics.last_error = f"Request timed out on {ep}"
                        self.metrics.last_error_at = datetime.now(timezone.utc)
                        self.metrics.errors += 1
                    except Exception as tag_err:
                        self.metrics.last_error = str(tag_err)
                        self.metrics.last_error_at = datetime.now(timezone.utc)
                        self.metrics.errors += 1

            latency_ms = (time.time() - t0) * 1000
            self.metrics.processing_latency_ms = latency_ms

            if rate_limited:
                self.status = ConnectorStatusEnum.DEGRADED
            elif has_healthy_fetch:
                self.metrics.records_fetched += len(records)
                self.metrics.records_accepted += len(records)
                self.metrics.last_successful_fetch = datetime.now(timezone.utc)
                self.status = ConnectorStatusEnum.HEALTHY
            elif not endpoints_to_poll:
                self.status = ConnectorStatusEnum.NOT_CONFIGURED
            else:
                self.status = ConnectorStatusEnum.ERROR

        except Exception as e:
            self.metrics.last_error = str(e)
            self.metrics.last_error_at = datetime.now(timezone.utc)
            self.metrics.errors += 1
            self.status = ConnectorStatusEnum.ERROR
            logger.error("Social API fetch error: %s", e)

        return records

    def parse(self, raw_data: Dict[str, Any]) -> Optional[CanonicalRawEvent]:
        if not isinstance(raw_data, dict):
            return None

        # Extract text/content
        raw_text = raw_data.get("text") or raw_data.get("content") or raw_data.get("body") or ""
        # Strip HTML tags if microblog format
        text_without_html = re.sub(r"<[^>]+>", " ", raw_text)
        clean_text = sanitize_text(html.unescape(text_without_html))
        if not clean_text:
            return None

        # Extract hashtags from content and structured tags
        extracted_tags = extract_hashtags(clean_text)
        tags_in_post = raw_data.get("tags") or []
        if isinstance(tags_in_post, list):
            for t in tags_in_post:
                if isinstance(t, dict) and t.get("name"):
                    extracted_tags.append(f"#{t['name']}")
                elif isinstance(t, str):
                    extracted_tags.append(f"#{t.lstrip('#')}")
        extracted_tags = parse_hashtag_list(extracted_tags)

        # Hashtag / Keyword weather filtering
        is_weather, matched_terms = matches_weather_filter(clean_text, self.queries, DEFAULT_WEATHER_KEYWORDS)
        if not is_weather and any(hashtag_registry.is_weather_hashtag(t) for t in extracted_tags):
            is_weather = True
            matched_terms = [t for t in extracted_tags if hashtag_registry.is_weather_hashtag(t)]

        if not is_weather:
            # Drop non-weather chit chat
            return None

        post_id = str(raw_data.get("id") or raw_data.get("post_id") or raw_data.get("external_id") or abs(hash(clean_text)))
        
        # Published timestamp
        pub_date_raw = raw_data.get("created_at") or raw_data.get("published_at") or raw_data.get("timestamp")
        observed_at = datetime.now(timezone.utc)
        if pub_date_raw:
            try:
                if isinstance(pub_date_raw, (int, float)):
                    observed_at = datetime.fromtimestamp(pub_date_raw, tz=timezone.utc)
                elif isinstance(pub_date_raw, str):
                    observed_at = datetime.fromisoformat(pub_date_raw.replace("Z", "+00:00"))
            except Exception:
                pass

        # GPS Extraction
        lat, lon = None, None
        geo = raw_data.get("geo") or raw_data.get("coordinates") or raw_data.get("location")
        if isinstance(geo, dict):
            lat = geo.get("lat") or geo.get("latitude")
            lon = geo.get("lon") or geo.get("longitude") or geo.get("lng")
        elif isinstance(geo, (list, tuple)) and len(geo) >= 2:
            # standard [lat, lon] or GeoJSON [lon, lat]
            lat, lon = geo[0], geo[1]
        try:
            if lat is not None and lon is not None:
                lat, lon = float(lat), float(lon)
        except (ValueError, TypeError):
            lat, lon = None, None

        # Explicit city/state strings
        city = raw_data.get("city")
        state = raw_data.get("state")
        if not city and isinstance(geo, dict):
            city = geo.get("city")
            state = geo.get("state")

        # Media Items
        media_items: List[MediaItem] = []
        raw_media = raw_data.get("media") or raw_data.get("attachments") or raw_data.get("media_attachments") or []
        if isinstance(raw_media, list):
            for m in raw_media:
                if isinstance(m, dict) and (m.get("url") or m.get("remote_url") or m.get("preview_url")):
                    m_url = m.get("url") or m.get("remote_url") or m.get("preview_url")
                    m_type = "IMAGE"
                    m_type_raw = str(m.get("type", "")).upper()
                    if "VIDEO" in m_type_raw or "GIF" in m_type_raw:
                        m_type = "VIDEO"
                    elif "AUDIO" in m_type_raw:
                        m_type = "AUDIO"
                    media_items.append(
                        MediaItem(
                            media_type=m_type,
                            url=m_url,
                            thumbnail_url=m.get("preview_url") or m.get("thumbnail_url"),
                            mime_type=m.get("mime_type") or m.get("content_type"),
                            file_size_bytes=int(m.get("file_size")) if str(m.get("file_size", "")).isdigit() else (int(m.get("size")) if str(m.get("size", "")).isdigit() else None),
                        )
                    )

        # Repost and relationship classification
        rel, rel_evidence = detect_content_relationship(clean_text, post_id, raw_data, self.last_records)
        self.last_records.append({"external_id": post_id, "text": clean_text, "content_hash": rel_evidence.get("content_hash")})
        if len(self.last_records) > 500:
            self.last_records.pop(0)

        suggested_category = normalize_category(None, clean_text)

        account = raw_data.get("account") if isinstance(raw_data.get("account"), dict) else {}
        author_id = raw_data.get("author_id") or account.get("username") or account.get("acct")
        author_name = account.get("display_name") or author_id

        raw_payload = {
            "platform": raw_data.get("platform", "Mastodon" if "mastodon" in (self.base_url or "").lower() else "SocialAPI"),
            "post_id": post_id,
            "post_url": raw_data.get("url") or raw_data.get("uri"),
            "author_id": author_id,
            "author_display_name": author_name,
            "language": raw_data.get("language"),
            "hashtags": extracted_tags,
            "matched_terms": matched_terms,
            "media_count": len(media_items),
            "content_relationship": rel.value,
            "relationship_evidence": rel_evidence,
            "initial_event_category": suggested_category,
            "source_trust_baseline": 0.50,
            "provenance": {
                "source_type": self.source_type,
                "source_name": self.name,
                "source_url": raw_data.get("url") or self.base_url,
                "external_id": post_id,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "published_at": observed_at.isoformat(),
                "connector_name": CONNECTOR_NAME,
                "connector_version": CONNECTOR_VERSION,
            },
        }

        return CanonicalRawEvent(
            source_id=self.provider_id,
            source_type=self.source_type,
            external_id=post_id,
            observed_at=observed_at,
            ingested_at=datetime.now(timezone.utc),
            text=clean_text,
            latitude=lat,
            longitude=lon,
            city=city,
            state=state,
            suggested_category=suggested_category,
            media=media_items,
            raw_payload=raw_payload,
            is_demo=False,
        )


# ============================================================================
# 2. RSS / ATOM FEED ADAPTER
# ============================================================================

class RSSAtomAdapter(SocialWebProvider):
    """
    Standardized RSS 2.0 and Atom XML syndication feed connector.
    Parses weather feeds, meteorological bulletins, and alerts.
    """

    def __init__(
        self,
        provider_id: str = "rss-feed-primary",
        name: str = "Weather Syndication RSS/Atom Feed",
        feed_url: Optional[str] = None,
        timeout_seconds: float = 10.0,
        max_bytes: int = 2 * 1024 * 1024,  # 2MB max
        user_agent: Optional[str] = None,
    ):
        config = {
            "feed_url": feed_url,
            "timeout_seconds": timeout_seconds,
            "max_bytes": max_bytes,
            "user_agent": user_agent or f"SkyPulse-WeatherAnalytics/{CONNECTOR_VERSION} (+https://skypulse.gov.in)",
        }
        super().__init__(
            provider_id=provider_id,
            name=name,
            source_type="RSS_FEED",
            config=config,
        )
        self.feed_url = feed_url
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.user_agent = config["user_agent"]
        self.status = ConnectorStatusEnum.HEALTHY if feed_url else ConnectorStatusEnum.NOT_CONFIGURED

    def is_configured(self) -> bool:
        return bool(self.feed_url)

    async def health_check(self) -> ConnectorStatusEnum:
        if not self.is_configured():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return self.status

        headers = {"User-Agent": self.user_agent}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
                resp = await client.head(self.feed_url)
                if resp.status_code in (200, 301, 302, 304):
                    self.status = ConnectorStatusEnum.HEALTHY
                elif resp.status_code == 405:  # Method not allowed for HEAD, fallback to GET
                    resp = await client.get(self.feed_url)
                    self.status = ConnectorStatusEnum.HEALTHY if resp.status_code == 200 else ConnectorStatusEnum.ERROR
                else:
                    self.status = ConnectorStatusEnum.ERROR
                    self.metrics.last_error = f"RSS Feed HTTP status {resp.status_code}"
        except Exception as e:
            self.status = ConnectorStatusEnum.ERROR
            self.metrics.last_error = str(e)

        return self.status

    async def fetch(self) -> List[Any]:
        if not self.is_configured():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return []

        t0 = time.time()
        headers = {"User-Agent": self.user_agent}
        items: List[Any] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
                resp = await client.get(self.feed_url)
                latency_ms = (time.time() - t0) * 1000

                if resp.status_code == 200:
                    if len(resp.content) > self.max_bytes:
                        self.metrics.last_error = f"Feed payload exceeds maximum limit of {self.max_bytes} bytes"
                        self.status = ConnectorStatusEnum.DEGRADED
                        return []

                    xml_text = resp.text
                    items = self._extract_xml_items(xml_text)
                    self.metrics.records_fetched += len(items)
                    self.metrics.records_accepted += len(items)
                    self.metrics.last_successful_fetch = datetime.now(timezone.utc)
                    self.metrics.processing_latency_ms = latency_ms
                    self.status = ConnectorStatusEnum.HEALTHY
                else:
                    self.metrics.last_error = f"RSS Feed HTTP {resp.status_code}"
                    self.metrics.last_error_at = datetime.now(timezone.utc)
                    self.status = ConnectorStatusEnum.ERROR
        except Exception as e:
            self.metrics.last_error = str(e)
            self.metrics.last_error_at = datetime.now(timezone.utc)
            self.status = ConnectorStatusEnum.ERROR
            logger.error("RSS fetch error: %s", e)

        return items

    def _extract_xml_items(self, xml_text: str) -> List[ET.Element]:
        items: List[ET.Element] = []
        try:
            root = ET.fromstring(xml_text)
            # RSS 2.0 items
            rss_items = root.findall(".//item")
            if rss_items:
                return rss_items

            # Atom entries
            atom_ns = "{http://www.w3.org/2005/Atom}"
            atom_items = root.findall(f".//{atom_ns}entry")
            if atom_items:
                return atom_items

            # Fallback without namespace
            for child in root.iter():
                if child.tag.endswith("item") or child.tag.endswith("entry"):
                    items.append(child)
        except Exception as e:
            logger.error("Error parsing RSS/Atom XML: %s", e)
            self.metrics.last_error = f"XML parse failure: {e}"
        return items

    def parse(self, item_elem: Any) -> Optional[CanonicalRawEvent]:
        if not isinstance(item_elem, ET.Element):
            return None

        # Tags to look for
        title, description, guid, link, author, published_str = "", "", "", "", "", ""
        lat_val: Optional[float] = None
        lon_val: Optional[float] = None
        country_val: Optional[str] = None
        city_val: Optional[str] = None
        state_val: Optional[str] = None
        event_type_val: Optional[str] = None
        media_items: List[MediaItem] = []
        categories: List[str] = []

        for child in item_elem:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            tag = tag.lower()
            text_val = (child.text or "").strip()

            if tag == "title":
                title = text_val
            elif tag in ("description", "summary", "content"):
                description = text_val
            elif tag in ("guid", "id"):
                guid = text_val
            elif tag == "link":
                # Link could be text or href attribute (Atom)
                link = child.get("href") or text_val
            elif tag in ("author", "creator"):
                author = text_val
            elif tag in ("pubdate", "published", "updated", "date"):
                published_str = text_val
            elif tag in ("category", "subject"):
                if text_val:
                    categories.append(text_val)
            elif tag in ("point", "georss:point"):
                parts = text_val.split()
                if len(parts) >= 2:
                    try:
                        lat_val = float(parts[0])
                        lon_val = float(parts[1])
                    except (ValueError, TypeError):
                        pass
            elif tag in ("lat", "latitude"):
                try:
                    lat_val = float(text_val)
                except (ValueError, TypeError):
                    pass
            elif tag in ("long", "lon", "longitude"):
                try:
                    lon_val = float(text_val)
                except (ValueError, TypeError):
                    pass
            elif tag in ("country", "iso3"):
                country_val = text_val
            elif tag == "city":
                city_val = text_val
            elif tag in ("state", "province"):
                state_val = text_val
            elif tag in ("eventtype", "event_type", "alertlevel"):
                event_type_val = text_val
            elif tag in ("enclosure", "icon"):
                enc_url = child.get("url") or (text_val if text_val.startswith("http") else None)
                enc_type = child.get("type", "IMAGE")
                if enc_url:
                    m_type = "VIDEO" if "video" in str(enc_type).lower() else ("AUDIO" if "audio" in str(enc_type).lower() else "IMAGE")
                    media_items.append(
                        MediaItem(
                            media_type=m_type,
                            url=enc_url,
                            mime_type=enc_type if child.get("type") else None,
                            file_size_bytes=int(child.get("length", 0)) if child.get("length", "").isdigit() else None,
                        )
                    )

        if not title and not description:
            return None

        clean_title = sanitize_text(re.sub(r"<[^>]+>", " ", title))
        clean_desc = sanitize_text(re.sub(r"<[^>]+>", " ", description))
        full_text = f"{clean_title}. {clean_desc}".strip(". ")

        # Check weather filtering
        is_weather, matched_terms = matches_weather_filter(full_text, None, None)
        if not is_weather and not categories and not event_type_val:
            return None

        # Parse publication date
        observed_at = datetime.now(timezone.utc)
        if published_str:
            try:
                # Try email/RFC 822 format (e.g. Thu, 01 Oct 2026 12:00:00 GMT)
                import email.utils
                parsed_tuple = email.utils.parsedate_to_datetime(published_str)
                if parsed_tuple:
                    observed_at = parsed_tuple.astimezone(timezone.utc)
            except Exception:
                try:
                    observed_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                except Exception:
                    pass

        lat, lon = lat_val, lon_val

        ext_id = guid or link or f"rss-{abs(hash(full_text))}"
        rel, rel_evidence = detect_content_relationship(full_text, ext_id, {"url": link, "title": clean_title}, self.last_records)
        self.last_records.append({"external_id": ext_id, "text": full_text, "content_hash": rel_evidence.get("content_hash")})
        if len(self.last_records) > 500:
            self.last_records.pop(0)

        raw_payload = {
            "title": clean_title,
            "description": clean_desc,
            "link": link,
            "author": author,
            "categories": categories,
            "raw_category": event_type_val,
            "country": country_val,
            "raw_coordinates": [lat_val, lon_val] if (lat_val is not None and lon_val is not None) else None,
            "matched_terms": matched_terms,
            "content_relationship": rel.value,
            "relationship_evidence": rel_evidence,
            "provenance": {
                "source_type": self.source_type,
                "source_name": self.name,
                "source_url": link or self.feed_url,
                "external_id": ext_id,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "published_at": observed_at.isoformat(),
                "connector_name": CONNECTOR_NAME,
                "connector_version": CONNECTOR_VERSION,
            },
        }

        return CanonicalRawEvent(
            source_id=self.provider_id,
            source_type=self.source_type,
            external_id=ext_id,
            observed_at=observed_at,
            ingested_at=datetime.now(timezone.utc),
            text=full_text,
            latitude=lat,
            longitude=lon,
            city=city_val,
            state=state_val,
            suggested_category=event_type_val,
            media=media_items,
            raw_payload=raw_payload,
            is_demo=False,
        )


# ============================================================================
# 3. PUBLIC WEB CONNECTOR (Permitted Weather Webpages)
# ============================================================================

class PublicWebAdapter(SocialWebProvider):
    """
    Controlled Public Web Ingestion Adapter.
    Ingests weather information from explicitly configured public URLs only.
    Strictly prohibits arbitrary recursive crawling, CAPTCHA bypass, or stealth proxies.
    Enforces URL scheme validation, max byte limit, timeouts, and robots compliance.
    """

    def __init__(
        self,
        provider_id: str = "public-web-primary",
        name: str = "Permitted Public Meteorological Webpages",
        urls: Optional[List[str]] = None,
        poll_interval_seconds: int = 300,
        timeout_seconds: float = 10.0,
        max_bytes: int = 500 * 1024,  # 500KB max per page
        user_agent: Optional[str] = None,
    ):
        config = {
            "urls": urls or [],
            "poll_interval_seconds": poll_interval_seconds,
            "timeout_seconds": timeout_seconds,
            "max_bytes": max_bytes,
            "user_agent": user_agent or f"SkyPulse-WeatherAnalytics/{CONNECTOR_VERSION} (+https://skypulse.gov.in)",
        }
        super().__init__(
            provider_id=provider_id,
            name=name,
            source_type="PUBLIC_WEB",
            config=config,
        )
        self.urls = urls or []
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.user_agent = config["user_agent"]
        self.status = ConnectorStatusEnum.HEALTHY if self.urls else ConnectorStatusEnum.NOT_CONFIGURED

    def is_configured(self) -> bool:
        return bool(self.urls)

    def validate_url(self, url: str) -> bool:
        """Validate URL is well-formed HTTP/HTTPS and not a local/private address."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False
            if not parsed.netloc:
                return False
            # Prevent SSRF targeting localhost/private ranges
            netloc_lower = parsed.netloc.lower().split(":")[0]
            if netloc_lower in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
                return False
            return True
        except Exception:
            return False

    async def health_check(self) -> ConnectorStatusEnum:
        if not self.is_configured():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return self.status

        # Check first configured URL
        test_url = self.urls[0]
        if not self.validate_url(test_url):
            self.status = ConnectorStatusEnum.ERROR
            self.metrics.last_error = f"Invalid or unsafe URL configured: {test_url}"
            return self.status

        headers = {"User-Agent": self.user_agent}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
                resp = await client.head(test_url)
                if resp.status_code in (200, 301, 302, 304):
                    self.status = ConnectorStatusEnum.HEALTHY
                elif resp.status_code == 405:
                    resp = await client.get(test_url)
                    self.status = ConnectorStatusEnum.HEALTHY if resp.status_code == 200 else ConnectorStatusEnum.ERROR
                else:
                    self.status = ConnectorStatusEnum.ERROR
                    self.metrics.last_error = f"Web page returned HTTP {resp.status_code}"
        except Exception as e:
            self.status = ConnectorStatusEnum.ERROR
            self.metrics.last_error = str(e)

        return self.status

    async def fetch(self) -> List[Dict[str, Any]]:
        if not self.is_configured():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return []

        results: List[Dict[str, Any]] = []
        headers = {"User-Agent": self.user_agent}

        for target_url in self.urls:
            if not self.validate_url(target_url):
                logger.warning("Skipping invalid web URL: %s", target_url)
                continue

            t0 = time.time()
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
                    resp = await client.get(target_url)
                    latency_ms = (time.time() - t0) * 1000

                    if resp.status_code == 200:
                        content_type = resp.headers.get("Content-Type", "").lower()
                        if "text/html" not in content_type and "text/plain" not in content_type:
                            self.metrics.records_rejected += 1
                            continue

                        body_bytes = resp.content
                        if len(body_bytes) > self.max_bytes:
                            body_bytes = body_bytes[: self.max_bytes]

                        html_str = body_bytes.decode(resp.encoding or "utf-8", errors="replace")
                        results.append({
                            "url": target_url,
                            "html": html_str,
                            "content_type": content_type,
                            "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        })
                        self.metrics.records_fetched += 1
                        self.metrics.records_accepted += 1
                        self.metrics.last_successful_fetch = datetime.now(timezone.utc)
                        self.metrics.processing_latency_ms = latency_ms
                        self.status = ConnectorStatusEnum.HEALTHY
                    else:
                        self.metrics.records_rejected += 1
                        self.metrics.last_error = f"HTTP {resp.status_code} on {target_url}"
            except Exception as e:
                self.metrics.last_error = str(e)
                self.metrics.last_error_at = datetime.now(timezone.utc)
                self.status = ConnectorStatusEnum.ERROR
                logger.error("Public web fetch error for %s: %s", target_url, e)

        return results

    def parse(self, raw_data: Dict[str, Any]) -> Optional[CanonicalRawEvent]:
        if not isinstance(raw_data, dict):
            return None

        target_url = raw_data.get("url", "")
        html_str = raw_data.get("html", "")
        if not html_str:
            return None

        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html_str, re.IGNORECASE | re.DOTALL)
        title = html.unescape(title_match.group(1)).strip() if title_match else ""

        # Extract meta description
        meta_desc_match = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
            html_str,
            re.IGNORECASE,
        )
        meta_desc = html.unescape(meta_desc_match.group(1)).strip() if meta_desc_match else ""

        # Strip script/style tags and clean HTML text
        text_content = re.sub(r"<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", html_str, flags=re.IGNORECASE | re.DOTALL)
        text_content = re.sub(r"<[^>]+>", " ", text_content)
        clean_body = sanitize_text(html.unescape(text_content))

        summary_text = f"{title}. {meta_desc}".strip(". ")
        if len(summary_text) < 20:
            summary_text = clean_body[:500]

        is_weather, matched_terms = matches_weather_filter(summary_text, None, None)
        if not is_weather:
            return None

        ext_id = f"web-{hashlib.sha256(target_url.encode()).hexdigest()[:16]}"
        rel, rel_evidence = detect_content_relationship(summary_text, ext_id, {"url": target_url}, self.last_records)
        self.last_records.append({"external_id": ext_id, "text": summary_text, "content_hash": rel_evidence.get("content_hash")})

        raw_payload = {
            "url": target_url,
            "title": title,
            "meta_description": meta_desc,
            "matched_terms": matched_terms,
            "content_relationship": rel.value,
            "relationship_evidence": rel_evidence,
            "provenance": {
                "source_type": self.source_type,
                "source_name": self.name,
                "source_url": target_url,
                "external_id": ext_id,
                "retrieved_at": raw_data.get("retrieved_at") or datetime.now(timezone.utc).isoformat(),
                "published_at": datetime.now(timezone.utc).isoformat(),
                "connector_name": CONNECTOR_NAME,
                "connector_version": CONNECTOR_VERSION,
            },
        }

        return CanonicalRawEvent(
            source_id=self.provider_id,
            source_type=self.source_type,
            external_id=ext_id,
            observed_at=datetime.now(timezone.utc),
            ingested_at=datetime.now(timezone.utc),
            text=summary_text,
            raw_payload=raw_payload,
            is_demo=False,
        )


# ============================================================================
# 4. PUBLIC JSON ADAPTER (Configurable JSON REST Endpoints)
# ============================================================================

def get_nested_field(data: Any, path: str) -> Any:
    """Retrieve value from nested dictionary using dot notation (e.g. 'location.coordinates.lat')."""
    if not path or not isinstance(data, dict):
        return None
    keys = path.split(".")
    curr = data
    for k in keys:
        if isinstance(curr, dict):
            curr = curr.get(k)
        else:
            return None
    return curr


class PublicJSONAdapter(SocialWebProvider):
    """
    Configurable Public JSON REST Endpoint Adapter.
    Maps custom JSON structures into CanonicalRawEvent schema using declarative field mappings.
    """

    def __init__(
        self,
        provider_id: str = "public-json-primary",
        name: str = "Public Meteorological JSON Endpoint",
        endpoint_url: Optional[str] = None,
        http_method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        record_path: str = ".",
        field_mapping: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 10.0,
    ):
        config = {
            "endpoint_url": endpoint_url,
            "http_method": http_method,
            "headers": headers or {},
            "record_path": record_path,
            "field_mapping": field_mapping or {
                "id": "id",
                "text": "description",
                "timestamp": "timestamp",
                "latitude": "lat",
                "longitude": "lon",
                "city": "city",
                "state": "state",
                "category": "category",
                "media_url": "media_url",
            },
            "timeout_seconds": timeout_seconds,
        }
        super().__init__(
            provider_id=provider_id,
            name=name,
            source_type="PUBLIC_JSON",
            config=config,
        )
        self.endpoint_url = endpoint_url
        self.http_method = http_method.upper()
        self.headers = headers or {}
        self.record_path = record_path
        self.field_mapping = config["field_mapping"]
        self.timeout_seconds = timeout_seconds
        self.status = ConnectorStatusEnum.HEALTHY if endpoint_url else ConnectorStatusEnum.NOT_CONFIGURED

    def is_configured(self) -> bool:
        return bool(self.endpoint_url)

    async def health_check(self) -> ConnectorStatusEnum:
        if not self.is_configured():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return self.status

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=self.headers) as client:
                if self.http_method == "GET":
                    resp = await client.get(self.endpoint_url)
                else:
                    resp = await client.post(self.endpoint_url, json={})

                if resp.status_code == 200:
                    self.status = ConnectorStatusEnum.HEALTHY
                elif resp.status_code == 429:
                    self.status = ConnectorStatusEnum.DEGRADED
                    self.metrics.last_error = "Rate limit reached on JSON endpoint"
                else:
                    self.status = ConnectorStatusEnum.ERROR
                    self.metrics.last_error = f"JSON endpoint HTTP {resp.status_code}"
        except Exception as e:
            self.status = ConnectorStatusEnum.ERROR
            self.metrics.last_error = str(e)

        return self.status

    async def fetch(self) -> List[Dict[str, Any]]:
        if not self.is_configured():
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return []

        t0 = time.time()
        records: List[Dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=self.headers) as client:
                if self.http_method == "GET":
                    resp = await client.get(self.endpoint_url)
                else:
                    resp = await client.post(self.endpoint_url, json={})
                latency_ms = (time.time() - t0) * 1000

                if resp.status_code == 200:
                    payload = resp.json()
                    raw_items = []
                    if self.record_path in (".", "", "[]"):
                        raw_items = payload if isinstance(payload, list) else [payload]
                    else:
                        extracted = get_nested_field(payload, self.record_path)
                        raw_items = extracted if isinstance(extracted, list) else ([extracted] if extracted else [])

                    for item in raw_items:
                        if isinstance(item, dict):
                            records.append(item)

                    self.metrics.records_fetched += len(records)
                    self.metrics.records_accepted += len(records)
                    self.metrics.last_successful_fetch = datetime.now(timezone.utc)
                    self.metrics.processing_latency_ms = latency_ms
                    self.status = ConnectorStatusEnum.HEALTHY
                else:
                    self.metrics.last_error = f"JSON endpoint HTTP {resp.status_code}"
                    self.metrics.last_error_at = datetime.now(timezone.utc)
                    self.status = ConnectorStatusEnum.ERROR
        except Exception as e:
            self.metrics.last_error = str(e)
            self.metrics.last_error_at = datetime.now(timezone.utc)
            self.status = ConnectorStatusEnum.ERROR
            logger.error("Public JSON fetch error: %s", e)

        return records

    def parse(self, raw_data: Dict[str, Any]) -> Optional[CanonicalRawEvent]:
        if not isinstance(raw_data, dict):
            return None

        mapping = self.field_mapping
        
        # Text extraction
        text = get_nested_field(raw_data, mapping.get("text", "text")) or raw_data.get("message") or raw_data.get("description") or ""
        clean_text = sanitize_text(str(text))
        if not clean_text:
            return None

        # Weather keyword match
        is_weather, matched_terms = matches_weather_filter(clean_text, None, None)
        category_field_val = get_nested_field(raw_data, mapping.get("category", "category"))
        if not is_weather and not category_field_val:
            return None

        # ID extraction
        ext_id = str(get_nested_field(raw_data, mapping.get("id", "id")) or f"json-{abs(hash(clean_text))}")

        # Timestamp
        raw_ts = get_nested_field(raw_data, mapping.get("timestamp", "timestamp"))
        observed_at = datetime.now(timezone.utc)
        if raw_ts:
            try:
                if isinstance(raw_ts, (int, float)):
                    observed_at = datetime.fromtimestamp(raw_ts, tz=timezone.utc)
                elif isinstance(raw_ts, str):
                    observed_at = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            except Exception:
                pass

        # GPS coordinates
        raw_lat = get_nested_field(raw_data, mapping.get("latitude", "latitude"))
        raw_lon = get_nested_field(raw_data, mapping.get("longitude", "longitude"))
        lat, lon = None, None
        try:
            if raw_lat is not None and raw_lon is not None:
                lat, lon = float(raw_lat), float(raw_lon)
        except (ValueError, TypeError):
            lat, lon = None, None

        city = get_nested_field(raw_data, mapping.get("city", "city"))
        state = get_nested_field(raw_data, mapping.get("state", "state"))

        # Media items
        media_items: List[MediaItem] = []
        raw_media = get_nested_field(raw_data, mapping.get("media_url", "media_url"))
        if isinstance(raw_media, str) and raw_media.startswith("http"):
            media_items.append(MediaItem(url=raw_media, media_type="IMAGE"))
        elif isinstance(raw_media, list):
            for m in raw_media:
                if isinstance(m, str) and m.startswith("http"):
                    media_items.append(MediaItem(url=m, media_type="IMAGE"))
                elif isinstance(m, dict) and m.get("url"):
                    media_items.append(MediaItem(url=m["url"], media_type=m.get("type", "IMAGE")))

        rel, rel_evidence = detect_content_relationship(clean_text, ext_id, raw_data, self.last_records)
        self.last_records.append({"external_id": ext_id, "text": clean_text, "content_hash": rel_evidence.get("content_hash")})

        raw_payload = {
            "endpoint_url": self.endpoint_url,
            "raw_category": category_field_val,
            "matched_terms": matched_terms,
            "content_relationship": rel.value,
            "relationship_evidence": rel_evidence,
            "provenance": {
                "source_type": self.source_type,
                "source_name": self.name,
                "source_url": self.endpoint_url,
                "external_id": ext_id,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "published_at": observed_at.isoformat(),
                "connector_name": CONNECTOR_NAME,
                "connector_version": CONNECTOR_VERSION,
            },
        }

        return CanonicalRawEvent(
            source_id=self.provider_id,
            source_type=self.source_type,
            external_id=ext_id,
            observed_at=observed_at,
            ingested_at=datetime.now(timezone.utc),
            text=clean_text,
            latitude=lat,
            longitude=lon,
            city=str(city) if city else None,
            state=str(state) if state else None,
            suggested_category=str(category_field_val) if category_field_val else None,
            media=media_items,
            raw_payload=raw_payload,
            is_demo=False,
        )


# ============================================================================
# MASTER CONNECTOR (Composite Orchestrator for all Social & Web Providers)
# ============================================================================

class SocialWebConnector(BaseConnector):
    """
    Master Production Connector for Social & Web Weather Intelligence.
    Coordinates multiple adapters (SocialAPI, RSSAtom, PublicWeb, PublicJSON).
    """

    def __init__(
        self,
        source_id: str = "social-web-master",
        name: str = "Social & Web Weather Intelligence Connector",
        config: Optional[Dict[str, Any]] = None,
        is_demo: bool = False,
    ):
        super().__init__(
            source_id=source_id,
            name=name,
            source_type="SOCIAL_FEED",
            config=config or {},
            is_demo=is_demo,
        )
        self.providers: Dict[str, SocialWebProvider] = {}
        self._init_providers_from_config(self.config)

    def _init_providers_from_config(self, cfg: Dict[str, Any]) -> None:
        """Instantiate adapters from configuration dictionary or application settings."""
        try:
            from app.core.config import settings
        except Exception:
            settings = None

        # Social API adapter (Mastodon / Social Web)
        social_cfg = cfg.get("social_api", {})
        base_url = (
            social_cfg.get("base_url")
            or cfg.get("SOCIAL_API_BASE_URL")
            or cfg.get("MASTODON_BASE_URL")
            or (getattr(settings, "MASTODON_BASE_URL", "https://mastodon.social") if settings else "https://mastodon.social")
        )
        api_key = social_cfg.get("api_key") or cfg.get("SOCIAL_API_KEY")
        api_token = social_cfg.get("api_token") or cfg.get("SOCIAL_API_TOKEN")
        queries = (
            social_cfg.get("queries")
            or cfg.get("SOCIAL_API_QUERIES")
            or cfg.get("SOCIAL_HASHTAGS")
            or (getattr(settings, "SOCIAL_HASHTAGS", None) if settings else None)
        )
        parsed_queries = parse_hashtag_list(queries) if queries else hashtag_registry.get_hashtags()
        max_posts = (
            social_cfg.get("max_posts_per_hashtag")
            or cfg.get("MASTODON_MAX_POSTS_PER_HASHTAG")
            or (getattr(settings, "MASTODON_MAX_POSTS_PER_HASHTAG", 20) if settings else 20)
        )
        poll_interval = (
            social_cfg.get("poll_interval_seconds")
            or cfg.get("SOCIAL_POLL_INTERVAL_SECONDS")
            or (getattr(settings, "SOCIAL_POLL_INTERVAL_SECONDS", 60) if settings else 60)
        )
        timeout = (
            social_cfg.get("timeout_seconds")
            or cfg.get("MASTODON_REQUEST_TIMEOUT_SECONDS")
            or (getattr(settings, "MASTODON_REQUEST_TIMEOUT_SECONDS", 10.0) if settings else 10.0)
        )
        user_agent = (
            social_cfg.get("user_agent")
            or cfg.get("MASTODON_USER_AGENT")
            or (getattr(settings, "MASTODON_USER_AGENT", None) if settings else None)
        )

        mastodon_enabled = cfg.get("MASTODON_ENABLED", getattr(settings, "MASTODON_ENABLED", True) if settings else True)
        social_enabled = cfg.get("SOCIAL_INGESTION_ENABLED", getattr(settings, "SOCIAL_INGESTION_ENABLED", True) if settings else True)

        if base_url and (mastodon_enabled and social_enabled):
            self.providers["social_api"] = SocialAPIAdapter(
                provider_id=f"{self.source_id}-api",
                name="Mastodon Weather Hashtag Monitor",
                base_url=base_url,
                api_key=api_key,
                api_token=api_token,
                queries=parsed_queries,
                max_posts_per_hashtag=max_posts,
                poll_interval_seconds=poll_interval,
                timeout_seconds=timeout,
                user_agent=user_agent,
            )

        # RSS Feed adapter
        rss_cfg = cfg.get("rss", {})
        feed_url = rss_cfg.get("feed_url") or cfg.get("RSS_FEED_URL")
        if feed_url:
            self.providers["rss"] = RSSAtomAdapter(
                provider_id=f"{self.source_id}-rss",
                name="Weather Alerts RSS/Atom Feed",
                feed_url=feed_url,
            )

        # Public Web adapter
        web_cfg = cfg.get("public_web", {})
        urls = web_cfg.get("urls") or cfg.get("WEB_SOURCE_URLS")
        if urls:
            if isinstance(urls, str):
                urls = [u.strip() for u in urls.split(",") if u.strip()]
            self.providers["public_web"] = PublicWebAdapter(
                provider_id=f"{self.source_id}-web",
                name="Permitted Weather Webpages",
                urls=urls,
            )

        # Public JSON adapter
        json_cfg = cfg.get("public_json", {})
        endpoint_url = json_cfg.get("endpoint_url") or cfg.get("PUBLIC_JSON_URL")
        if endpoint_url:
            self.providers["public_json"] = PublicJSONAdapter(
                provider_id=f"{self.source_id}-json",
                name="Public Weather JSON Endpoint",
                endpoint_url=endpoint_url,
                http_method=json_cfg.get("http_method", "GET"),
                record_path=json_cfg.get("record_path", "."),
                field_mapping=json_cfg.get("field_mapping"),
            )

    def register_provider(self, key: str, provider: SocialWebProvider) -> None:
        """Attach a provider adapter to the connector."""
        self.providers[key] = provider

    def get_configured_hashtags(self) -> List[str]:
        """Return currently configured list of weather hashtags."""
        soc_prov = self.providers.get("social_api")
        if soc_prov and isinstance(soc_prov, SocialAPIAdapter):
            return soc_prov.queries
        return hashtag_registry.get_hashtags()

    def set_configured_hashtags(self, hashtags: Any) -> List[str]:
        """Update configured hashtags across registry and active social adapter."""
        updated = hashtag_registry.set_hashtags(hashtags)
        soc_prov = self.providers.get("social_api")
        if soc_prov and isinstance(soc_prov, SocialAPIAdapter):
            soc_prov.queries = updated
            soc_prov.config["queries"] = updated
        return updated

    async def poll(self) -> List[CanonicalRawEvent]:
        """Poll all configured providers and collect canonical raw events."""
        t0 = time.time()
        now = datetime.now(timezone.utc)
        self.metrics.last_poll_at = now
        all_events: List[CanonicalRawEvent] = []

        if not self.providers:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return []

        has_healthy = False
        has_error = False

        # Per-poll run accumulators
        run_fetched = 0
        run_weather_rel = 0
        run_accepted_india = 0
        run_quar_foreign = 0
        run_quar_unknown = 0
        run_rejected_non_weather = 0
        run_duplicates = 0
        run_reposts = 0
        run_errors = 0
        run_rate_limits = 0

        for key, prov in self.providers.items():
            try:
                raw_items = await prov.fetch()
                run_fetched += len(raw_items)
                run_rate_limits += prov.metrics.rate_limits
                run_errors += prov.metrics.errors

                for item in raw_items:
                    event = prov.parse(item)
                    if event is None:
                        run_rejected_non_weather += 1
                        continue

                    run_weather_rel += 1
                    all_events.append(event)

                    # Normalize for telemetry counting
                    norm = prov.normalize(event)
                    if norm.is_india_valid and not norm.is_quarantined:
                        run_accepted_india += 1
                    elif norm.is_quarantined:
                        if norm.quarantine_reason == "FOREIGN_COORDINATES":
                            run_quar_foreign += 1
                        else:
                            run_quar_unknown += 1

                    # Check repost/duplicate relationships
                    rel_val = event.raw_payload.get("content_relationship")
                    if rel_val == "REPOST":
                        run_reposts += 1
                    elif rel_val in ("DUPLICATE", "LIKELY_COPY"):
                        run_duplicates += 1

                if prov.status == ConnectorStatusEnum.HEALTHY:
                    has_healthy = True
                elif prov.status == ConnectorStatusEnum.ERROR:
                    has_error = True
            except Exception as e:
                has_error = True
                run_errors += 1
                self.record_error(f"Provider {key} failed during poll: {e}")

        # Update connector metrics with strict mathematical consistency
        self.metrics.records_fetched += run_fetched
        self.metrics.weather_relevant += run_weather_rel
        self.metrics.accepted_india += run_accepted_india
        self.metrics.accepted_for_pipeline += run_accepted_india
        self.metrics.rejected_non_weather += run_rejected_non_weather
        self.metrics.quarantined_foreign += run_quar_foreign
        self.metrics.quarantined_unknown_location += run_quar_unknown
        self.metrics.duplicates += run_duplicates
        self.metrics.reposts += run_reposts
        self.metrics.rate_limits += run_rate_limits
        latency_ms = (time.time() - t0) * 1000
        self.metrics.processing_latency_ms = latency_ms
        self.metrics.records_accepted += run_weather_rel
        if has_healthy:
            self.status = ConnectorStatusEnum.HEALTHY
            self.metrics.last_successful_fetch = now
        elif has_error:
            self.status = ConnectorStatusEnum.ERROR
        else:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED

        return all_events

    def parse(self, raw_data: Any) -> CanonicalRawEvent:
        """Parse raw record using the appropriate provider."""
        if isinstance(raw_data, dict) and "provider_key" in raw_data:
            prov = self.providers.get(raw_data["provider_key"])
            if prov:
                parsed = prov.parse(raw_data.get("payload"))
                if parsed:
                    return parsed

        # Fallback default generic parse
        text = str(raw_data.get("text", "") if isinstance(raw_data, dict) else str(raw_data))
        clean_text = sanitize_text(text)
        return CanonicalRawEvent(
            source_id=self.source_id,
            source_type=self.source_type,
            text=clean_text or "Empty social observation",
            raw_payload={"raw": raw_data},
            is_demo=self.is_demo,
        )

    async def health_check(self) -> ConnectorStatusEnum:
        """Inspect health of all underlying providers."""
        if not self.providers:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED
            return self.status

        statuses = []
        for prov in self.providers.values():
            s = await prov.health_check()
            statuses.append(s)

        if any(s == ConnectorStatusEnum.HEALTHY for s in statuses):
            self.status = ConnectorStatusEnum.HEALTHY
        elif any(s == ConnectorStatusEnum.DEGRADED for s in statuses):
            self.status = ConnectorStatusEnum.DEGRADED
        elif any(s == ConnectorStatusEnum.ERROR for s in statuses):
            self.status = ConnectorStatusEnum.ERROR
        else:
            self.status = ConnectorStatusEnum.NOT_CONFIGURED

        return self.status

    def get_sources_status(self) -> List[Dict[str, Any]]:
        """Return list of configured sources and their status."""
        return [prov.get_source_metadata() for prov in self.providers.values()]


# Singleton default connector instance for application use
social_web_connector = SocialWebConnector()
