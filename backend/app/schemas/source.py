"""Source request/response and Reputation schemas."""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.models.enums import ReputationState


class SourceResponse(BaseModel):
    id: str
    name: str
    source_type: str
    trust_score: float
    is_active: bool
    is_demo: bool
    last_success_at: Optional[datetime] = None
    health_status: Optional[str] = None
    records_ingested_last_hour: int = 0

    model_config = ConfigDict(from_attributes=True)


class TrustHistoryEntry(BaseModel):
    recorded_at: datetime
    old_score: Optional[float] = None
    new_score: float
    outcome: Optional[str] = None
    triggering_event_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TrustHistoryResponse(BaseModel):
    source_id: str
    current_trust_score: float
    history: List[TrustHistoryEntry]


class CreateConnectorRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_type: str
    connector_class: str = Field(min_length=1, max_length=100)
    config: dict = Field(default_factory=dict)
    is_demo: bool = False


class UpdateConnectorRequest(BaseModel):
    is_active: Optional[bool] = None
    config: Optional[dict] = None


# =========================================================================
# Weather Source Reputation Graph Schemas (Signature Intelligence)
# =========================================================================

class CategoryReputationDetail(BaseModel):
    """Category-specific reliability analysis for a single weather source."""
    category: str
    observation_count: int = 0
    verified_count: int = 0
    contradicted_count: int = 0
    supported_count: int = 0
    support_rate: Optional[float] = None
    contradiction_rate: Optional[float] = None
    reliability_level: str = "INSUFFICIENT_EVIDENCE"  # STRONG_EVIDENCE, LIMITED_EVIDENCE, INSUFFICIENT_EVIDENCE, CONTRADICTED_PATTERN, MODERATE_EVIDENCE

    model_config = ConfigDict(from_attributes=True)


class ReputationFactorsBreakdown(BaseModel):
    """Granular 9-factor decomposition of source reliability."""
    verification_support_rate: Optional[float] = None
    contradiction_rate: Optional[float] = None
    corroboration_rate: Optional[float] = None
    duplicate_rate: Optional[float] = None
    temporal_consistency: Optional[float] = None
    spatial_consistency: Optional[float] = None
    category_consistency: Optional[float] = None
    evidence_volume_score: float = 0.0
    recency_score: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class ReputationTimelineEntry(BaseModel):
    """Key chronological milestone in a source's evidence lifecycle."""
    milestone_id: str
    timestamp: datetime
    event_type: str
    title: str
    description: str
    old_state: Optional[str] = None
    new_state: Optional[str] = None
    trust_score: float
    triggering_event_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SourceReputationResponse(BaseModel):
    """Complete, evidence-driven reputation profile for a weather source."""
    source_id: str
    source_name: str
    source_type: str
    current_trust: float
    reputation_state: ReputationState
    observation_count: int
    verified_count: int
    supported_count: int
    contradicted_count: int
    duplicate_count: int
    corroboration_rate: Optional[float] = None
    contradiction_rate: Optional[float] = None
    verification_support_rate: Optional[float] = None
    duplicate_rate: Optional[float] = None
    category_breakdown: Dict[str, CategoryReputationDetail] = Field(default_factory=dict)
    factors: ReputationFactorsBreakdown
    temporal_accuracy: Optional[float] = None
    spatial_accuracy: Optional[float] = None
    explanation: List[str] = Field(default_factory=list)
    is_official: bool = False
    is_active: bool = True
    last_observed_at: Optional[datetime] = None
    reputation_updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceReputationListResponse(BaseModel):
    """Paginated/filtered collection of source reputation profiles."""
    items: List[SourceReputationResponse]
    total: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class SourceReputationTimelineResponse(BaseModel):
    """Chronological reputation history and audit trace."""
    source_id: str
    source_name: str
    current_state: ReputationState
    timeline: List[ReputationTimelineEntry]

    model_config = ConfigDict(from_attributes=True)


class SourceReputationCategoriesResponse(BaseModel):
    """Category-specific breakdown for a source."""
    source_id: str
    source_name: str
    categories: Dict[str, CategoryReputationDetail]

    model_config = ConfigDict(from_attributes=True)


class SourceReputationEvidenceResponse(BaseModel):
    """Historical evidence items associated with a source."""
    source_id: str
    source_name: str
    evidence_count: int
    items: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
