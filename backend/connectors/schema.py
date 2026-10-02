import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ConnectorStatusEnum(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    ERROR = "ERROR"
    DISABLED = "DISABLED"
    DEMO = "DEMO"


class ConnectorMetrics(BaseModel):
    records_fetched: int = 0
    records_accepted: int = 0
    records_rejected: int = 0
    
    # Specific semantic telemetry counters
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
    
    last_successful_fetch: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    last_poll_at: Optional[datetime] = None
    processing_latency_ms: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class MediaItem(BaseModel):
    media_type: str = "IMAGE"  # IMAGE, VIDEO, AUDIO
    url: str
    thumbnail_url: Optional[str] = None
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None


class CanonicalRawEvent(BaseModel):
    """
    Standardized raw ingestion envelope produced by all connectors.
    Decouples source-specific structures from the core processing pipeline.
    """
    ingestion_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    source_type: str
    external_id: Optional[str] = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    text: str = Field(min_length=1)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    location_source: str = "UNKNOWN"  # COORDINATES, METADATA, TEXT, UNKNOWN
    location_confidence: str = "LOW"  # HIGH, MEDIUM, LOW
    is_india_valid: bool = False
    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None
    suggested_category: Optional[str] = None
    severity: Optional[int] = Field(default=None, ge=1, le=4)
    media: List[MediaItem] = Field(default_factory=list)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    is_demo: bool = False
    idempotency_key: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class NormalizedEvent(BaseModel):
    """
    Validated and geocoded event ready for persistence into weather_reports
    and downstream AI classification.
    """
    ingestion_id: str
    source_id: str
    source_type: str
    external_id: Optional[str] = None
    tracking_id: str
    text: str
    primary_category: str = "UNKNOWN"
    severity: int = 2
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    location_source: str = "UNKNOWN"  # COORDINATES, METADATA, TEXT, UNKNOWN
    location_confidence: str = "LOW"
    is_india_valid: bool = False
    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None
    observed_at: datetime
    ingested_at: datetime
    media: List[MediaItem] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_demo: bool = False
    is_duplicate: bool = False
    idempotency_key: str

    model_config = ConfigDict(from_attributes=True)
