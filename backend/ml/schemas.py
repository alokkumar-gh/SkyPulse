"""
SkyPulse ML Schemas and Data Models
===================================
Pydantic contracts for ML inputs, outputs, feature vectors,
model registry metadata, training schemas, and evaluation metrics.
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, model_validator


class ModelStatus(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    ARTIFACT_FOUND = "ARTIFACT_FOUND"
    VALIDATING = "VALIDATING"
    READY = "READY"
    LOADED = "LOADED"
    ACTIVE = "ACTIVE"
    ERROR = "ERROR"
    DISABLED = "DISABLED"
    # Legacy / Compatibility statuses
    NOT_TRAINED = "NOT_TRAINED"
    TRAINED = "TRAINED"
    NOT_LOADED = "NOT_LOADED"


class ModelFramework(str, Enum):
    ONNX = "ONNX"
    PYTORCH = "PYTORCH"
    HUGGINGFACE = "HUGGINGFACE"
    SCIKIT_LEARN = "SCIKIT_LEARN"
    CUSTOM = "CUSTOM"


class ModelTask(str, Enum):
    TEXT_CLASSIFICATION = "TEXT_CLASSIFICATION"
    CREDIBILITY = "CREDIBILITY"
    ANOMALY_DETECTION = "ANOMALY_DETECTION"
    EMBEDDING = "EMBEDDING"


class WeatherEventCategory(str, Enum):
    RAINFALL = "RAINFALL"
    THUNDERSTORM = "THUNDERSTORM"
    FLOODING = "FLOODING"
    HEATWAVE = "HEATWAVE"
    FOG = "FOG"
    DUST_STORM = "DUST_STORM"
    STRONG_WINDS = "STRONG_WINDS"
    CYCLONE = "CYCLONE"
    HAILSTORM = "HAILSTORM"
    SNOWFALL = "SNOWFALL"
    SMOG = "SMOG"
    UNKNOWN = "UNKNOWN"


class CredibilityLabel(str, Enum):
    CREDIBLE = "CREDIBLE"
    SUSPICIOUS = "SUSPICIOUS"
    UNVERIFIED = "UNVERIFIED"
    CONTRADICTED = "CONTRADICTED"


class DuplicateMatchCategory(str, Enum):
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    NEAR_DUPLICATE = "NEAR_DUPLICATE"
    RELATED_REPORT = "RELATED_REPORT"
    UNIQUE = "UNIQUE"


class AnomalyStatus(str, Enum):
    NORMAL = "NORMAL"
    SPATIAL = "SPATIAL"
    TEMPORAL = "TEMPORAL"
    VOLUME = "VOLUME"
    MEASUREMENT = "MEASUREMENT"
    ANOMALOUS = "ANOMALOUS"


class MLClassificationOutput(BaseModel):
    category: WeatherEventCategory
    confidence: float = Field(ge=0.0, le=1.0)
    probabilities: Dict[str, float] = Field(default_factory=dict)
    model_name: str
    model_version: str
    severity: Optional[int] = None
    inference_latency_ms: float = 0.0
    fallback_used: bool = False
    status: str = "PREDICTED"

    @model_validator(mode="before")
    @classmethod
    def convert_category(cls, data: Any) -> Any:
        if isinstance(data, dict) and "category" in data:
            cat_val = data["category"]
            if isinstance(cat_val, WeatherEventCategory):
                return data
            if hasattr(cat_val, "value"):
                cat_val = cat_val.value
            cat_str = str(cat_val).upper().strip()
            if cat_str in WeatherEventCategory._value2member_map_:
                data["category"] = WeatherEventCategory(cat_str)
            else:
                data["category"] = WeatherEventCategory.UNKNOWN
        return data


class MLCredibilityOutput(BaseModel):
    label: CredibilityLabel = CredibilityLabel.UNVERIFIED
    credibility_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    features_used: List[str] = Field(default_factory=list)
    model_name: str = "credibility_model"
    model_version: str = "1.0.0"
    status: ModelStatus = ModelStatus.NOT_TRAINED
    inference_latency_ms: float = 0.0
    fallback_used: bool = False


class MLAnomalyOutput(BaseModel):
    is_anomalous: bool = False
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0)
    anomaly_status: AnomalyStatus = AnomalyStatus.NORMAL
    anomaly_type: Optional[str] = None
    signals: List[str] = Field(default_factory=list)
    model_name: str = "anomaly_model"
    model_version: str = "1.0.0"
    status: ModelStatus = ModelStatus.NOT_TRAINED
    inference_latency_ms: float = 0.0
    fallback_used: bool = False


class MLDuplicateMatch(BaseModel):
    match_category: DuplicateMatchCategory = DuplicateMatchCategory.UNIQUE
    match_type: str = "UNIQUE"
    semantic_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_report_id: Optional[str] = None
    spatial_distance_km: Optional[float] = None
    temporal_delta_seconds: Optional[float] = None


class ModelMetadata(BaseModel):
    name: str = ""
    model_name: str = ""
    version: str = "1.0.0"
    model_version: str = "1.0.0"
    task: Union[ModelTask, str] = ModelTask.TEXT_CLASSIFICATION
    framework: ModelFramework = ModelFramework.ONNX
    artifact_path: Optional[str] = None
    checksum: Optional[str] = None
    artifact_sha256: Optional[str] = None
    checksum_status: Optional[str] = None
    classes: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    dataset_version: Optional[str] = None
    training_period: Dict[str, Any] = Field(default_factory=dict)
    validation_period: Dict[str, Any] = Field(default_factory=dict)
    test_period: Dict[str, Any] = Field(default_factory=dict)
    status: ModelStatus = ModelStatus.NOT_CONFIGURED
    active: bool = False
    loaded: bool = False
    artifact_available: bool = False
    artifact_valid: bool = False
    fallback_enabled: bool = True
    last_loaded_at: Optional[datetime] = None
    last_validated_at: Optional[datetime] = None
    last_inference_at: Optional[datetime] = None
    inference_count: int = 0
    total_latency_ms: float = 0.0
    error_count: int = 0
    last_error: Optional[str] = None
    training_metadata: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    latency_breakdown: Dict[str, float] = Field(default_factory=lambda: {
        "preprocessing_ms": 0.0,
        "inference_ms": 0.0,
        "postprocessing_ms": 0.0,
        "total_ms": 0.0,
    })
    avg_latency_breakdown: Dict[str, float] = Field(default_factory=lambda: {
        "preprocessing_ms": 0.0,
        "inference_ms": 0.0,
        "postprocessing_ms": 0.0,
        "total_ms": 0.0,
    })

    @model_validator(mode="before")
    @classmethod
    def sync_model_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "name" in data and not data.get("model_name"):
                data["model_name"] = data["name"]
            elif "model_name" in data and not data.get("name"):
                data["name"] = data["model_name"]
            if "version" in data and not data.get("model_version"):
                data["model_version"] = data["version"]
            elif "model_version" in data and not data.get("version"):
                data["version"] = data["model_version"]
            if "classes" in data and not data.get("labels"):
                data["labels"] = data["classes"]
            elif "labels" in data and not data.get("classes"):
                data["classes"] = data["labels"]
            if "checksum" in data and not data.get("artifact_sha256"):
                data["artifact_sha256"] = data["checksum"]
            elif "artifact_sha256" in data and not data.get("checksum"):
                data["checksum"] = data["artifact_sha256"]
        return data

    @property
    def avg_latency_ms(self) -> float:
        return (self.total_latency_ms / self.inference_count) if self.inference_count > 0 else 0.0


class LabelType(str, Enum):
    STRONG = "STRONG"
    WEAK = "WEAK"
    UNLABELED = "UNLABELED"


class LocationMethod(str, Enum):
    EXACT_COORDINATE = "EXACT_COORDINATE"
    STATION = "STATION"
    DISTRICT_CENTROID = "DISTRICT_CENTROID"
    ERA5_GRID = "ERA5_GRID"
    NEAREST_ERA5_GRID = "ERA5_GRID"
    GEOCODED = "GEOCODED"


class DataQualityStatus(str, Enum):
    VALID = "VALID"
    SUSPICIOUS = "SUSPICIOUS"
    INVALID = "INVALID"


class DatasetReadiness(str, Enum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    NOT_READY = "NOT_READY"


class TrainingRecord(BaseModel):
    """Canonical training sample format for weather intelligence datasets."""
    id: Optional[str] = None
    text: str
    category: WeatherEventCategory
    severity: int = Field(ge=1, le=4)
    timestamp: Optional[Union[str, datetime]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    verified: bool = False
    verification_status: Optional[str] = "UNVERIFIED"
    label_source: Optional[str] = "HEURISTIC"
    label_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    label_method: Optional[str] = "EXPLICIT_WARNING"
    language: str = "en"
    location_method: Optional[str] = "EXACT_COORDINATE"
    conflict_flag: bool = False
    candidate_labels: List[str] = Field(default_factory=list)
    aligned_timestamp: Optional[str] = None
    alignment_window: Optional[str] = None
    reanalysis_features: Optional[Dict[str, Any]] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def convert_category_and_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "category" in data:
                cat_val = data["category"]
                if not isinstance(cat_val, WeatherEventCategory):
                    if hasattr(cat_val, "value"):
                        cat_val = cat_val.value
                    cat_str = str(cat_val).upper().strip()
                    if cat_str in WeatherEventCategory._value2member_map_:
                        data["category"] = WeatherEventCategory(cat_str)
                    else:
                        data["category"] = WeatherEventCategory.UNKNOWN
            if "id" not in data or not data["id"]:
                import uuid
                data["id"] = str(uuid.uuid4())
            if "reanalysis_features" not in data or data["reanalysis_features"] is None:
                data["reanalysis_features"] = {}
            if "label_method" not in data or data["label_method"] is None:
                data["label_method"] = "METEOROLOGICAL_RULE"
            if "location_method" not in data or data["location_method"] is None:
                data["location_method"] = "EXACT_COORDINATE"
        return data


class DatasetManifest(BaseModel):
    """Manifest describing a compiled dataset version, its sources, quality, and hash."""
    dataset_version: str
    creation_timestamp: str
    sources: List[str] = Field(default_factory=list)
    source_statuses: Dict[str, str] = Field(default_factory=dict)
    source_versions: Dict[str, str] = Field(default_factory=dict)
    total_records: int = 0
    train_records: int = 0
    val_records: int = 0
    test_records: int = 0
    valid_records: int = 0
    rejected_records: int = 0
    duplicate_records: int = 0
    strong_labels: int = 0
    weak_labels: int = 0
    unlabeled_records: int = 0
    class_distribution: Dict[str, int] = Field(default_factory=dict)
    language_distribution: Dict[str, int] = Field(default_factory=dict)
    date_range: Dict[str, Optional[str]] = Field(default_factory=dict)
    geographic_bounds: Dict[str, Optional[float]] = Field(default_factory=dict)
    quality_summary: Dict[str, Any] = Field(default_factory=dict)
    sha256_checksum: str = ""
    split_info: Dict[str, Any] = Field(default_factory=dict)



class DatasetReadinessReport(BaseModel):
    """Evaluates whether an assembled dataset satisfies production training criteria."""
    status: DatasetReadiness = DatasetReadiness.NOT_READY
    overall_score: float = 0.0
    total_samples: int = 0
    class_counts: Dict[str, int] = Field(default_factory=dict)
    insufficient_classes: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    temporal_leakage_detected: bool = False
    spatial_leakage_detected: bool = False
    evaluated_at: str = ""


class MultiModalFeatures(BaseModel):
    """Multi-modal feature vector extracted for credibility and anomaly scoring."""
    # Text features
    char_length: int = 0
    word_count: int = 0
    text_length: int = 0
    urgency_keyword_count: int = 0
    sentiment_subjectivity: float = 0.0

    # Spatiotemporal features
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    event_age_hours: float = 0.0
    nearby_reports_1h: int = 0
    nearby_reports_24h: int = 0

    # Source features
    source_type: str = "CITIZEN"
    source_trust: float = 0.5
    source_trust_score: float = 0.5
    source_historical_verifications: int = 0

    # Weather observations
    rainfall_mm: Optional[float] = None
    temperature_c: Optional[float] = None
    wind_kmph: Optional[float] = None

    # Evidence corroboration features
    has_imd_bulletin: bool = False
    has_imd_corroboration: bool = False
    has_datagov_record: bool = False
    has_media_attachment: bool = False
    media_verified: bool = False
    dweg_degree_count: int = 0
    dense_feature_vector: List[float] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def sync_feature_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "char_length" in data and not data.get("text_length"):
                data["text_length"] = data["char_length"]
            if "has_imd_bulletin" in data and "has_imd_corroboration" not in data:
                data["has_imd_corroboration"] = data["has_imd_bulletin"]
            if "source_trust_score" in data and "source_trust" not in data:
                data["source_trust"] = data["source_trust_score"]
        return data

