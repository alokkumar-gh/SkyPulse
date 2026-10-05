"""
SkyPulse Regional Weather Intelligence Discovery Connector
==========================================================
Main connector that orchestrates all regional discovery sub-layers:

  Layer 1: Regional RSS feeds (30+ Indian news + official alert feeds)
  Layer 2: Google News RSS discovery (LOCATION × EVENT × LANGUAGE queries)

Each poll cycle:
  1. Runs RSS layer → collects CanonicalRawEvents
  2. Runs GNews layer → collects CanonicalRawEvents
  3. Deduplicates via idempotency_service
  4. Returns all unique weather signals to the orchestrator pipeline

The orchestrator sends events through:
  CanonicalRawEvent → Normalizer → India Validation → Kafka → AI/NLP →
  WeatherEvent → DWEG → OpenSearch → WebSocket

Admin Telemetry
---------------
  - Per-cycle feed health (ok/timeout/error per feed)
  - Per-cycle GNews query stats (queries run / ok / events found)
  - Cumulative connector metrics (via BaseConnector)
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector
from connectors.idempotency import idempotency_service
from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum
from connectors.weather_discovery.gnews_discovery import GoogleNewsRSSDiscovery
from connectors.weather_discovery.regional_rss import RSS_FEEDS, poll_all_rss_feeds

logger = logging.getLogger("skypulse.connectors.regional_discovery")

CONNECTOR_NAME = "Regional Weather Intelligence Discovery Engine"
CONNECTOR_VERSION = "1.0.0"
DEFAULT_SOURCE_ID = "00000000-0000-0000-0000-000000000010"


class RegionalDiscoveryConnector(BaseConnector):
    """
    Unified connector for regional Indian weather signal discovery.

    Combines:
      - 30+ RSS/Atom feeds (national + regional + vernacular + official)
      - Google News RSS discovery (LOCATION × EVENT × LANGUAGE query matrix)

    All discovered events flow into the standard CanonicalRawEvent pipeline.
    """

    def __init__(
        self,
        source_id: str = DEFAULT_SOURCE_ID,
        name: str = CONNECTOR_NAME,
        max_gnews_queries_per_cycle: int = 30,
        enable_gnews: bool = True,
        enable_rss: bool = True,
    ):
        super().__init__(
            source_id=source_id,
            name=name,
            source_type="NEWS_PUBLISHER",
            config={
                "max_gnews_queries_per_cycle": max_gnews_queries_per_cycle,
                "enable_gnews": enable_gnews,
                "enable_rss": enable_rss,
                "rss_feeds_count": len(RSS_FEEDS),
            },
            is_demo=False,
        )
        self.enable_gnews = enable_gnews
        self.enable_rss = enable_rss

        self._gnews = GoogleNewsRSSDiscovery(
            source_id=source_id,
            max_queries_per_cycle=max_gnews_queries_per_cycle,
        )

        # Extended telemetry
        self._last_rss_summary: Dict[str, Any] = {}
        self._last_gnews_summary: Dict[str, Any] = {}
        self._total_events_discovered: int = 0
        self._total_events_accepted: int = 0
        self._total_rss_cycles: int = 0
        self._total_gnews_cycles: int = 0

    # ------------------------------------------------------------------
    # BaseConnector implementation
    # ------------------------------------------------------------------

    async def poll(self) -> List[CanonicalRawEvent]:
        """
        Execute one discovery cycle across all layers.
        Returns deduplicated CanonicalRawEvent list.
        """
        t0 = time.time()
        self.last_attempt_at = datetime.now(timezone.utc)
        self.metrics.last_poll_at = self.last_attempt_at

        all_events: List[CanonicalRawEvent] = []

        # ── Layer 1: Regional RSS ──────────────────────────────────────
        if self.enable_rss:
            try:
                rss_result = await poll_all_rss_feeds(
                    source_id=self.source_id,
                    max_items_per_feed=12,
                    max_concurrent=8,
                )
                self._last_rss_summary = {
                    k: v for k, v in rss_result.items() if k != "events"
                }
                self._total_rss_cycles += 1
                rss_events = rss_result.get("events", [])
                all_events.extend(rss_events)
                logger.info(
                    "RSS layer: %d feeds OK, %d events",
                    rss_result.get("feeds_ok", 0),
                    len(rss_events),
                )
            except Exception as e:
                logger.warning("RSS layer error: %s", e)
                self._last_rss_summary = {"error": str(e)}

        # ── Layer 2: Google News RSS ───────────────────────────────────
        if self.enable_gnews:
            try:
                gnews_result = await self._gnews.poll()
                self._last_gnews_summary = {
                    k: v for k, v in gnews_result.items() if k != "events"
                }
                self._total_gnews_cycles += 1
                gnews_events = gnews_result.get("events", [])
                all_events.extend(gnews_events)
                logger.info(
                    "GNews layer: %d queries, %d events",
                    gnews_result.get("queries_run", 0),
                    len(gnews_events),
                )
            except Exception as e:
                logger.warning("GNews layer error: %s", e)
                self._last_gnews_summary = {"error": str(e)}

        # ── Idempotency dedup ──────────────────────────────────────────
        accepted: List[CanonicalRawEvent] = []
        for event in all_events:
            try:
                ikey = event.idempotency_key or event.external_id or event.text[:80]
                if not idempotency_service.is_duplicate(ikey):
                    idempotency_service.mark_seen(ikey)
                    accepted.append(event)
                else:
                    self.metrics.duplicates += 1
            except Exception:
                accepted.append(event)  # fallback: include if dedup check fails

        elapsed_ms = (time.time() - t0) * 1000
        self._total_events_discovered += len(all_events)
        self._total_events_accepted += len(accepted)

        if accepted:
            self.record_success(len(accepted), elapsed_ms)
            self.is_reachable = True
            self.status = ConnectorStatusEnum.LIVE
        else:
            # No events is not necessarily a failure – could be quiet period
            self.metrics.last_poll_at = datetime.now(timezone.utc)
            self.metrics.processing_latency_ms = elapsed_ms
            if self.status != ConnectorStatusEnum.LIVE:
                self.status = ConnectorStatusEnum.HEALTHY

        logger.info(
            "Regional Discovery poll: %d discovered → %d accepted (%.0f ms)",
            len(all_events), len(accepted), elapsed_ms,
        )
        return accepted

    def parse(self, raw_data: Any) -> Optional[CanonicalRawEvent]:
        """Not used directly; parsing is delegated to sub-layers."""
        return None

    # ------------------------------------------------------------------
    # Telemetry / admin
    # ------------------------------------------------------------------

    def get_discovery_status(self) -> Dict[str, Any]:
        """Return extended discovery engine status for the admin dashboard."""
        from connectors.weather_discovery.regional_rss import RSS_FEEDS
        return {
            "connector": CONNECTOR_NAME,
            "version": CONNECTOR_VERSION,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "layers": {
                "rss": {
                    "enabled": self.enable_rss,
                    "feeds_registered": len(RSS_FEEDS),
                    "cycles_run": self._total_rss_cycles,
                    "last_summary": self._last_rss_summary,
                },
                "gnews": {
                    "enabled": self.enable_gnews,
                    "cycles_run": self._total_gnews_cycles,
                    "last_summary": self._last_gnews_summary,
                },
            },
            "totals": {
                "events_discovered": self._total_events_discovered,
                "events_accepted": self._total_events_accepted,
                "duplicates_dropped": self.metrics.duplicates,
            },
            "last_attempt_at": (
                self.last_attempt_at.isoformat() if self.last_attempt_at else None
            ),
            "last_success_at": (
                self.metrics.last_successful_fetch.isoformat()
                if self.metrics.last_successful_fetch else None
            ),
        }


# ---------------------------------------------------------------------------
# Module-level singleton (used by orchestrator)
# ---------------------------------------------------------------------------

regional_discovery_connector = RegionalDiscoveryConnector(
    source_id=DEFAULT_SOURCE_ID,
    name=CONNECTOR_NAME,
    max_gnews_queries_per_cycle=30,
    enable_gnews=True,
    enable_rss=True,
)
