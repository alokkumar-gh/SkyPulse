"""DWEG (Dynamic Weather Evidence Graph) schemas — placeholder for Phase 10."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class DWEGNode(BaseModel):
    id: str
    type: str
    label: str
    properties: Dict[str, Any] = {}


class DWEGEdge(BaseModel):
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = {}


class DWEGGraphResponse(BaseModel):
    event_id: str
    nodes: List[DWEGNode]
    edges: List[DWEGEdge]
    generated_at: datetime


class ConfidenceFieldFeature(BaseModel):
    type: str = "Feature"
    geometry: Dict[str, Any]
    properties: Dict[str, Any]


class ConfidenceFieldResponse(BaseModel):
    type: str = "FeatureCollection"
    features: List[ConfidenceFieldFeature]
    metadata: Optional[Dict[str, Any]] = None


class PropagationStep(BaseModel):
    step: int
    timestamp: Optional[datetime] = None
    location: Optional[Dict[str, Any]] = None
    evidence_count: int = 0
    severity: Optional[int] = None
    propagation_direction: Optional[str] = None
    time_delta_minutes: Optional[int] = None


class PropagationTimelineResponse(BaseModel):
    event_id: str
    propagation_steps: List[PropagationStep]
    is_still_propagating: bool


class EvidenceChainStep(BaseModel):
    step: int
    type: str
    source: str
    at: str
    location: Optional[str] = None
    value: Optional[str] = None


class EvidenceChainResponse(BaseModel):
    event_id: str
    narrative: str
    evidence_chain: List[EvidenceChainStep]
    confidence: float
    generated_at: datetime


class PropagationAlert(BaseModel):
    id: str
    event_id: str
    event_category: str
    alert_type: str
    message: str
    new_district: Optional[str] = None
    severity_trend: Optional[str] = None
    created_at: datetime


class PropagationAlertsResponse(BaseModel):
    alerts: List[PropagationAlert]
