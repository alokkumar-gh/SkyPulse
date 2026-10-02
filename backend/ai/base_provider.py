"""
SkyPulse AI Provider Base Interface
Defines the standard abstraction for all AI, ML, NLP, and vision models.
Enables plug-and-play provider substitution (Local heuristic fallback vs External LLM/Vision).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    category: str  # RAINFALL, THUNDERSTORM, FLOODING, HEATWAVE, FOG, DUST_STORM, STRONG_WINDS, UNKNOWN
    sub_category: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    severity: int = Field(ge=1, le=4)
    evidence_signals: List[str] = Field(default_factory=list)
    method: str = "fallback_heuristic"
    model: str = "rule_based"
    fallback_used: bool = False


class WeatherAttribute(BaseModel):
    name: str  # rainfall_mm, wind_speed_kmh, temperature_c, flood_depth_ft, visibility_m
    value: float
    unit: str
    raw_mention: str


class EntityExtractionResult(BaseModel):
    event_mentions: List[str] = Field(default_factory=list)
    location_mentions: List[str] = Field(default_factory=list)
    resolved_city: Optional[str] = None
    resolved_district: Optional[str] = None
    resolved_state: Optional[str] = None
    resolved_lat: Optional[float] = None
    resolved_lon: Optional[float] = None
    weather_attributes: List[WeatherAttribute] = Field(default_factory=list)
    temporal_mentions: List[str] = Field(default_factory=list)
    observed_time: Optional[datetime] = None
    duration_str: Optional[str] = None
    impact_mentions: List[str] = Field(default_factory=list)
    evidence_phrases: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    method: str = "heuristic_regex"


class MediaAnalysisResult(BaseModel):
    has_media: bool = False
    media_type: Optional[str] = None  # image, video
    visual_category: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    signals: List[str] = Field(default_factory=list)
    supports_claimed_event: Optional[bool] = None
    is_blurry: bool = False
    phash: Optional[str] = None
    faces_detected: bool = False
    method: str = "metadata_heuristic"


class AnomalyResult(BaseModel):
    is_anomalous: bool = False
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0)
    z_score: Optional[float] = None
    anomaly_type: Optional[str] = None  # SPATIAL, TEMPORAL, VOLUME, CONTENT
    signals: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class EvidenceAssessmentResult(BaseModel):
    verification_status: str  # VERIFIED, LIKELY, UNVERIFIED, CONTRADICTED, REQUIRES_REVIEW
    verification_confidence: float = Field(ge=0.0, le=1.0)
    signal_scores: Dict[str, float] = Field(default_factory=dict)
    evidence_summary: List[Dict[str, Any]] = Field(default_factory=list)
    explanation: str
    method: str = "evidence_matrix"


class AIProvider(ABC):
    """
    Abstract contract for AI providers in SkyPulse.
    All AI models, whether deterministic local rules or remote LLMs, implement this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider."""
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Whether external credentials or resources are ready."""
        pass

    @abstractmethod
    async def classify_event(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        """Classify report into one of the 7 core weather event categories."""
        pass

    @abstractmethod
    async def extract_entities(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> EntityExtractionResult:
        """Extract structured spatial, meteorological, and temporal attributes."""
        pass

    @abstractmethod
    async def analyze_media(self, media_urls: List[str], claimed_category: Optional[str] = None) -> MediaAnalysisResult:
        """Extract visual evidence and perceptual fingerprints from media attachments."""
        pass

    @abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate a 384-dimensional dense semantic embedding vector."""
        pass

    @abstractmethod
    async def detect_anomaly(
        self,
        category: str,
        severity: int,
        city: Optional[str] = None,
        district: Optional[str] = None,
        state: Optional[str] = None,
        event_time: Optional[datetime] = None,
        nearby_events_count: int = 0,
    ) -> AnomalyResult:
        """Detect spatiotemporal, volume, or seasonal weather anomalies."""
        pass

    @abstractmethod
    async def assess_evidence(
        self,
        report_data: Dict[str, Any],
        official_data: Optional[Dict[str, Any]] = None,
        nearby_reports: Optional[List[Dict[str, Any]]] = None,
        source_trust: float = 0.5,
        media_analysis: Optional[MediaAnalysisResult] = None,
    ) -> EvidenceAssessmentResult:
        """Synthesize multi-source signals into an explainable verification verdict."""
        pass
