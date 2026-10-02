"""Pydantic schemas for Social & Web Weather Intelligence Connector."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class SocialWebSourceDetail(BaseModel):
    provider_id: str
    name: str
    source_type: str
    status: str
    config: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class SocialWebConnectorOverviewResponse(BaseModel):
    connector_name: str
    connector_version: str
    status: str
    supported_source_types: List[str]
    default_weather_hashtags: List[str]
    default_weather_keywords: List[str]
    active_sources_count: int
    sources: List[SocialWebSourceDetail] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class SocialWebConnectorStatusResponse(BaseModel):
    connector_name: str
    status: str
    is_running: bool
    is_demo: bool
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
    reposts: int = 0
    rate_limits: int = 0
    errors: int = 0
    last_poll_at: Optional[datetime] = None
    last_successful_fetch: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    processing_latency_ms: float = 0.0
    sources_count: int = 0
    configured_hashtags: List[str] = Field(default_factory=list)
    sources_status: List[SocialWebSourceDetail] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class SocialWebTestSourceRequest(BaseModel):
    source_type: str = Field(description="One of SOCIAL_API, RSS_FEED, PUBLIC_WEB, PUBLIC_JSON")
    url: Optional[str] = None
    api_key: Optional[str] = None
    api_token: Optional[str] = None
    http_method: str = "GET"
    record_path: Optional[str] = "."
    field_mapping: Optional[Dict[str, str]] = None
    queries: Optional[List[str]] = None


class SocialWebTestSourceResponse(BaseModel):
    status: str  # HEALTHY, NOT_CONFIGURED, DEGRADED, ERROR
    source_type: str
    tested_url: Optional[str] = None
    success: bool
    records_found: int = 0
    records_fetched: int = 0
    weather_relevant: int = 0
    accepted_for_pipeline: int = 0
    accepted_india: int = 0
    rejected_non_weather: int = 0
    quarantined_foreign: int = 0
    quarantined_unknown_location: int = 0
    duplicates: int = 0
    reposts: int = 0
    rate_limits: int = 0
    errors: int = 0
    sample_records: List[Dict[str, Any]] = Field(default_factory=list)
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class SocialWebSourcesListResponse(BaseModel):
    total: int
    sources: List[SocialWebSourceDetail]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
