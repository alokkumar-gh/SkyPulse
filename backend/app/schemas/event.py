"""Weather event request/response schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from app.schemas.common import LocationSchema
from app.schemas.report import SourceSummary, MediaSummary


class VerificationSummary(BaseModel):
    status: str
    confidence_score: Optional[float] = None
    explanation: Optional[str] = None
    evidence_items: List[dict] = []
    method: Optional[str] = None
    reviewed_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EvidenceReportSummary(BaseModel):
    id: str
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    publisher: Optional[str] = None
    source_url: Optional[str] = None
    title: Optional[str] = None
    snippet: Optional[str] = None
    event_time: Optional[datetime] = None
    ingested_at: Optional[datetime] = None
    severity: Optional[int] = None
    relevance: Optional[str] = "High spatial-temporal agreement"
    trust_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class SourceItemSummary(BaseModel):
    source_id: Optional[str] = None
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    publisher: Optional[str] = None
    source_url: Optional[str] = None
    title: Optional[str] = None
    snippet: Optional[str] = None
    published_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EventSummary(BaseModel):
    id: str
    category: Optional[str] = None
    sub_category: Optional[str] = None
    phenomenon: Optional[str] = None
    event_nature: Optional[str] = "OBSERVATION"
    temporal_scope: Optional[str] = "CURRENT"
    is_current_observation: bool = True
    evidence_basis: Optional[str] = "CURRENT_OBSERVATION"
    severity: Optional[int] = None
    confidence_score: Optional[float] = None
    verification_status: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location: Optional[LocationSchema] = None
    first_reported_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None
    evidence_count: int = 0
    sources_count: int = 1
    publishers: List[str] = []
    is_anomalous: bool = False
    is_active: bool = True
    is_demo: bool = False

    model_config = ConfigDict(from_attributes=True)


class EventDetail(BaseModel):
    id: str
    category: Optional[str] = None
    sub_category: Optional[str] = None
    phenomenon: Optional[str] = None
    event_nature: Optional[str] = "OBSERVATION"
    temporal_scope: Optional[str] = "CURRENT"
    is_current_observation: bool = True
    evidence_basis: Optional[str] = "CURRENT_OBSERVATION"
    severity: Optional[int] = None
    confidence_score: Optional[float] = None
    verification_status: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location: Optional[LocationSchema] = None
    first_reported_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    evidence_count: int = 0
    sources_count: int = 1
    publishers: List[str] = []
    sources: List[SourceItemSummary] = []
    is_anomalous: bool = False
    anomaly_z_score: Optional[float] = None
    verification: Optional[VerificationSummary] = None
    evidence_reports: List[EvidenceReportSummary] = []
    evidence: List[dict] = []
    media_gallery: List[MediaSummary] = []
    is_demo: bool = False

    model_config = ConfigDict(from_attributes=True)


class TimelineEntry(BaseModel):
    timestamp: Optional[datetime] = None
    report_id: str
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    severity: Optional[int] = None
    location: Optional[LocationSchema] = None
    summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EventTimeline(BaseModel):
    event_id: str
    timeline: List[TimelineEntry]


class NearbyEvent(EventSummary):
    distance_km: Optional[float] = None
