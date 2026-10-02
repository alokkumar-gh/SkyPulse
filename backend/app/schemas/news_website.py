"""Pydantic schemas for News Website Ingestion Connector."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class NewsSourceDetailResponse(BaseModel):
    source_id: str
    publisher_name: str
    domains: List[str]
    feed_urls: List[str] = Field(default_factory=list)
    article_category_urls: List[str] = Field(default_factory=list)
    source_type: str
    enabled: bool
    polling_interval_seconds: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class NewsWebsiteStatusResponse(BaseModel):
    connector_name: str
    status: str
    is_running: bool
    is_demo: bool
    sources_configured: int = 0
    sources_healthy: int = 0
    sources_failed: int = 0
    feeds_polled: int = 0
    articles_discovered: int = 0
    weather_relevant: int = 0
    accepted_for_pipeline: int = 0
    accepted_india: int = 0
    rejected_non_weather: int = 0
    quarantined_foreign: int = 0
    quarantined_unknown_location: int = 0
    duplicates: int = 0
    parsing_errors: int = 0
    rate_limit_responses: int = 0
    last_successful_fetch: Optional[datetime] = None
    last_poll_at: Optional[datetime] = None
    processing_latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class NewsWebsiteSourcesListResponse(BaseModel):
    total: int
    sources: List[NewsSourceDetailResponse] = Field(default_factory=list)


class NewsWebsiteTestSourceRequest(BaseModel):
    feed_url: str
    publisher_name: Optional[str] = "Test Publisher"


class NewsWebsiteTestSourceResponse(BaseModel):
    status: str
    feed_url: str
    publisher_name: str
    success: bool
    articles_found: int = 0
    weather_relevant: int = 0
    accepted_india: int = 0
    quarantined: int = 0
    sample_articles: List[Dict[str, Any]] = Field(default_factory=list)
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
