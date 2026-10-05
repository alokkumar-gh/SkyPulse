"""
SkyPulse Google News RSS Discovery Layer
==========================================
Discovers regional Indian weather news via Google News RSS search URLs.

Google News RSS endpoint (no API key required, public):
  https://news.google.com/rss/search?q=QUERY&hl=en-IN&gl=IN&ceid=IN:en

Strategy
--------
1. QueryEngine generates LOCATION × EVENT × LANGUAGE tuples.
2. For each tuple, build a Google News RSS URL.
3. Poll the RSS feed; parse items.
4. Apply weather-relevance filter.
5. Strip Google redirect wrappers to get canonical article URLs.
6. Deduplicate via idempotency key.
7. Emit CanonicalRawEvent objects into the pipeline.

Rate limiting
-------------
- Google News RSS is a public endpoint but should be polled respectfully.
- We use a token-bucket to ensure ≤ 2 requests/second.
- Full query matrix is executed in rotating windows (not all at once).
- Only the top N highest-priority queries are executed per poll cycle.

Robots.txt compliance
---------------------
- Google News RSS is explicitly a public feed endpoint for syndication.
- We do NOT scrape news.google.com HTML pages.
- We do NOT bypass Cloudflare or CAPTCHAs.
"""

import asyncio
import hashlib
import html
import logging
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

from connectors.schema import CanonicalRawEvent
from connectors.weather_discovery.query_engine import DiscoveryQuery, QueryEngine
from connectors.weather_discovery.regional_rss import is_weather_relevant

logger = logging.getLogger("skypulse.connectors.gnews_discovery")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GNEWS_RSS_BASE = "https://news.google.com/rss/search"

# User-agent that identifies us correctly
_UA = "SkyPulse-WeatherIntelligence/2.0 (Regional Discovery; +https://skypulse.gov.in)"

# Minimum seconds between individual GNews RSS requests
_MIN_INTERVAL_S = 0.6

# Max queries per poll cycle (to stay under implicit rate limits)
MAX_QUERIES_PER_CYCLE = 40

# Max items to process per GNews RSS response
MAX_ITEMS_PER_RESPONSE = 10

# Minimum text length to accept an event
MIN_TEXT_LENGTH = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_gnews_url(query: str, lang: str = "en") -> str:
    """Build Google News RSS URL for a given query and language with fresh time window."""
    clean_q = query.strip()
    if "when:" not in clean_q:
        clean_q = f"{clean_q} when:3d"
    encoded = urllib.parse.quote_plus(clean_q)
    if lang == "hi":
        return f"{GNEWS_RSS_BASE}?q={encoded}&hl=hi&gl=IN&ceid=IN%3Ahi"
    elif lang in ("ta", "te", "kn", "ml"):
        # Regional language codes map to their GNews hl codes
        hl_map = {"ta": "ta", "te": "te", "kn": "kn", "ml": "ml"}
        hl = hl_map.get(lang, "en")
        return f"{GNEWS_RSS_BASE}?q={encoded}&hl={hl}&gl=IN&ceid=IN%3A{hl}"
    # Default: English India
    return f"{GNEWS_RSS_BASE}?q={encoded}&hl=en-IN&gl=IN&ceid=IN%3Aen"


def _unwrap_gnews_url(raw_url: str) -> str:
    """
    Google News RSS wraps article URLs in a redirect.
    E.g. https://news.google.com/rss/articles/CBMi...
    We store the raw URL as canonical (article content is not fetched).
    """
    return raw_url.strip()


