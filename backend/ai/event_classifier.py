import logging
from typing import Dict, Any, List, Optional
from ai.base_provider import ClassificationResult, AIProvider
from ai.fallback_provider import FallbackAIProvider
from ai.external_provider import ExternalAIProvider
from ai.groq_provider import GroqProvider, groq_provider
from ml.inference_service import ml_inference_service

logger = logging.getLogger("skypulse.event_classifier")


class EventClassifier:
    """
    Classifies raw weather reports into the 7 canonical categories.
    Order of preference:
      1. Real Trainable ML Model (backend/ml) if trained model artifacts exist
      2. Groq LLM Provider (if configured and enabled)
      3. Deterministic Fallback AI Provider (offline heuristic)
    """

    def __init__(self, provider: Optional[AIProvider] = None):
        if provider:
            self.provider = provider
        elif groq_provider.is_configured:
            self.provider = groq_provider
        elif ExternalAIProvider().is_configured:
            self.provider = ExternalAIProvider()
        else:
            self.provider = FallbackAIProvider()

    async def classify(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        # 1. Attempt genuine ML inference
        try:
            ml_res = await ml_inference_service.classify_event(text)
            if ml_res:
                signals = [
                    f"ml_prob_{k.lower()}:{v:.2f}"
                    for k, v in ml_res.probabilities.items()
                    if v >= 0.15
                ]
                return ClassificationResult(
                    category=ml_res.category.value,
                    confidence=ml_res.confidence,
                    severity=ml_res.severity or 2,
                    evidence_signals=signals,
                    method="ml_model",
                    model=f"{ml_res.model_name}:{ml_res.model_version}",
                    fallback_used=False,
                )
        except Exception as e:
            logger.warning("ML event classification inference failed or unconfigured: %s", e)

        # 2. Fallback to deterministic heuristic provider
        return await self.provider.classify_event(text, metadata)

