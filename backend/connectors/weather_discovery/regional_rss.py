"""
SkyPulse Regional RSS Feed Connector
======================================
Polls curated regional Indian news RSS/Atom feeds and official government
alert RSS feeds (NDMA SACHET CAP, IMD public, CWC, state government).

Sources covered
---------------
OFFICIAL / GOVERNMENT:
  - NDMA SACHET CAP alerts (cap.ndma.gov.in)
  - IMD public forecast RSS (mausam.imd.gov.in)
  - CWC flood bulletin RSS
  - India.gov.in press releases

REGIONAL NEWS (RSS-first, no scraping):
  - The Hindu (national + regional editions)
  - NDTV (India)
  - India Today
  - Dainik Jagran (Hindi)
  - Amar Ujala (Hindi)
  - Anandabazar Patrika (Bengali)
  - Mathrubhumi (Malayalam)
  - The New Indian Express (South)
  - Deccan Herald (Karnataka)
  - Odisha TV / Pragativadi (Odia)
  - Telegraphindia (West Bengal / NE)

Source Trust mapping (aligned with SkyPulse SourceType enum)
------------------------------------------------------------
  - OFFICIAL/NDMA/IMD    → SourceType.OFFICIAL
  - State Government      → SourceType.GOVERNMENT
  - National News         → SourceType.NEWS_PUBLISHER
  - Regional vernacular   → SourceType.NEWS_PUBLISHER

Each CanonicalRawEvent produced here is:
  - Weather-relevance filtered
  - Duplicate-checked via idempotency_key
  - Location-enriched from title/description
  - Sent to the normalizer → Kafka → AI pipeline
"""

import email.utils
import hashlib
import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum
from connectors.weather_discovery.multilingual_keywords import KEYWORDS

logger = logging.getLogger("skypulse.connectors.regional_rss")

# ---------------------------------------------------------------------------
# RSS Feed Registry
# ---------------------------------------------------------------------------

@dataclass
class RSSFeedConfig:
    """Configuration for a single regional RSS feed."""
    url: str
    name: str
    source_type: str          # OFFICIAL | GOVERNMENT | NEWS_PUBLISHER | SOCIAL_SIGNAL
    language: str             # ISO 639-1
    state_coverage: List[str] = field(default_factory=list)  # empty = national
    trust_score: float = 0.5  # 0.0 – 1.0
    requires_weather_filter: bool = True  # filter non-weather items?
    timeout_s: float = 12.0
    enabled: bool = True