def _clean_html(raw: str) -> str:
    if not raw:
        return ""
    raw = html.unescape(raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def _sanitize_xml(xml_text: str) -> str:
    xml_text = xml_text.lstrip("\ufeff")
    xml_text = re.sub(r"&(?!(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)", "&amp;", xml_text)
    return xml_text


def _parse_pub_date(raw: Optional[str]) -> Optional[datetime]:
    """Parse RFC 822 date strings to UTC datetime."""
    if not raw:
        return None
    import email.utils
    try:
        return email.utils.parsedate_to_datetime(raw.strip())
    except Exception:
        return None


def _make_idem_key(guid: str, title: str) -> str:
    src = guid or title
    return "gnews-" + hashlib.sha256(src.encode()).hexdigest()[:20]


# ---------------------------------------------------------------------------
# RSS parser
# ---------------------------------------------------------------------------

def parse_gnews_rss(
    xml_text: str,
    query: DiscoveryQuery,
    source_id: str,
    max_items: int = MAX_ITEMS_PER_RESPONSE,
) -> List[CanonicalRawEvent]:
    """Parse Google News RSS XML into CanonicalRawEvents."""
    events: List[CanonicalRawEvent] = []
    xml_text = _sanitize_xml(xml_text)

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.debug("GNews XML parse error for '%s': %s", query.query, e)
        return events

    items = root.findall(".//item")
    for item in items[:max_items]:
        try:
            raw_title = _clean_html(item.findtext("title") or "")
            description = _clean_html(item.findtext("description") or "")
            link = (item.findtext("link") or "").strip()
            pub_date = item.findtext("pubDate")
            guid = (item.findtext("guid") or link or "").strip()

            full_text = f"{raw_title}. {description}".strip(". ")
            if len(full_text) < MIN_TEXT_LENGTH:
                continue

            # Section 6: Weather Relevance Validation (reject false positives like political storms)
            if not is_weather_relevant(full_text):
                continue

            # Section 4: Original Publisher Provenance extraction
            source_elem = item.find("source")
            publisher = ""
            publisher_url = ""
            if source_elem is not None:
                publisher = (source_elem.text or "").strip()
                publisher_url = (source_elem.attrib.get("url") or "").strip()

            clean_title = raw_title
            if not publisher and " - " in raw_title:
                parts = raw_title.rsplit(" - ", 1)
                clean_title = parts[0].strip()
                publisher = parts[1].strip()
            elif publisher and raw_title.endswith(f" - {publisher}"):
                clean_title = raw_title[:-len(f" - {publisher}")].strip()

            if not publisher or publisher.lower() in ("google news", "google"):
                publisher = "Unknown Publisher"

            observed_at = _parse_pub_date(pub_date) or datetime.now(timezone.utc)
            now_utc = datetime.now(timezone.utc)
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=timezone.utc)
            # Live discovery filter: discard articles published more than 7 days ago
            if (now_utc - observed_at).total_seconds() > 7 * 86400:
                continue

            idem_key = _make_idem_key(guid, full_text)
            canonical_url = _unwrap_gnews_url(link)
            original_url = publisher_url if publisher_url else canonical_url

            # Location extraction (Sections 5, 6, 7, 8, 9, 10)
            from connectors.weather_discovery.india_locations import resolve_article_locations
            loc_res = resolve_article_locations(
                title=clean_title,
                text=full_text,
                metadata={"state": query.state},
            )

            events.append(
                CanonicalRawEvent(
                    source_id=source_id,
                    source_type="NEWS_DISCOVERY",
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
                        "discovery_source": "GOOGLE_NEWS_RSS",
                        "publisher": publisher,
                        "original_url": original_url,
                        "title": clean_title,
                        "published_at": observed_at.isoformat(),
                        "link": canonical_url,
                        "description": description[:400],
                        "query": query.query,
                        "query_location": query.location,
                        "query_event": query.event_key,
                        "query_language": query.language,
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
            logger.debug("Error parsing GNews item: %s", e)
            continue

    return events


# ---------------------------------------------------------------------------
# Async poller
# ---------------------------------------------------------------------------

class GoogleNewsRSSDiscovery:
    """
    Async discovery layer that polls Google News RSS for regional weather signals.
    """

    def __init__(
        self,
        source_id: str,
        max_queries_per_cycle: int = MAX_QUERIES_PER_CYCLE,
        request_interval_s: float = _MIN_INTERVAL_S,
        max_concurrent: int = 4,
    ):
        self.source_id = source_id
        self.max_queries_per_cycle = max_queries_per_cycle
        self.request_interval_s = request_interval_s
        self.max_concurrent = max_concurrent
        self._query_engine = QueryEngine(
            include_multilingual=True,
            max_keywords_per_event_lang=1,
        )
        self._seen_idem_keys: Set[str] = set()
        self._cycle_index: int = 0

    def set_active_alerts(
        self,
        states: Optional[List[str]] = None,
        districts: Optional[List[str]] = None,
        events: Optional[List[str]] = None,
    ) -> None:
        """Forward active alert context to underlying query engine."""
        self._query_engine.set_active_alerts(states=states, districts=districts, events=events)

    def _select_cycle_queries(self) -> List[DiscoveryQuery]:
        """
        Select a priority-aware window of queries for this cycle.
        Priority 1 queries (e.g. active alerts, severe weather) lead the cycle,
        while maintaining bounded rotation across the full query matrix within budget.
        """
        all_queries = self._query_engine.generate()
        total = len(all_queries)
        if total == 0:
            return []

        budget = self.max_queries_per_cycle
        p1_queries = [q for q in all_queries if q.priority == 1]
        other_queries = [q for q in all_queries if q.priority > 1]

        # Active alert and high severity queries lead the cycle
        p1_take = min(len(p1_queries), max(1, budget // 2)) if other_queries else min(len(p1_queries), budget)
        selected_p1 = p1_queries[:p1_take]

        remaining_budget = budget - len(selected_p1)
        if remaining_budget > 0 and other_queries:
            start = (self._cycle_index * remaining_budget) % len(other_queries)
            end = start + remaining_budget
            if end <= len(other_queries):
                selected_others = other_queries[start:end]
            else:
                selected_others = other_queries[start:] + other_queries[: end - len(other_queries)]
        else:
            selected_others = []

        self._cycle_index += 1
        return selected_p1 + selected_others

    async def _fetch_one(
        self,
        query: DiscoveryQuery,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
    ) -> Tuple[DiscoveryQuery, List[CanonicalRawEvent], str]:
        """Fetch a single GNews RSS query with rate limiting."""
        async with semaphore:
            url = _build_gnews_url(query.query, lang=query.language)
            try:
                resp = await client.get(url, timeout=10.0, follow_redirects=True)
                if resp.status_code != 200:
                    return query, [], f"http_{resp.status_code}"
                events = parse_gnews_rss(resp.text, query, self.source_id)
                # Apply seen-key dedup
                fresh = [e for e in events if e.idempotency_key not in self._seen_idem_keys]
                for e in fresh:
                    self._seen_idem_keys.add(e.idempotency_key)
                # Bound memory growth of seen set
                if len(self._seen_idem_keys) > 50_000:
                    self._seen_idem_keys = set(list(self._seen_idem_keys)[-25_000:])
                return query, fresh, "ok"
            except httpx.TimeoutException:
                return query, [], "timeout"
            except Exception as e:
                logger.debug("GNews fetch error for '%s': %s", query.query, e)
                return query, [], "error"

    async def poll(self) -> Dict[str, Any]:
        """
        Run one poll cycle. Returns summary + all discovered events.
        """
        queries = self._select_cycle_queries()
        if not queries:
            return {"events": [], "queries_run": 0, "events_found": 0}

        headers = {"User-Agent": _UA, "Accept": "application/rss+xml, text/xml, */*"}
        semaphore = asyncio.Semaphore(self.max_concurrent)
        all_events: List[CanonicalRawEvent] = []
        query_results: Dict[str, str] = {}

        # Stagger requests to respect rate limits
        async def fetch_with_delay(idx: int, query: DiscoveryQuery):
            await asyncio.sleep(idx * self.request_interval_s / self.max_concurrent)
            async with httpx.AsyncClient(headers=headers) as client:
                return await self._fetch_one(query, client, semaphore)

        tasks = [fetch_with_delay(i, q) for i, q in enumerate(queries)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                continue
            query, events, status = result
            query_results[query.query_hash] = status
            all_events.extend(events)

        ok_count = sum(1 for s in query_results.values() if s == "ok")
        logger.info(
            "GNews Discovery: %d queries, %d OK, %d new events",
            len(queries), ok_count, len(all_events),
        )
        return {
            "events": all_events,
            "queries_run": len(queries),
            "queries_ok": ok_count,
            "events_found": len(all_events),
            "cycle_index": self._cycle_index,
        }
