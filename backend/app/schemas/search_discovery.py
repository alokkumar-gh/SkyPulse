"""Pydantic schemas for Search Discovery Weather Ingestion Connector (Phase 1)."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class SearchDiscoveryStatusResponse(BaseModel):
    connector_name: str
    status: str
    is_running: bool
    is_demo: bool
    provider_name: str
    records_fetched: int = 0
    records_accepted: int = 0
    records_rejected: int = 0
    weather_relevant: int = 0
    accepted_for_pipeline: int = 0
    accepted_india: int = 0
    rejected_non_weather: int = 0
    quarantined_foreign: int = 0
    quarantined_unknown_location: int = 0
    duplicates: int = 0
    errors: int = 0
    last_poll_at: Optional[datetime] = None
    last_successful_fetch: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    processing_latency_ms: float = 0.0
    active_queries_count: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class SearchDiscoveryQueriesResponse(BaseModel):
    total_queries: int
    hashtags: List[str]
    locations: List[str]
    categories: List[str]
    custom_queries: List[str]
    generated_sample_queries: List[str]


class SearchDiscoveryTestSourceRequest(BaseModel):
    query: str
    max_results: int = 5
    provider_type: Optional[str] = None  # duckduckgo, searxng, custom


class SearchDiscoveryTestSourceResponse(BaseModel):
    status: str
    query: str
    provider: str
    success: bool
    records_found: int = 0
    weather_relevant: int = 0
    accepted_india: int = 0
    quarantined: int = 0
    sample_records: List[Dict[str, Any]] = Field(default_factory=list)
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