# Complete feed registry
# Complete feed registry (30 feeds)
RSS_FEEDS: List[RSSFeedConfig] = [
    # ── OFFICIAL / GOVERNMENT ──────────────────────────────────────────────
    RSSFeedConfig(
        url="https://sachet.ndma.gov.in/cap_public_website/getAllCapAlert",
        name="NDMA SACHET CAP Feed",
        source_type="OFFICIAL",
        language="en",
        trust_score=0.98,
        requires_weather_filter=False,
    ),
    RSSFeedConfig(
        url="https://imd.gov.in/pages/rss/weather_forecast.xml",
        name="IMD Forecast RSS",
        source_type="OFFICIAL",
        language="en",
        trust_score=0.97,
        requires_weather_filter=False,
    ),
    RSSFeedConfig(
        url="https://www.imd.gov.in/pages/rss/warnings.xml",
        name="IMD Warnings RSS",
        source_type="OFFICIAL",
        language="en",
        trust_score=0.97,
        requires_weather_filter=False,
    ),
    RSSFeedConfig(
        url="https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
        name="PIB Environment/Weather Releases",
        source_type="GOVERNMENT",
        language="en",
        trust_score=0.88,
        requires_weather_filter=True,
    ),
    RSSFeedConfig(
        url="https://cwc.gov.in/rss.xml",
        name="CWC Flood Bulletin",
        source_type="OFFICIAL",
        language="en",
        trust_score=0.95,
        requires_weather_filter=False,
    ),
    # ── NATIONAL NEWS (ENGLISH) ────────────────────────────────────────────
    RSSFeedConfig(
        url="https://feeds.feedburner.com/ndtvnews-india-news",
        name="NDTV India News",
        source_type="NEWS_PUBLISHER",
        language="en",
        trust_score=0.75,
    ),
    RSSFeedConfig(
        url="https://www.indiatoday.in/rss/1206578",
        name="India Today Weather",
        source_type="NEWS_PUBLISHER",
        language="en",
        trust_score=0.75,
    ),
    RSSFeedConfig(
        url="https://www.thehindu.com/news/national/feeder/default.rss",
        name="The Hindu National",
        source_type="NEWS_PUBLISHER",
        language="en",
        trust_score=0.80,
    ),
    RSSFeedConfig(
        url="https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms",
        name="Times of India India News",
        source_type="NEWS_PUBLISHER",
        language="en",
        trust_score=0.75,
    ),
    RSSFeedConfig(
        url="https://indianexpress.com/feed/",
        name="Indian Express",
        source_type="NEWS_PUBLISHER",
        language="en",
        trust_score=0.78,
    ),
    RSSFeedConfig(
        url="https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
        name="Hindustan Times India",
        source_type="NEWS_PUBLISHER",
        language="en",
        trust_score=0.75,
    ),
    RSSFeedConfig(
        url="https://www.news18.com/rss/india.xml",
        name="News18 India",
        source_type="NEWS_PUBLISHER",
        language="en",
        trust_score=0.70,
    ),
    RSSFeedConfig(
        url="https://zeenews.india.com/rss/india-national-news.xml",
        name="Zee News National",
        source_type="NEWS_PUBLISHER",
        language="en",
        trust_score=0.72,
    ),
    # ── REGIONAL EDITIONS (ENGLISH & VERNACULAR) ──────────────────────────
    RSSFeedConfig(
        url="https://feeds.feedburner.com/ndtvnews-cities-news",
        name="NDTV Regional Cities",
        source_type="NEWS_PUBLISHER",
        language="en",
        trust_score=0.74,
    ),
    RSSFeedConfig(
        url="https://www.thehindu.com/news/cities/chennai/feeder/default.rss",
        name="The Hindu Chennai",
        source_type="NEWS_PUBLISHER",
        language="en",
        state_coverage=["Tamil Nadu"],
        trust_score=0.80,
    ),
    RSSFeedConfig(
        url="https://www.thehindu.com/news/national/karnataka/feeder/default.rss",
        name="The Hindu Karnataka",
        source_type="NEWS_PUBLISHER",
        language="en",
        state_coverage=["Karnataka"],
        trust_score=0.80,
    ),
    RSSFeedConfig(
        url="https://www.thehindu.com/news/national/kerala/feeder/default.rss",
        name="The Hindu Kerala",
        source_type="NEWS_PUBLISHER",
        language="en",
        state_coverage=["Kerala"],
        trust_score=0.80,
    ),
    RSSFeedConfig(
        url="https://www.thehindu.com/news/national/andhra-pradesh/feeder/default.rss",
        name="The Hindu Andhra Pradesh",
        source_type="NEWS_PUBLISHER",
        language="en",
        state_coverage=["Andhra Pradesh", "Telangana"],
        trust_score=0.80,
    ),
    RSSFeedConfig(
        url="https://www.thehindu.com/news/cities/mumbai/feeder/default.rss",
        name="The Hindu Mumbai",
        source_type="NEWS_PUBLISHER",
        language="en",
        state_coverage=["Maharashtra"],
        trust_score=0.80,
    ),
    RSSFeedConfig(
        url="https://www.thehindu.com/news/cities/kolkata/feeder/default.rss",
        name="The Hindu Kolkata",
        source_type="NEWS_PUBLISHER",
        language="en",
        state_coverage=["West Bengal"],
        trust_score=0.80,
    ),
    RSSFeedConfig(
        url="https://www.thehindu.com/news/cities/Delhi/feeder/default.rss",
        name="The Hindu Delhi",
        source_type="NEWS_PUBLISHER",
        language="en",
        state_coverage=["Delhi"],
        trust_score=0.80,
    ),
    RSSFeedConfig(
        url="https://odishatv.in/feed",
        name="OdishaTV",
        source_type="NEWS_PUBLISHER",
        language="en",
        state_coverage=["Odisha"],
        trust_score=0.72,
    ),
    RSSFeedConfig(
        url="https://pragativadi.com/feed/",
        name="Pragativadi Odisha",
        source_type="NEWS_PUBLISHER",
        language="en",
        state_coverage=["Odisha"],
        trust_score=0.75,
    ),
    RSSFeedConfig(
        url="https://kalingatv.com/feed/",
        name="Kalinga TV",
        source_type="NEWS_PUBLISHER",
        language="en",
        state_coverage=["Odisha"],
        trust_score=0.74,
    ),
    RSSFeedConfig(
        url="https://sambadenglish.com/feed/",
        name="Sambad English",
        source_type="NEWS_PUBLISHER",
        language="en",
        state_coverage=["Odisha"],
        trust_score=0.75,
    ),
    RSSFeedConfig(
        url="https://prameyanews.com/feed/",
        name="Prameya News",
        source_type="NEWS_PUBLISHER",
        language="en",
        state_coverage=["Odisha"],
        trust_score=0.72,
    ),
    # ── HINDI (NATIONAL & REGIONAL) ───────────────────────────────────────
    RSSFeedConfig(
        url="https://rss.jagran.com/rss/news/national.xml",
        name="Dainik Jagran National",
        source_type="NEWS_PUBLISHER",
        language="hi",
        trust_score=0.72,
    ),
    RSSFeedConfig(
        url="https://www.amarujala.com/rss/india-news.xml",
        name="Amar Ujala India",
        source_type="NEWS_PUBLISHER",
        language="hi",
        trust_score=0.70,
    ),
    RSSFeedConfig(
        url="https://www.bhaskar.com/rss-feed/1061/",
        name="Dainik Bhaskar",
        source_type="NEWS_PUBLISHER",
        language="hi",
        trust_score=0.70,
    ),
    RSSFeedConfig(
        url="https://zeenews.india.com/hindi/india.xml",
        name="Zee News Hindi",
        source_type="NEWS_PUBLISHER",
        language="hi",
        trust_score=0.70,
    ),
    # ── REGIONAL VERNACULAR (BENGALI, TAMIL, TELUGU, MARATHI) ─────────────
    RSSFeedConfig(
        url="https://www.sangbadpratidin.in/feed/",
        name="Sangbad Pratidin (WB)",
        source_type="NEWS_PUBLISHER",
        language="bn",
        state_coverage=["West Bengal"],
        trust_score=0.72,
    ),
    RSSFeedConfig(
        url="https://www.hindutamil.in/feed",
        name="Hindu Tamil Thisai",
        source_type="NEWS_PUBLISHER",
        language="ta",
        state_coverage=["Tamil Nadu"],
        trust_score=0.72,
    ),
    RSSFeedConfig(
        url="https://www.sakshi.com/rss.xml",
        name="Sakshi Telugu",
        source_type="NEWS_PUBLISHER",
        language="te",
        state_coverage=["Andhra Pradesh", "Telangana"],
        trust_score=0.70,
    ),
    RSSFeedConfig(
        url="https://www.lokmat.com/rss/maharashtra.xml",
        name="Lokmat Maharashtra",
        source_type="NEWS_PUBLISHER",
        language="mr",
        state_coverage=["Maharashtra"],
        trust_score=0.72,
    ),
]

