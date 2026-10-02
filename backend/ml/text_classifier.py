"""
SkyPulse Weather Event Text Classifier
======================================
Deep learning / transformer text classification wrapper for real-time weather event categorization.
Executes trained ONNX Runtime models on CPU with softmax probabilities and granular latency profiling.
"""

import time
import math
import logging
from typing import Dict, Any, List, Optional

from ml.schemas import MLClassificationOutput, ModelStatus, WeatherEventCategory
from ml.model_registry import model_registry
from ml.model_loader import model_loader
from ml.preprocessing import clean_weather_text, simple_tokenize
from app.models.enums import WeatherCategory
from app.core.config import settings

logger = logging.getLogger("skypulse.ml.classifier")

DEFAULT_CATEGORIES = [
    WeatherCategory.RAINFALL.value,
    WeatherCategory.THUNDERSTORM.value,
    WeatherCategory.FLOODING.value,
    WeatherCategory.HEATWAVE.value,
    WeatherCategory.FOG.value,
    WeatherCategory.DUST_STORM.value,
    WeatherCategory.STRONG_WINDS.value,
    WeatherCategory.CYCLONE.value,
    WeatherCategory.HAILSTORM.value,
    WeatherCategory.SNOWFALL.value,
    WeatherCategory.SMOG.value,
    WeatherCategory.UNKNOWN.value,
]


def softmax(logits: List[float]) -> List[float]:
    """Computes stable softmax probabilities over logits."""
    if not logits:
        return []
    max_logit = max(logits)
    exps = [math.exp(l - max_logit) for l in logits]
    sum_exps = sum(exps)
    if sum_exps == 0:
        return [1.0 / len(logits)] * len(logits)
    return [round(e / sum_exps, 4) for e in exps]


class WeatherTextClassifier:
    """
    Production-ready weather event text classifier.
    Infers category probabilities using verified, active ONNX artifacts with sub-millisecond CPU profiling.
    """

    def __init__(self, model_name: str = "weather_event_classifier"):
        self.model_name = model_name
        self.threshold = float(getattr(settings, "ML_CLASSIFICATION_THRESHOLD", 0.60) or 0.60)

    def predict(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[MLClassificationOutput]:
        """
        Runs ML inference on input text.
        If no active trained model is available on disk, returns None (triggering safe fallback).
        """
        meta = model_registry.get_active_model(self.model_name)
        if not meta or not meta.active or meta.status not in [ModelStatus.ACTIVE, ModelStatus.LOADED]:
            return None

        session = model_loader.load_model(self.model_name, version=meta.model_version)
        if session is None:
            return None

        t_total_start = time.time()
        
        try:
            # 1. Preprocessing Stage
            t_prep_start = time.time()
            cleaned_text = clean_weather_text(text)
            tokens = simple_tokenize(cleaned_text, max_tokens=128)
            prep_latency_ms = (time.time() - t_prep_start) * 1000

            # 2. ONNX Inference Stage
            t_infer_start = time.time()
            logits: List[float] = []

            categories = meta.labels if meta.labels else DEFAULT_CATEGORIES

            if hasattr(session, "run"):  # ONNX Runtime InferenceSession
                import numpy as np
                inputs = session.get_inputs()
                input_feed = {}
                
                for inp in inputs:
                    name = inp.name
                    shape = [1, len(tokens)]
                    if "int64" in inp.type:
                        input_feed[name] = np.array([tokens], dtype=np.int64)
                    elif "int32" in inp.type:
                        input_feed[name] = np.array([tokens], dtype=np.int32)
                    elif "attention_mask" in name.lower():
                        input_feed[name] = np.ones(shape, dtype=np.int64)
                    else:
                        input_feed[name] = np.array([tokens], dtype=np.int64)

                outputs = session.run(None, input_feed)
                raw_logits = outputs[0][0]
                logits = [float(x) for x in raw_logits[:len(categories)]]
            elif callable(session):  # PyTorch model fallback
                import torch
                tensor_in = torch.tensor([tokens], dtype=torch.long)
                with torch.no_grad():
                    out = session(tensor_in)
                    raw_logits = out.logits[0].tolist() if hasattr(out, "logits") else out[0].tolist()
                    logits = [float(x) for x in raw_logits[:len(categories)]]

            infer_latency_ms = (time.time() - t_infer_start) * 1000

            if not logits:
                return None

            # 3. Postprocessing & Softmax Probabilities Stage
            t_post_start = time.time()
            while len(logits) < len(categories):
                logits.append(0.0)

            probs = softmax(logits)
            prob_dict = {categories[i]: probs[i] for i in range(min(len(categories), len(probs)))}

            best_idx = probs.index(max(probs))
            top_category_str = categories[best_idx]
            top_confidence = probs[best_idx]

            post_latency_ms = (time.time() - t_post_start) * 1000
            total_latency_ms = (time.time() - t_total_start) * 1000

            # Record Granular Latency Telemetry
            model_registry.record_inference_latency(
                model_name=self.model_name,
                prep_ms=prep_latency_ms,
                infer_ms=infer_latency_ms,
                post_ms=post_latency_ms,
                total_ms=total_latency_ms,
            )

            status = "PREDICTED"
            if top_confidence < self.threshold:
                status = "LOW_CONFIDENCE"

            version = meta.model_version or meta.version or "1.0.0"

            # Parse category to enum safely
            cat_enum = WeatherEventCategory.UNKNOWN
            if top_category_str in WeatherEventCategory._value2member_map_:
                cat_enum = WeatherEventCategory(top_category_str)

            return MLClassificationOutput(
                category=cat_enum,
                confidence=round(top_confidence, 4),
                probabilities=prob_dict,
                model_name=self.model_name,
                model_version=version,
                inference_latency_ms=round(total_latency_ms, 2),
                fallback_used=False,
                status=status,
            )

        except Exception as e:
            logger.error("ML Weather Classifier inference error: %s", e)
            model_registry.update_status(self.model_name, ModelStatus.ERROR, error=str(e), version=meta.model_version)
            return None


# Global classifier instance
weather_text_classifier = WeatherTextClassifier()
