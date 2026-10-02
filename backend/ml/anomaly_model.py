"""
SkyPulse Spatiotemporal Anomaly Detection ML Model
==================================================
Unsupervised ML anomaly detection using Isolation Forest / LOF algorithms
to detect unusual spatial clusters, sudden volume spikes, and unseasonal weather anomalies.
"""

import time
import logging
from typing import Dict, Any, List, Optional

from ml.schemas import MLAnomalyOutput, ModelStatus
from ml.model_registry import model_registry
from ml.model_loader import model_loader
from ml.feature_extraction import feature_extractor
from app.core.config import settings

logger = logging.getLogger("skypulse.ml.anomaly")


class AnomalyModel:
    """
    Evaluates weather event reports for spatiotemporal, volume, or measurement anomalies.
    Runs trained Isolation Forest or LOF models on CPU.
    """

    def __init__(self, model_name: str = "anomaly_model"):
        self.model_name = model_name
        self.threshold = float(getattr(settings, "ML_ANOMALY_THRESHOLD", 0.70) or 0.70)

    def detect_anomaly(
        self,
        report_data: Dict[str, Any],
        nearby_reports: Optional[List[Dict[str, Any]]] = None,
        source_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[MLAnomalyOutput]:
        """
        Runs ML anomaly inference on multi-modal report features.
        If no trained weights exist, returns None (triggering safe fallback).
        """
        model = model_loader.load_model(self.model_name)
        if model is None:
            return None

        t0 = time.time()
        try:
            # 1. Extract feature vector
            features = feature_extractor.extract_features(
                report_data=report_data,
                source_data=source_data,
                nearby_reports=nearby_reports,
            )
            vec = feature_extractor.features_to_vector(features)

            # 2. Run model prediction
            anomaly_score = 0.0
            is_anomalous = False
            signals = []

            if hasattr(model, "score_samples"):
                # Isolation Forest outputs negative anomaly scores (lower = more anomalous)
                raw_score = model.score_samples([vec])[0]
                # Normalize raw score roughly between 0.0 and 1.0
                anomaly_score = max(0.0, min(1.0, -raw_score))
                is_anomalous = anomaly_score >= self.threshold
            elif hasattr(model, "predict"):
                pred = model.predict([vec])[0]
                is_anomalous = pred == -1  # -1 indicates outlier in scikit-learn
                anomaly_score = 0.85 if is_anomalous else 0.20

            # Determine anomaly type
            anomaly_type = None
            if is_anomalous:
                if features.nearby_reports_1h == 0 and (report_data.get("severity") or 1) >= 3:
                    anomaly_type = "SPATIAL"
                    signals.append("Isolated high-severity event without nearby corroboration")
                elif features.rainfall_mm and features.rainfall_mm > 150:
                    anomaly_type = "MEASUREMENT"
                    signals.append(f"Extreme precipitation measurement: {features.rainfall_mm} mm")
                else:
                    anomaly_type = "VOLUME"
                    signals.append("Unusual multi-modal feature distribution")

            latency_ms = (time.time() - t0) * 1000
            model_registry.record_inference(self.model_name, latency_ms)

            meta = model_registry.get_model(self.model_name)
            version = meta.version if meta else "1.0.0"

            return MLAnomalyOutput(
                is_anomalous=is_anomalous,
                anomaly_score=round(anomaly_score, 2),
                anomaly_type=anomaly_type,
                signals=signals,
                model_name=self.model_name,
                model_version=version,
                inference_latency_ms=round(latency_ms, 2),
                fallback_used=False,
            )

        except Exception as e:
            logger.error("ML Anomaly Model inference error: %s", e)
            model_registry.update_status(self.model_name, ModelStatus.ERROR, error=str(e))
            return None

    async def predict_anomaly(
        self,
        features_or_data: Any,
        nearby_reports: Optional[List[Dict[str, Any]]] = None,
        source_data: Optional[Dict[str, Any]] = None,
    ) -> MLAnomalyOutput:
        """Evaluates anomaly on raw vector or report dictionary, returning MLAnomalyOutput."""
        if isinstance(features_or_data, list):
            # Input is already a numerical feature vector
            model = model_loader.load_model(self.model_name)
            if model is None:
                return MLAnomalyOutput(
                    is_anomalous=False,
                    anomaly_score=0.0,
                    status=ModelStatus.NOT_TRAINED,
                )
            # Run on vector
            score = 0.0
            is_anomalous = False
            if hasattr(model, "score_samples"):
                raw_score = model.score_samples([features_or_data])[0]
                score = max(0.0, min(1.0, -raw_score))
                is_anomalous = score >= self.threshold
            return MLAnomalyOutput(
                is_anomalous=is_anomalous,
                anomaly_score=round(score, 2),
                status=ModelStatus.LOADED,
            )

        res = self.detect_anomaly(features_or_data, nearby_reports, source_data)
        if res is None:
            return MLAnomalyOutput(
                is_anomalous=False,
                anomaly_score=0.0,
                status=ModelStatus.NOT_TRAINED,
            )
        return res


# Global anomaly model instance
anomaly_model = AnomalyModel()