# ---------------------------------------------------------------------------
# Weather relevance keywords & filter
# ---------------------------------------------------------------------------

_WEATHER_TERMS_EN: List[str] = [
    "rain", "rainfall", "storm", "cyclone", "flood", "flooding", "heatwave",
    "heat wave", "fog", "dense fog", "dust storm", "dust", "thunderstorm",
    "lightning", "monsoon", "drought", "cloudburst", "landslide", "cold wave",
    "frost", "hailstorm", "weather warning", "imd", "ndma", "sachet",
    "inundation", "waterlogging", "depression", "gale", "squall",
    "red alert", "orange alert", "yellow alert", "weather alert",
    "temperature", "humidity", "pressure", "wind speed",
]

# Collect all multilingual keywords flattened
_MULTILINGUAL_WEATHER_TERMS: List[str] = []
for _ev, _lang_map in KEYWORDS.items():
    for _lang, _kws in _lang_map.items():
        _MULTILINGUAL_WEATHER_TERMS.extend([k.lower() for k in _kws])

_ALL_WEATHER_TERMS = set(_WEATHER_TERMS_EN + _MULTILINGUAL_WEATHER_TERMS)

# Non-weather / political metaphorical patterns that must be rejected
_METAPHOR_PATTERNS = [
    re.compile(r"\bpolitical\s+storm\b", re.IGNORECASE),
    re.compile(r"\b(storm|firestorm)\s+(in|hits|inside|rocks|shakes|roils|engulfs)\s+(parliament|lok\s+sabha|rajya\s+sabha|assembly|congress|bjp|aap|cabinet|government|ministry|politics|court|supreme\s+court)\b", re.IGNORECASE),
    re.compile(r"\b(parliament|lok\s+sabha|rajya\s+sabha|assembly|opposition|bjp|congress|political)\s+.*?\b(storm|firestorm)\b", re.IGNORECASE),
    re.compile(r"\bstorm\s+hits\s+parliament\b", re.IGNORECASE),
    re.compile(r"\bstorm\s+over\s+(allegations?|scam|controversy|bill|election|speech|remark|budget|protest|resignation)\b", re.IGNORECASE),
    re.compile(r"\bflood\s+of\s+(applications?|complaints?|wishes?|tributes?|congratulations?|messages?|requests?|memes?|reactions?|queries)\b", re.IGNORECASE),
    re.compile(r"\b(wave|flood)\s+of\s+protests?\b", re.IGNORECASE),
    re.compile(r"\b(brainstorm|teacup)\b", re.IGNORECASE),
]

