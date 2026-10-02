"""Report request/response schemas."""
from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator, ConfigDict
import uuid

from app.schemas.common import LocationSchema


# ─── Validators ──────────────────────────────────────────────────────────────

VALID_CATEGORIES = {
    "RAINFALL", "THUNDERSTORM", "FLOODING", "HEATWAVE",
    "FOG", "DUST_STORM", "STRONG_WINDS", "SNOWFALL", "HAILSTORM", "CYCLONE", "SMOG"
}

INDIA_LAT_MIN, INDIA_LAT_MAX = 6.5, 37.6
INDIA_LON_MIN, INDIA_LON_MAX = 68.0, 97.5


# ─── Requests ─────────────────────────────────────────────────────────────────

class CreateReportRequest(BaseModel):
    description: str = Field(min_length=5, max_length=2000)
    event_type: str
    severity: Optional[int] = Field(default=None, ge=1, le=4)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = Field(default=None, max_length=255)
    event_time: Optional[datetime] = None
    media_ids: Optional[List[str]] = Field(default_factory=list)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        v = v.upper()
        if v not in VALID_CATEGORIES:
            raise ValueError(f"event_type must be one of {sorted(VALID_CATEGORIES)}")
        return v

    @field_validator("latitude")
    @classmethod
    def validate_lat(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (INDIA_LAT_MIN <= v <= INDIA_LAT_MAX):
            raise ValueError(f"latitude must be between {INDIA_LAT_MIN} and {INDIA_LAT_MAX} (India bounds)")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_lon(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (INDIA_LON_MIN <= v <= INDIA_LON_MAX):
            raise ValueError(f"longitude must be between {INDIA_LON_MIN} and {INDIA_LON_MAX} (India bounds)")
        return v


# ─── Responses ────────────────────────────────────────────────────────────────

class MediaSummary(BaseModel):
    id: str
    media_type: str
    url: str
    thumbnail_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SourceSummary(BaseModel):
    id: str
    name: str
    type: str
    trust_score: float

    model_config = ConfigDict(from_attributes=True)


class ReportSummary(BaseModel):
    id: str
    primary_category: Optional[str] = None
    sub_category: Optional[str] = None
    severity: Optional[int] = None
    confidence_score: Optional[float] = None
    classification_confidence: Optional[float] = None
    location: Optional[LocationSchema] = None
    event_time: Optional[datetime] = None
    ingested_at: datetime
    canonical_event_id: Optional[str] = None
    verification_status: Optional[str] = None
    source: Optional[SourceSummary] = None
    media_count: int = 0
    is_demo: bool = False

    model_config = ConfigDict(from_attributes=True)


class ReportDetail(BaseModel):
    id: str
    normalized_text: Optional[str] = None
    primary_category: Optional[str] = None
    sub_category: Optional[str] = None
    severity: Optional[int] = None
    classification_confidence: Optional[float] = None
    classification_method: Optional[str] = None
    location: Optional[LocationSchema] = None
    event_time: Optional[datetime] = None
    ingested_at: datetime
    canonical_event_id: Optional[str] = None
    is_duplicate: bool = False
    ai_extraction: Optional[Dict[str, Any]] = None
    source: Optional[SourceSummary] = None
    media: List[MediaSummary] = []
    verification_status: Optional[str] = None
    is_demo: bool = False

    model_config = ConfigDict(from_attributes=True)


class CreateReportResponse(BaseModel):
    id: str
    status: str
    tracking_id: str
    message: str
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MediaUploadResponse(BaseModel):
    media_id: str
    media_type: str
    filename: str
    size_bytes: int
    status: str = "UPLOADED"

    model_config = ConfigDict(from_attributes=True)
