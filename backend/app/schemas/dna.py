"""
SkyPulse Weather Event DNA Schemas
==================================
Strict Pydantic contracts for Weather Event DNA:
- Event Identity & Persistent Lifecycle
- Evidence Fingerprint & Source Aggregation
- Explainable Confidence Factor Breakdown
- Multi-dimensional Evidence Coverage
- Propagation Profiles & DWEG Integration
- Chronological Event Evolution Timeline
- Related Evidence-Supported Event Links
- Compact DNA Fingerprint Snapshot
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, ConfigDict, Field


class EvidenceFingerprintSource(BaseModel):
    """Granular evidence metrics for a specific observation source category."""
    source_type: str
    total_observations: int = 0
    supporting_observations: int = 0
    contradicting_observations: int = 0
    unverified_observations: int = 0
    latest_observation_at: Optional[datetime] = None
    spatial_coverage_km: float = 0.0
    confidence_weight: float = 0.5

    model_config = ConfigDict(from_attributes=True)


class EvidenceFingerprint(BaseModel):
    """Complete multi-source evidence summary for an event."""
    total_evidence_count: int = 0
    supporting_evidence_count: int = 0
    contradicting_evidence_count: int = 0
    unverified_evidence_count: int = 0
    duplicate_count: int = 0
    unique_sources_count: int = 0
    sources: Dict[str, EvidenceFingerprintSource] = Field(default_factory=dict)
    cross_source_corroborated: bool = False

    model_config = ConfigDict(from_attributes=True)


class ConfidenceFactorBreakdown(BaseModel):
    """Transparent explainable breakdown of the event confidence calculation."""
    source_reliability_score: float = Field(ge=0.0, le=1.0, default=0.5)
    cross_source_support_score: float = Field(ge=0.0, le=1.0, default=0.0)
    spatial_consistency_score: float = Field(ge=0.0, le=1.0, default=0.8)
    temporal_consistency_score: float = Field(ge=0.0, le=1.0, default=0.85)
    meteorological_score: float = Field(ge=0.0, le=1.0, default=0.5)
    media_score: float = Field(ge=0.0, le=1.0, default=0.5)
    contradiction_penalty: float = Field(ge=0.0, le=1.0, default=0.0)
    final_confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    explanation: str = ""

    model_config = ConfigDict(from_attributes=True)


class EvidenceCoverageBreakdown(BaseModel):
    """
    Evidence coverage measures how comprehensively an event is supported
    across available observational dimensions (distinct from confidence score).
    """
    overall_coverage_score: float = Field(ge=0.0, le=1.0, default=0.0)
    temporal_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    spatial_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    source_diversity_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    meteorological_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    official_validation_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    corroboration_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    active_dimensions_count: int = 0
    explanation: str = ""

    model_config = ConfigDict(from_attributes=True)


class DNAPropagationStage(BaseModel):
    """A distinct recorded stage in the physical propagation trajectory."""
    stage_number: int
    timestamp: datetime
    center_latitude: float
    center_longitude: float
    direction_name: str = "STATIONARY"
    direction_deg: Optional[float] = None
    estimated_speed_kmh: float = 0.0
    distance_from_origin_km: float = 0.0
    confidence: float = 0.5
    supporting_evidence_count: int = 1
    stage_description: str = ""

    model_config = ConfigDict(from_attributes=True)


class DNAPropagationProfile(BaseModel):
    """Spatio-temporal movement profile derived from DWEG evidence tracking."""
    has_propagation: bool = False
    stage_count: int = 0
    stages: List[DNAPropagationStage] = Field(default_factory=list)
    overall_direction: str = "STATIONARY"
    average_speed_kmh: float = 0.0
    total_distance_km: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class DNATimelineEntry(BaseModel):
    """Chronological milestone in the lifecycle of an Event DNA."""
    timestamp: datetime
    phase: str  # DETECTED, EMERGING, SUPPORTED, VERIFIED, PROPAGATING, SUBSIDING, RESOLVED, CONTRADICTED
    title: str
    description: str
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    confidence_at_step: Optional[float] = None
    evidence_count_at_step: Optional[int] = None
    location_summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RelatedEventLink(BaseModel):
    """Related event connection established via Dynamic Weather Evidence Graph."""
    event_id: str
    category: str
    severity: int
    verification_status: str
    relationship_type: str  # PROPAGATES_TO, SPATIALLY_ADJACENT, CORROBORATES, CONTRADICTS, SUPPORTS
    distance_km: Optional[float] = None
    time_delta_minutes: Optional[int] = None
    confidence: float = 0.5
    evidence_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class EventDNASnapshot(BaseModel):
    """Compact DNA fingerprint for quick operational rendering and dashboards."""
    event_id: str
    event_type: str
    status: str
    severity: int = 1
    source_count: int = 0
    evidence_count: int = 0
    conflict_count: int = 0
    duplicate_count: int = 0
    propagation_stages: int = 0
    confidence_score: float = 0.5
    evidence_coverage_score: float = 0.0
    first_observed_at: datetime
    last_updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventDNAResponse(BaseModel):
    """Comprehensive Weather Event DNA model answering identity, credibility, and evolution."""
    event_id: str
    event_type: str
    sub_category: Optional[str] = None
    status: str
    lifecycle_phase: str  # DETECTED, EMERGING, SUPPORTED, VERIFIED, PROPAGATING, SUBSIDING, RESOLVED, CONTRADICTED
    severity: int = 1
    first_observed_at: datetime
    last_observed_at: datetime
    resolved_at: Optional[datetime] = None

    # Spatial Footprint
    origin_latitude: Optional[float] = None
    origin_longitude: Optional[float] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    primary_city: Optional[str] = None
    primary_district: Optional[str] = None
    primary_state: Optional[str] = None
    spatial_radius_km: float = 0.0
    spatial_footprint_km: float = 0.0

    # Core Intelligence Sub-Objects
    confidence: ConfidenceFactorBreakdown
    evidence_coverage: EvidenceCoverageBreakdown
    evidence: EvidenceFingerprint
    propagation: DNAPropagationProfile
    timeline: List[DNATimelineEntry] = Field(default_factory=list)
    related_events: List[RelatedEventLink] = Field(default_factory=list)
    dweg_node_id: Optional[str] = None
    snapshot: EventDNASnapshot

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