_EXPLICIT_MET_OVERRIDE = re.compile(
    r"\b(rainfall|precipitation|celsius|temperature|wind\s+speed|monsoon|imd|inundat|waterlog|cloudburst|cyclone|depression|cyclonic|hailstorm|cold\s+wave|heatwave|weather\s+forecast|meteorological|\d+\s*mm|\d+\s*cm)\b",
    re.IGNORECASE,
)

_UNAMBIGUOUS_WEATHER = [
    "rainfall", "heavy rain", "torrential rain", "cyclone", "flood", "flooding",
    "flood warning", "cloudburst", "landslide", "hailstorm", "heatwave", "heat wave",
    "cold wave", "waterlogging", "inundation", "thunderstorm", "dust storm",
    "dense fog", "red alert", "orange alert", "monsoon", "weather warning",
]


def is_weather_relevant(text: str) -> bool:
    """
    Validates weather relevance using WeatherRelevanceEngine,
    rejecting metaphorical, political, drill, infrastructure, and non-meteorological false positives.
    """
    if not text:
        return False
    try:
        from connectors.weather_relevance_engine import WeatherRelevanceEngine
        assessment = WeatherRelevanceEngine.evaluate(text=text)
        return assessment.is_relevant
    except Exception:
        # Fallback to local regex check if import error
        low = text.lower()
        for pat in _METAPHOR_PATTERNS:
            if pat.search(low) and not _EXPLICIT_MET_OVERRIDE.search(low):
                return False
        return any(term in low for term in _ALL_WEATHER_TERMS)


