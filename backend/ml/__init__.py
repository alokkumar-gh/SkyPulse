"""SkyPulse ML Core Package.

Production-oriented, trainable, CPU-optimized ML intelligence layer.
"""

from ml.schemas import (
    ModelStatus,
    ModelFramework,
    ModelTask,
    WeatherEventCategory,
    CredibilityLabel,
    DuplicateMatchCategory,
    AnomalyStatus,
    ModelMetadata,
    MLClassificationOutput,
    MLCredibilityOutput,
    MLAnomalyOutput,
    MLDuplicateMatch,
    MultiModalFeatures,
    TrainingRecord,
    LabelType,
    LocationMethod,
    DataQualityStatus,
    DatasetReadiness,
    DatasetManifest,
    DatasetReadinessReport,
)
from ml.model_registry import ModelRegistry, model_registry
from ml.model_loader import ModelLoader, model_loader
from ml.inference_service import MLInferenceService, ml_inference_service
from ml.preprocessing import TextPreprocessor, text_preprocessor
from ml.feature_extraction import FeatureExtractor, feature_extractor

__all__ = [
    "ModelStatus",
    "ModelFramework",
    "ModelTask",
    "WeatherEventCategory",
    "CredibilityLabel",
    "DuplicateMatchCategory",
    "AnomalyStatus",
    "ModelMetadata",
    "MLClassificationOutput",
    "MLCredibilityOutput",
    "MLAnomalyOutput",
    "MLDuplicateMatch",
    "MultiModalFeatures",
    "TrainingRecord",
    "ModelRegistry",
    "model_registry",
    "ModelLoader",
    "model_loader",
    "MLInferenceService",
    "ml_inference_service",
    "TextPreprocessor",
    "text_preprocessor",
    "FeatureExtractor",
    "feature_extractor",
]
