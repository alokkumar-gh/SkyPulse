"""
SkyPulse OpenSearch Indexer
Asynchronously indexes classified, normalized weather reports and events into OpenSearch.
Provides fallback in-memory index storage if OpenSearch cluster is unreachable.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.core.config import settings
from app.db.opensearch_indexes import WEATHER_REPORTS_INDEX, get_opensearch_client

logger = logging.getLogger("skypulse.opensearch_indexer")


class OpenSearchIndexer:
    """
    Manages indexing and querying of weather intelligence in OpenSearch.
    Maintains an in-memory document store as a graceful fallback when OpenSearch is offline.
    """

    def __init__(self):
        self._client = None
        self._checked_connection = False
        self._is_live = False
        self._in_memory_index: Dict[str, Dict[str, Any]] = {}
        self.metrics = {
            "documents_indexed_total": 0,
            "indexing_errors_total": 0,
            "search_queries_total": 0,
            "fallback_activations_total": 0,
            "last_index_latency_ms": 0.0,
            "last_search_latency_ms": 0.0,
        }

    def _ensure_connection(self):
        if not settings.OPENSEARCH_ENABLED:
            self._is_live = False
            return

        now = time.time()
        if self._checked_connection and not self._is_live and (now - getattr(self, "_last_check_time", 0.0)) < 60.0:
            return

        self._checked_connection = True
        self._last_check_time = now
        try:
            self._client = get_opensearch_client()
            self._is_live = bool(self._client.ping(request_timeout=0.5))
        except Exception as e:
            self._is_live = False
            self._client = None
            logger.debug("OpenSearch connection check failed: %s", e)

    @property
    def is_live(self) -> bool:
        self._ensure_connection()
        return self._is_live

    @property
    def status(self) -> str:
        if not settings.OPENSEARCH_ENABLED:
            return "DISABLED"
        return "ONLINE" if self.is_live else "FALLBACK"

    def get_health_status(self) -> Dict[str, Any]:
        """Return operational health telemetry for OpenSearch."""
        self._ensure_connection()
        cluster_health = "UNKNOWN"
        cluster_name = None
        if self._is_live and self._client:
            try:
                info = self._client.cluster.health(request_timeout=2.0)
                cluster_health = info.get("status", "ONLINE").upper()
                cluster_name = info.get("cluster_name")
            except Exception:
                cluster_health = "DEGRADED"

        return {
            "status": self.status,
            "is_live": self._is_live,
            "cluster_status": cluster_health,
            "cluster_name": cluster_name,
            "index_name": WEATHER_REPORTS_INDEX,
            "in_memory_documents": len(self._in_memory_index),
            "metrics": dict(self.metrics),
        }

    async def index_report(self, report_doc: Dict[str, Any]) -> bool:
        """Index a processed report document idempotently using deterministic ID."""
        t0 = time.perf_counter()
        report_id = str(report_doc.get("id"))
        # Cache locally in fallback index
        self._in_memory_index[report_id] = report_doc

        self._ensure_connection()
        if self._is_live and self._client:
            try:
                doc = dict(report_doc)
                lat = doc.get("location_lat")
                lon = doc.get("location_lon")
                if lat is not None and lon is not None:
                    doc["location_point"] = {"lat": float(lat), "lon": float(lon)}

                # Remove non-serializable fields
                doc.pop("location_lat", None)
                doc.pop("location_lon", None)

                self._client.index(
                    index=WEATHER_REPORTS_INDEX,
                    id=report_id,
                    body=doc,
                    refresh=True,
                )
                self._is_live = True
                self.metrics["documents_indexed_total"] += 1
                self.metrics["last_index_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
                return True
            except Exception as e:
                self._is_live = False
                self.metrics["indexing_errors_total"] += 1
                self.metrics["fallback_activations_total"] += 1
                logger.debug("OpenSearch indexing error (%s). Saved to in-memory fallback.", e)
                return True

        self.metrics["fallback_activations_total"] += 1
        return True

    async def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific report by ID from OpenSearch or in-memory fallback."""
        self._ensure_connection()
        if self._is_live and self._client:
            try:
                res = self._client.get(index=WEATHER_REPORTS_INDEX, id=str(report_id))
                return res.get("_source")
            except Exception as e:
                logger.debug("OpenSearch get error: %s", e)

        return self._in_memory_index.get(str(report_id))

    async def delete_report(self, report_id: str) -> bool:
        """Delete a report by ID from OpenSearch and in-memory store."""
        self._in_memory_index.pop(str(report_id), None)
        self._ensure_connection()
        if self._is_live and self._client:
            try:
                self._client.delete(index=WEATHER_REPORTS_INDEX, id=str(report_id), refresh=True)
                return True
            except Exception as e:
                logger.debug("OpenSearch delete error: %s", e)
                return False
        return True

    async def search_reports(
        self,
        category: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        verification_status: Optional[str] = None,
        min_confidence: Optional[float] = None,
        query_text: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search reports across OpenSearch or fallback to in-memory search."""
        t0 = time.perf_counter()
        self.metrics["search_queries_total"] += 1
        self._ensure_connection()
        if self._is_live and self._client:
            try:
                must_clauses = []
                if category:
                    must_clauses.append({"term": {"primary_category": category.upper()}})
                if city:
                    must_clauses.append({"match": {"location_city": city}})
                if state:
                    must_clauses.append({"match": {"location_state": state}})
                if verification_status:
                    must_clauses.append({"term": {"verification_status": verification_status.upper()}})
                if min_confidence is not None:
                    must_clauses.append({"range": {"confidence_score": {"gte": min_confidence}}})
                if query_text:
                    must_clauses.append({"match": {"normalized_text": query_text}})

                query = {"query": {"bool": {"must": must_clauses}}} if must_clauses else {"query": {"match_all": {}}}
                res = self._client.search(index=WEATHER_REPORTS_INDEX, body=query, size=limit)
                hits = res.get("hits", {}).get("hits", [])
                self.metrics["last_search_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
                return [h["_source"] for h in hits]
            except Exception as e:
                self.metrics["fallback_activations_total"] += 1
                logger.warning("OpenSearch search error (%s). Falling back to in-memory store.", e)

        # Fallback in-memory search
        results = []
        for doc in self._in_memory_index.values():
            if category and (doc.get("primary_category") or "").upper() != category.upper():
                continue
            if city and city.lower() not in (doc.get("location_city") or "").lower():
                continue
            if state and state.lower() not in (doc.get("location_state") or "").lower():
                continue
            if verification_status and (doc.get("verification_status") or "").upper() != verification_status.upper():
                continue
            if min_confidence is not None and (doc.get("confidence_score") or 0.0) < min_confidence:
                continue
            if query_text and query_text.lower() not in (doc.get("normalized_text") or "").lower():
                continue

            results.append(doc)
            if len(results) >= limit:
                break

        self.metrics["last_search_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return results


# Global OpenSearch Indexer instance
opensearch_indexer = OpenSearchIndexer()
