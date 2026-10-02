"""
SkyPulse Emerging Weather Event Schemas
======================================
Strict Pydantic models for the Emerging Weather Event Detector.
Defines schemas for emergence factors, individual signals, milestone timelines,
and full emerging event responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from app.models.enums import EmergenceState, WeatherCategory, EventSeverity


class EmergenceFactorBreakdown(BaseModel):
    """Transparent decomposition of the 9 emergence score drivers."""
    spatial_convergence_score: float = Field(..., ge=0.0, le=1.0, description="Spatial density and proximity clustering [0..1]")
    temporal_acceleration_score: float = Field(..., ge=0.0, le=1.0, description="Rate of incoming report acceleration [0..1]")
    source_diversity_score: float = Field(..., ge=0.0, le=1.0, description="Independent multi-source corroboration [0..1]")
    category_consistency_score: float = Field(..., ge=0.0, le=1.0, description="Agreement across weather category/met synergy [0..1]")
    meteorological_support_score: float = Field(..., ge=0.0, le=1.0, description="Sensor/station/radar physical confirmation [0..1]")
    anomaly_strength_score: float = Field(..., ge=0.0, le=1.0, description="Statistical baseline anomaly intensity [0..1]")
    dweg_connectivity_score: float = Field(..., ge=0.0, le=1.0, description="Dynamic Weather Evidence Graph node degree [0..1]")
    evidence_freshness_score: float = Field(..., ge=0.0, le=1.0, description="Freshness decay factor of latest observations [0..1]")
    contradiction_penalty: float = Field(..., ge=0.0, le=1.0, description="Penalty for disproving/conflicting observations [0..1]")
    final_emergence_score: float = Field(..., ge=0.0, le=1.0, description="Synthesized emergence score [0..1]")
    explanation_bullets: List[str] = Field(default_factory=list, description="Human-readable transparent explanations")


class EmergingSignalItem(BaseModel):
    """An individual weather signal or report feeding the emerging cluster."""
    report_id: str
    source_id: Optional[str] = None
    source_name: str
    source_type: str
    source_trust_score: float = 1.0
    category: str
    severity: int = 1
    latitude: float
    longitude: float
    location_name: Optional[str] = None
    event_time: datetime
    ingested_at: datetime
    raw_text: Optional[str] = None
    confidence_score: float = 0.5
    is_contradictory: bool = False
    weight: float = 1.0
    distance_from_centroid_km: float = 0.0


class EmergingTimelineMilestone(BaseModel):
    """Chronological state progression milestone."""
    timestamp: datetime
    state: EmergenceState
    title: str
    description: str
    emergence_score: float
    signal_count: int


class EmergingEventResponse(BaseModel):
    """Full emerging event detector response payload."""
    id: str = Field(..., description="Unique deterministic cluster ID (e.g. emg-xxxxxxxx)")
    dominant_category: WeatherCategory
    sub_category: Optional[str] = None
    severity: EventSeverity = EventSeverity.MODERATE
    state: EmergenceState
    emergence_score: float = Field(..., ge=0.0, le=1.0)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    evidence_count: int = Field(..., ge=0)
    source_count: int = Field(..., ge=0)
    unique_source_types: List[str] = Field(default_factory=list)
    spatial_centroid_lat: float
    spatial_centroid_lon: float
    spatial_radius_km: float
    spatial_footprint_km2: float
    temporal_window_minutes: int
    acceleration_indicator: float = Field(..., description="Velocity factor of incoming observations (e.g. 1.5x)")
    location_summary: Optional[str] = None
    state_name: Optional[str] = None
    district: Optional[str] = None
    first_signal_at: datetime
    latest_signal_at: datetime
    factors: EmergenceFactorBreakdown
    signals: List[EmergingSignalItem] = Field(default_factory=list)
    timeline: List[EmergingTimelineMilestone] = Field(default_factory=list)
    canonical_event_id: Optional[str] = None
    event_dna_id: Optional[str] = None
    dweg_node_id: Optional[str] = None
    detected_at: datetime
    updated_at: datetime


class EmergingEventListResponse(BaseModel):
    """List response of active emerging weather clusters."""
    total: int
    active_count: int
    items: List[EmergingEventResponse]


class EmergingEventSignalsResponse(BaseModel):
    """Detailed signals contributing to an emerging event."""
    emerging_event_id: str
    total_signals: int
    dominant_category: str
    signals: List[EmergingSignalItem]


class EmergingEventTimelineResponse(BaseModel):
    """Timeline milestones for an emerging event."""
    emerging_event_id: str
    state: EmergenceState
    milestones: List[EmergingTimelineMilestone]


class EmergingEventEvidenceResponse(BaseModel):
    """Evidence breakdown and source distribution for an emerging event."""
    emerging_event_id: str
    emergence_score: float
    confidence_score: float
    source_diversity: Dict[str, int]
    supporting_signals_count: int
    contradicting_signals_count: int
    factors: EmergenceFactorBreakdown
