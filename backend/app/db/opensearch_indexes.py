"""OpenSearch Index Definitions and Management for SkyPulse Search & Filtering"""

from typing import Dict, Any
from opensearchpy import OpenSearch
from app.core.config import settings
import logging

logger = logging.getLogger("skypulse.opensearch")

WEATHER_REPORTS_INDEX = "weather_reports"

WEATHER_REPORTS_MAPPING: Dict[str, Any] = {
    "settings": {
        "index": {
            "number_of_shards": 2,
            "number_of_replicas": 0,
        }
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "canonical_event_id": {"type": "keyword"},
            "normalized_text": {"type": "text", "analyzer": "standard"},
            "primary_category": {"type": "keyword"},
            "sub_category": {"type": "keyword"},
            "severity": {"type": "integer"},
            "location_state": {"type": "keyword"},
            "location_district": {"type": "keyword"},
            "location_city": {"type": "keyword"},
            "location_point": {"type": "geo_point"},
            "event_time": {"type": "date"},
            "ingested_at": {"type": "date"},
            "verification_status": {"type": "keyword"},
            "confidence_score": {"type": "float"},
            "source_type": {"type": "keyword"},
            "is_demo": {"type": "boolean"},
            "status": {"type": "keyword"},
        }
    },
}


def get_opensearch_client() -> OpenSearch:
    """Return an OpenSearch client instance based on application settings."""
    return OpenSearch(
        hosts=[settings.OPENSEARCH_URL],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )


def initialize_opensearch_indexes(client: OpenSearch = None) -> bool:
    """Create or verify the weather_reports index in OpenSearch."""
    if client is None:
        client = get_opensearch_client()

    try:
        if not client.indices.exists(index=WEATHER_REPORTS_INDEX):
            logger.info("Creating OpenSearch index: %s", WEATHER_REPORTS_INDEX)
            client.indices.create(index=WEATHER_REPORTS_INDEX, body=WEATHER_REPORTS_MAPPING)
            logger.info("Successfully created OpenSearch index: %s", WEATHER_REPORTS_INDEX)
        else:
            logger.info("OpenSearch index '%s' already exists.", WEATHER_REPORTS_INDEX)
        return True
    except Exception as e:
        logger.warning("Could not initialize OpenSearch index (OpenSearch may be offline): %s", e)
        return False
