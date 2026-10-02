"""
SkyPulse OpenSearch Indexer
Asynchronously indexes classified, normalized weather reports and events into OpenSearch.
Provides fallback in-memory index storage if OpenSearch cluster is unreachable.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

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

    def _ensure_connection(self):
        if not self._checked_connection:
            self._checked_connection = True
            try:
                self._client = get_opensearch_client()
                self._is_live = bool(self._client.ping(request_timeout=0.2))
            except Exception:
                self._is_live = False
                self._client = None

    @property
    def is_live(self) -> bool:
        self._ensure_connection()
        return self._is_live

    async def index_report(self, report_doc: Dict[str, Any]) -> bool:
        """Index a processed report document."""
        report_id = str(report_doc.get("id"))
        # Cache locally in fallback index
        self._in_memory_index[report_id] = report_doc

        self._ensure_connection()
        if self._is_live and self._client:
            try:
                # OpenSearch geo_point format: {"lat": float, "lon": float}
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
                return True
            except Exception as e:
                self._is_live = False
                logger.debug("OpenSearch indexing offline (%s). Saved to in-memory index.", e)
                return True

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
                return [h["_source"] for h in hits]
            except Exception as e:
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

        return results


# Global OpenSearch Indexer instance
opensearch_indexer = OpenSearchIndexer()
