"""
SkyPulse Report Credibility & Misinformation ML Model
=====================================================
Multi-feature tabular model assessing report plausibility and trustworthiness
using multi-modal signals (text, spatial, temporal, sensor telemetry, and DWEG evidence).
"""

import time
import logging
from typing import Dict, Any, List, Optional

from ml.schemas import MLCredibilityOutput, ModelStatus, CredibilityLabel
from ml.model_registry import model_registry
from ml.model_loader import model_loader
from ml.feature_extraction import feature_extractor
from app.core.config import settings

logger = logging.getLogger("skypulse.ml.credibility")

CREDIBILITY_CLASSES = ["CONTRADICTED", "UNVERIFIED", "SUSPICIOUS", "CREDIBLE"]


class CredibilityModel:
    """
    Evaluates report credibility using trained tabular ML (RandomForest / XGBoost / LogisticRegression).
    Integrates with deterministic VerificationEngine without replacing it.
    """

    def __init__(self, model_name: str = "credibility_model"):
        self.model_name = model_name
        self.threshold = float(getattr(settings, "ML_CREDIBILITY_THRESHOLD", 0.65) or 0.65)

    def predict_credibility(
        self,
        report_data: Dict[str, Any],
        source_data: Optional[Dict[str, Any]] = None,
        official_data: Optional[Dict[str, Any]] = None,
        nearby_reports: Optional[List[Dict[str, Any]]] = None,
        dweg_graph_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[MLCredibilityOutput]:
        """
        Runs ML credibility inference on multi-modal features.
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
                official_data=official_data,
                nearby_reports=nearby_reports,
                dweg_graph_context=dweg_graph_context,
            )
            vec = feature_extractor.features_to_vector(features)

            # 2. Run model prediction
            score = 0.5
            verdict = "UNVERIFIED"
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba([vec])[0]
                # Assume binary or multi-class output
                if len(probs) == 2:
                    score = float(probs[1])
                    verdict = "CREDIBLE" if score >= self.threshold else "SUSPICIOUS"
                else:
                    best_idx = int(probs.argmax())
                    verdict = CREDIBILITY_CLASSES[min(best_idx, len(CREDIBILITY_CLASSES) - 1)]
                    score = float(probs[best_idx])
            elif hasattr(model, "predict"):
                pred = model.predict([vec])[0]
                score = float(pred) if isinstance(pred, (int, float)) else 0.75
                verdict = "CREDIBLE" if score >= self.threshold else "SUSPICIOUS"

            latency_ms = (time.time() - t0) * 1000
            model_registry.record_inference(self.model_name, latency_ms)

            meta = model_registry.get_model(self.model_name)
            version = meta.version if meta else "1.0.0"

            used_features = [
                f"source_trust={features.source_trust_score}",
                f"nearby_1h={features.nearby_reports_1h}",
                f"imd_match={features.has_imd_bulletin}",
                f"datagov_match={features.has_datagov_record}",
                f"media_verified={features.media_verified}",
            ]

            return MLCredibilityOutput(
                label=CredibilityLabel(verdict) if verdict in CredibilityLabel._value2member_map_ else CredibilityLabel.UNVERIFIED,
                credibility_score=round(score, 2),
                confidence=round(score, 2),
                features_used=used_features,
                model_name=self.model_name,
                model_version=version,
                status=ModelStatus.LOADED,
                inference_latency_ms=round(latency_ms, 2),
                fallback_used=False,
            )

        except Exception as e:
            logger.error("ML Credibility Model inference error: %s", e)
            model_registry.update_status(self.model_name, ModelStatus.ERROR, error=str(e))
            return None

    async def predict_credibility_async(
        self,
        features_or_data: Any,
        source_data: Optional[Dict[str, Any]] = None,
        official_data: Optional[Dict[str, Any]] = None,
        nearby_reports: Optional[List[Dict[str, Any]]] = None,
        dweg_graph_context: Optional[Dict[str, Any]] = None,
    ) -> MLCredibilityOutput:
        if isinstance(features_or_data, list):
            model = model_loader.load_model(self.model_name)
            if model is None:
                return MLCredibilityOutput(
                    label=CredibilityLabel.UNVERIFIED,
                    credibility_score=0.0,
                    confidence=0.0,
                    status=ModelStatus.NOT_TRAINED,
                )
            # Run model on vector
            score = 0.5
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba([features_or_data])[0]
                score = float(probs[1]) if len(probs) == 2 else float(probs.max())
            return MLCredibilityOutput(
                label=CredibilityLabel.CREDIBLE if score >= self.threshold else CredibilityLabel.SUSPICIOUS,
                credibility_score=round(score, 2),
                confidence=round(score, 2),
                status=ModelStatus.LOADED,
            )

        res = self.predict_credibility(
            report_data=features_or_data,
            source_data=source_data,
            official_data=official_data,
            nearby_reports=nearby_reports,
            dweg_graph_context=dweg_graph_context,
        )
        if res is None:
            return MLCredibilityOutput(
                label=CredibilityLabel.UNVERIFIED,
                credibility_score=0.0,
                confidence=0.0,
                status=ModelStatus.NOT_TRAINED,
            )
        return res


# Global credibility model instance
credibility_model = CredibilityModel()
