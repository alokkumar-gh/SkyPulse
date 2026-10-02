"""
SkyPulse ML Inference Service
==============================
Main unified gateway for executing machine learning inference in SkyPulse.
Coordinates event classification, dense embeddings, credibility scoring,
and anomaly detection with zero-cost CPU optimization and transparent fallbacks.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ml.schemas import (
    MLClassificationOutput,
    MLCredibilityOutput,
    MLAnomalyOutput,
    MLDuplicateMatch,
    ModelStatus,
)
from ml.model_registry import model_registry
from ml.text_classifier import weather_text_classifier
from ml.credibility_model import credibility_model
from ml.duplicate_model import duplicate_model
from ml.anomaly_model import anomaly_model
from app.core.config import settings

logger = logging.getLogger("skypulse.ml.inference")


class MLInferenceService:
    """
    High-performance, CPU-optimized ML inference orchestrator.
    Executes trained open-source models with safe, automatic fallbacks.
    """

    def __init__(self):
        self.enabled = getattr(settings, "ML_ENABLED", True)

    async def classify_event(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[MLClassificationOutput]:
        """
        Classifies incoming weather text using the trained Weather Event Classifier.
        Returns None if model is unavailable or in NOT_TRAINED state.
        """
        if not self.enabled:
            return None

        try:
            result = weather_text_classifier.predict(text, metadata)
            return result
        except Exception as e:
            logger.warning("MLInferenceService.classify_event encountered an error: %s", e)
            return None

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generates a 384-dimensional dense semantic embedding vector.
        """
        try:
            return duplicate_model.encode(text)
        except Exception as e:
            logger.warning("MLInferenceService.generate_embedding error: %s", e)
            from ml.duplicate_model import generate_fallback_embedding
            return generate_fallback_embedding(text, dim=384)

    async def assess_credibility(
        self,
        report_data: Dict[str, Any],
        source_data: Optional[Dict[str, Any]] = None,
        official_data: Optional[Dict[str, Any]] = None,
        nearby_reports: Optional[List[Dict[str, Any]]] = None,
        dweg_graph_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[MLCredibilityOutput]:
        """
        Runs ML credibility scoring on multi-modal report features.
        Returns None if credibility model is in NOT_TRAINED state.
        """
        if not self.enabled:
            return None

        try:
            return credibility_model.predict_credibility(
                report_data=report_data,
                source_data=source_data,
                official_data=official_data,
                nearby_reports=nearby_reports,
                dweg_graph_context=dweg_graph_context,
            )
        except Exception as e:
            logger.warning("MLInferenceService.assess_credibility error: %s", e)
            return None

    async def detect_anomaly(
        self,
        report_data: Dict[str, Any],
        nearby_reports: Optional[List[Dict[str, Any]]] = None,
        source_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[MLAnomalyOutput]:
        """
        Runs ML anomaly detection using Isolation Forest / LOF algorithms.
        Returns None if anomaly model is in NOT_TRAINED state.
        """
        if not self.enabled:
            return None

        try:
            return anomaly_model.detect_anomaly(
                report_data=report_data,
                nearby_reports=nearby_reports,
                source_data=source_data,
            )
        except Exception as e:
            logger.warning("MLInferenceService.detect_anomaly error: %s", e)
            return None

    async def check_duplicate_pair(
        self,
        text1: str,
        text2: str,
        lat1: Optional[float] = None,
        lon1: Optional[float] = None,
        lat2: Optional[float] = None,
        lon2: Optional[float] = None,
        time_delta_seconds: Optional[float] = None,
    ) -> MLDuplicateMatch:
        """
        Evaluates semantic similarity and spatiotemporal proximity for duplicate detection.
        """
        return duplicate_model.evaluate_pair(
            text1=text1,
            text2=text2,
            lat1=lat1,
            lon1=lon1,
            lat2=lat2,
            lon2=lon2,
            time_delta_seconds=time_delta_seconds,
        )

    def get_status_summary(self) -> Dict[str, Any]:
        """Exposes runtime ML health telemetry to Admin APIs."""
        return model_registry.get_health_summary()


# Global ML Inference Service Instance
ml_inference_service = MLInferenceService()
