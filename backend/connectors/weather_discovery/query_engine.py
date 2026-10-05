"""
SkyPulse Regional Discovery Query Engine
=========================================
Generates LOCATION × WEATHER_EVENT × LANGUAGE search queries for use by:
  - Google News RSS discovery layer
  - DuckDuckGo / SearXNG search providers
  - RSS feed title filtering

Strategy
--------
1. For each (location, event) pair, select appropriate languages based on
   the state that location belongs to.
2. Combine location + keyword into clean search strings.
3. Deduplicate and rank by priority (cyclone/flood-prone districts get
   higher weight; official alert terms rank first).
4. Yield queries in batches to avoid rate-limit bursts.
"""

import hashlib
import random
from dataclasses import dataclass, field
from typing import Dict, Generator, List, Optional, Set, Tuple

from connectors.weather_discovery.india_locations import (
    CYCLONE_PRONE_DISTRICTS,
    FLOOD_PRONE_DISTRICTS,
    HIGH_PRIORITY_LOCATIONS,
    INDIA_DISTRICTS,
    INDIA_STATES,
    get_state_for_district,
)
from connectors.weather_discovery.multilingual_keywords import (
    KEYWORDS,
    LANGUAGE_STATE_COVERAGE,
    EventKey,
    LangCode,
    get_languages_for_state,
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DiscoveryQuery:
    """A single resolved search query ready for submission to a provider."""
    query: str
    location: str
    state: Optional[str]
    event_key: EventKey
    language: LangCode
    priority: int           # 1 (highest) … 5 (lowest)
    query_hash: str = field(init=False)

    def __post_init__(self):
        self.query_hash = hashlib.md5(self.query.lower().strip().encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Priority helpers
# ---------------------------------------------------------------------------

_HIGH_PRIORITY_EVENTS: Set[EventKey] = {"CYCLONE", "FLOOD", "CLOUDBURST", "LANDSLIDE"}
_MEDIUM_PRIORITY_EVENTS: Set[EventKey] = {"HEAVY_RAIN", "HEATWAVE", "THUNDERSTORM", "STRONG_WINDS"}

def _location_priority(location: str, state: Optional[str]) -> int:
    """Return priority integer for a location (1 = highest)."""
    loc = location.strip()
    if loc in CYCLONE_PRONE_DISTRICTS or loc in FLOOD_PRONE_DISTRICTS:
        return 1
    if loc in HIGH_PRIORITY_LOCATIONS:
        return 2
    if state and state in [
        "Maharashtra", "Kerala", "Odisha", "West Bengal",
        "Assam", "Bihar", "Gujarat", "Tamil Nadu",
    ]:
        return 3
    return 4


def _event_priority(event: EventKey) -> int:
    if event in _HIGH_PRIORITY_EVENTS:
        return 1
    if event in _MEDIUM_PRIORITY_EVENTS:
        return 2
    return 3


# ---------------------------------------------------------------------------
# Query generation
# ---------------------------------------------------------------------------

class QueryEngine:
    """
    Generates and manages the discovery query matrix for the regional engine.

    Usage::

        qe = QueryEngine()
        for batch in qe.iter_batches(batch_size=20):
            for query in batch:
                print(query.query, query.priority)
    """

    def __init__(
        self,
        locations: Optional[List[str]] = None,
        event_keys: Optional[List[EventKey]] = None,
        max_keywords_per_event_lang: int = 2,
        include_multilingual: bool = True,
        shuffle: bool = True,
        active_alert_states: Optional[List[str]] = None,
        active_alert_districts: Optional[List[str]] = None,
        active_alert_events: Optional[List[str]] = None,
    ):
        self.locations = locations or HIGH_PRIORITY_LOCATIONS
        self.event_keys = event_keys or list(KEYWORDS.keys())
        self.max_keywords_per_event_lang = max_keywords_per_event_lang
        self.include_multilingual = include_multilingual
        self.shuffle = shuffle
        self.active_alert_states: Set[str] = set(active_alert_states or [])
        self.active_alert_districts: Set[str] = set(active_alert_districts or [])
        self.active_alert_events: Set[str] = set(active_alert_events or [])
        self._seen_hashes: Set[str] = set()

    def set_active_alerts(
        self,
        states: Optional[List[str]] = None,
        districts: Optional[List[str]] = None,
        events: Optional[List[str]] = None,
    ) -> None:
        """Dynamically configure active severe weather alerts to prioritize affected regions."""
        if states is not None:
            self.active_alert_states = set(states)
        if districts is not None:
            self.active_alert_districts = set(districts)
        if events is not None:
            self.active_alert_events = set(events)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> List[DiscoveryQuery]:
        """Generate the full deduplicated query list with priority ranking."""
        queries: List[DiscoveryQuery] = []
        for location in self.locations:
            state = get_state_for_district(location)
            if not state:
                # Try state names
                for sk, sv in INDIA_STATES.items():
                    if sv["name"] == location:
                        state = sv["name"]
                        break
            loc_priority = _location_priority(location, state)
            langs = get_languages_for_state(state) if (state and self.include_multilingual) else ["en"]

            for event_key in self.event_keys:
                ev_priority = _event_priority(event_key)
                combined_priority = min(loc_priority + ev_priority - 1, 5)

                # Dynamic priority boost for active severe weather & official alerts
                is_active_loc = (state and state in self.active_alert_states) or (location in self.active_alert_districts)
                is_active_ev = (event_key in self.active_alert_events) or (event_key in _HIGH_PRIORITY_EVENTS)
                if is_active_loc and is_active_ev:
                    combined_priority = 1
                elif is_active_loc:
                    combined_priority = max(1, combined_priority - 2)

                event_kws = KEYWORDS.get(event_key, {})
                for lang in langs:
                    kws = event_kws.get(lang, [])
                    for kw in kws[: self.max_keywords_per_event_lang]:
                        q_str = f"{location} {state} {kw}" if (state and state != location and lang == "en") else f"{location} {kw}"
                        dq = DiscoveryQuery(
                            query=q_str,
                            location=location,
                            state=state,
                            event_key=event_key,
                            language=lang,
                            priority=combined_priority,
                        )
                        if dq.query_hash not in self._seen_hashes:
                            self._seen_hashes.add(dq.query_hash)
                            queries.append(dq)

        if self.shuffle:
            random.shuffle(queries)
        # Active alerts lead rotation batches first, followed by priority ranking (1 to 5)
        def _sort_key(q: DiscoveryQuery):
            is_active_loc = (q.state and q.state in self.active_alert_states) or (q.location in self.active_alert_districts)
            is_active_ev = (q.event_key in self.active_alert_events) or (not self.active_alert_events and q.event_key in _HIGH_PRIORITY_EVENTS)
            alert_rank = 0 if (is_active_loc and is_active_ev) else (1 if is_active_loc else 2)
            return (alert_rank, q.priority)

        queries.sort(key=_sort_key)
        return queries

    def iter_batches(self, batch_size: int = 20) -> Generator[List[DiscoveryQuery], None, None]:
        """Yield queries in priority-ordered batches of `batch_size`."""
        all_queries = self.generate()
        for i in range(0, len(all_queries), batch_size):
            yield all_queries[i : i + batch_size]

    def total_query_count(self) -> int:
        """Return total number of unique queries that would be generated."""
        saved = set(self._seen_hashes)
        self._seen_hashes.clear()
        count = len(self.generate())
        self._seen_hashes = saved
        return count

    # ------------------------------------------------------------------
    # Specialised helpers
    # ------------------------------------------------------------------

    @staticmethod
    def gnews_rss_url(query: str) -> str:
        """
        Build a Google News RSS URL for a query string.
        Google News RSS: https://news.google.com/rss/search?q=QUERY&hl=en-IN&gl=IN&ceid=IN:en
        """
        import urllib.parse
        encoded = urllib.parse.quote_plus(query)
        return (
            f"https://news.google.com/rss/search"
            f"?q={encoded}"
            f"&hl=en-IN&gl=IN&ceid=IN%3Aen"
        )

    @staticmethod
    def gnews_rss_url_hindi(query: str) -> str:
        """Google News RSS URL for Hindi-language results."""
        import urllib.parse
        encoded = urllib.parse.quote_plus(query)
        return (
            f"https://news.google.com/rss/search"
            f"?q={encoded}"
            f"&hl=hi&gl=IN&ceid=IN%3Ahi"
        )

    @staticmethod
    def high_priority_gnews_urls(max_queries: int = 50) -> List[Tuple[str, DiscoveryQuery]]:
        """
        Return a list of (gnews_rss_url, DiscoveryQuery) tuples
        for the top N highest-priority English queries.
        Suitable for the frequent polling cycle.
        """
        qe = QueryEngine(
            include_multilingual=False,  # English only for GNews
            max_keywords_per_event_lang=1,
            shuffle=False,
        )
        queries = qe.generate()
        result: List[Tuple[str, DiscoveryQuery]] = []
        for dq in queries[:max_queries]:
            url = QueryEngine.gnews_rss_url(dq.query)
            result.append((url, dq))
        return result


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_engine: Optional[QueryEngine] = None


def get_query_engine(refresh: bool = False) -> QueryEngine:
    """Return the shared singleton QueryEngine instance."""
    global _default_engine
    if _default_engine is None or refresh:
        _default_engine = QueryEngine()
    return _default_engine