_is_weather_relevant = is_weather_relevant

ATOM_NS = "{http://www.w3.org/2005/Atom}"
MEDIA_NS = "{http://search.yahoo.com/mrss/}"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 SkyPulse-WeatherIntelligence/2.0 (+https://skypulse.gov.in)"


def _clean_html(raw: str) -> str:
    """Strip HTML tags and unescape entities."""
    if not raw:
        return ""
    raw = html.unescape(raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    """Parse RFC 822 or ISO date strings to UTC datetime."""
    if not raw:
        return None
    try:
        return email.utils.parsedate_to_datetime(raw.strip())
    except Exception:
        pass
    # Try ISO 8601
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw.strip()[:25], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue
    return None


def _sanitize_xml(xml_text: str) -> str:
    """Strip UTF-8 BOM and repair bare ampersands before parsing."""
    xml_text = xml_text.lstrip("\ufeff")
    xml_text = re.sub(r"&(?!(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)", "&amp;", xml_text)
    return xml_text


def parse_rss_feed(
    xml_text: str,
    feed_config: RSSFeedConfig,
    source_id: str,
    max_items: int = 20,
) -> List[CanonicalRawEvent]:
    """
    Parse RSS 2.0 / Atom feed XML into CanonicalRawEvent list.
    Applies weather-relevance filter if feed_config.requires_weather_filter is True.
    """
    events: List[CanonicalRawEvent] = []
    xml_text = _sanitize_xml(xml_text)

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning("XML parse error for feed '%s': %s", feed_config.name, e)
        return events

    # Detect format: RSS 2.0 vs Atom
    items = root.findall(".//item")
    is_atom = not items
    if is_atom:
        items = root.findall(f".//{ATOM_NS}entry")

    for item in items[:max_items]:
        try:
            if is_atom:
                title = (item.findtext(f"{ATOM_NS}title") or "").strip()
                desc = (item.findtext(f"{ATOM_NS}summary") or
                        item.findtext(f"{ATOM_NS}content") or "").strip()
                link = ""
                link_el = item.find(f"{ATOM_NS}link")
                if link_el is not None:
                    link = link_el.get("href", "")
                pub_date = item.findtext(f"{ATOM_NS}published") or item.findtext(f"{ATOM_NS}updated")
                guid = item.findtext(f"{ATOM_NS}id") or link
            else:
                title = (item.findtext("title") or "").strip()
                desc = (item.findtext("description") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = item.findtext("pubDate")
                guid = item.findtext("guid") or link

            title = _clean_html(title)
            desc = _clean_html(desc)

            full_text = f"{title}. {desc}".strip(". ")
            if not full_text:
                continue

            # Weather relevance gate
            if feed_config.requires_weather_filter and not _is_weather_relevant(full_text):
                continue

            observed_at = _parse_date(pub_date) or datetime.now(timezone.utc)

            # Location extraction (Sections 5, 6, 7, 8, 9, 10)
            from connectors.weather_discovery.india_locations import resolve_article_locations
            state_hint = feed_config.state_coverage[0] if (feed_config.state_coverage and len(feed_config.state_coverage) == 1) else None
            loc_res = resolve_article_locations(title=title, text=full_text, metadata={"state": state_hint})

            # Build stable idempotency key
            dedup_src = guid or link or full_text
            idem_key = "regional-rss-" + hashlib.sha256(dedup_src.encode()).hexdigest()[:20]

            events.append(
                CanonicalRawEvent(
                    source_id=source_id,
                    source_type=feed_config.source_type,
                    external_id=guid or idem_key,
                    observed_at=observed_at,
                    text=full_text[:1000],
                    city=loc_res["primary_city"],
                    district=loc_res["primary_district"],
                    state=loc_res["primary_state"],
                    latitude=loc_res["latitude"],
                    longitude=loc_res["longitude"],
                    location_source=loc_res["resolution_method"],
                    location_confidence="HIGH" if loc_res["primary_city"] else ("MEDIUM" if loc_res["primary_district"] else "LOW"),
                    is_india_valid=True if loc_res["primary_state"] else False,
                    raw_payload={
                        "title": title,
                        "description": desc[:400],
                        "link": link,
                        "feed": feed_config.name,
                        "publisher": feed_config.name,
                        "language": feed_config.language,
                        "state_coverage": feed_config.state_coverage,
                        "trust_score": feed_config.trust_score,
                        "published_at": observed_at.isoformat(),
                        "affected_districts": loc_res["affected_districts"],
                        "affected_states": loc_res["affected_states"],
                        "affected_district_count": loc_res["affected_district_count"],
                        "resolution_method": loc_res["resolution_method"],
                    },
                    idempotency_key=idem_key,
                    is_demo=False,
                )
            )
        except Exception as e:
            logger.debug("Error parsing feed item from '%s': %s", feed_config.name, e)
            continue

    return events


# ---------------------------------------------------------------------------
# Feed poller
# ---------------------------------------------------------------------------

async def poll_rss_feed(
    feed: RSSFeedConfig,
    source_id: str,
    client: httpx.AsyncClient,
    max_items: int = 20,
) -> Tuple[List[CanonicalRawEvent], str]:
    """
    Fetch and parse a single RSS feed.
    Returns (events, status_code) where status_code is one of:
      'ok', 'http_error', 'timeout', 'parse_error', 'disabled', 'empty'
    """
    if not feed.enabled:
        return [], "disabled"

    try:
        resp = await client.get(
            feed.url,
            timeout=feed.timeout_s,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            logger.info("Feed '%s' HTTP %d", feed.name, resp.status_code)
            return [], f"http_{resp.status_code}"

        events = parse_rss_feed(resp.text, feed, source_id, max_items=max_items)
        if not events:
            return [], "empty"
        return events, "ok"

    except httpx.TimeoutException:
        logger.debug("Timeout fetching feed '%s'", feed.name)
        return [], "timeout"
    except Exception as e:
        logger.debug("Error fetching feed '%s': %s", feed.name, e)
        return [], "error"


async def poll_all_rss_feeds(
    source_id: str,
    enabled_only: bool = True,
    max_items_per_feed: int = 15,
    max_concurrent: int = 8,
) -> Dict[str, Any]:
    """
    Concurrently poll all registered RSS feeds.
    Returns a summary dict with aggregated events and per-feed status.
    """
    import asyncio

    active_feeds = [f for f in RSS_FEEDS if (f.enabled or not enabled_only)]
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, text/xml, */*",
    }

    all_events: List[CanonicalRawEvent] = []
    feed_statuses: Dict[str, str] = {}
    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded_poll(feed: RSSFeedConfig) -> Tuple[str, List[CanonicalRawEvent], str]:
        async with semaphore:
            async with httpx.AsyncClient(headers=headers) as client:
                events, status = await poll_rss_feed(feed, source_id, client, max_items_per_feed)
            return feed.name, events, status

    tasks = [bounded_poll(f) for f in active_feeds]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            logger.debug("RSS task exception: %s", result)
            continue
        name, events, status = result
        feed_statuses[name] = status
        all_events.extend(events)

    ok_count = sum(1 for s in feed_statuses.values() if s == "ok")
    logger.info(
        "Regional RSS poll: %d feeds polled, %d OK, %d events collected",
        len(active_feeds), ok_count, len(all_events),
    )

    return {
        "events": all_events,
        "feed_statuses": feed_statuses,
        "feeds_polled": len(active_feeds),
        "feeds_ok": ok_count,
        "total_events": len(all_events),
    }
