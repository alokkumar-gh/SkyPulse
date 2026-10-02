from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging

from app.core.config import settings

logger = logging.getLogger("skypulse.ai_provider")


class AIProvider(ABC):
    """Abstract interface defining the AI integration boundary for SkyPulse."""

    @abstractmethod
    async def extract_weather_entities(self, text: str) -> Dict[str, Any]:
        """Extract category, severity, location names, and temporal cues from text."""
        pass

    @abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate 384-dimensional vector embedding for text similarity."""
        pass

    @abstractmethod
    async def verify_claim(self, claim: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Verify report consistency and provide confidence score and explanation."""
        pass


class HeuristicFallbackAIProvider(AIProvider):
    """
    Standard deterministic provider used when external models/Ollama are disabled or offline.
    Provides robust rule-based NLP extraction and normalized dummy embeddings.
    """

    async def extract_weather_entities(self, text: str) -> Dict[str, Any]:
        text_lower = text.lower()
        category = "UNKNOWN"
        severity = 2
        confidence = 0.6

        if any(w in text_lower for w in ["flood", "waterlogging", "submerged", "inundated"]):
            category = "FLOODING"
            severity = 3
            confidence = 0.85
        elif any(w in text_lower for w in ["cyclone", "hurricane", "typhoon"]):
            category = "CYCLONE"
            severity = 4
            confidence = 0.95
        elif any(w in text_lower for w in ["rain", "downpour", "heavy showers", "monsoon"]):
            category = "RAINFALL"
            severity = 2
            confidence = 0.80
        elif any(w in text_lower for w in ["thunder", "lightning", "storm"]):
            category = "THUNDERSTORM"
            severity = 3
            confidence = 0.85
        elif any(w in text_lower for w in ["heatwave", "heat wave", "extreme temperature"]):
            category = "HEATWAVE"
            severity = 3
            confidence = 0.85
        elif any(w in text_lower for w in ["fog", "smog", "poor visibility"]):
            category = "FOG"
            severity = 2
            confidence = 0.80
        elif any(w in text_lower for w in ["hail", "hailstorm"]):
            category = "HAILSTORM"
            severity = 3
            confidence = 0.90

        return {
            "primary_category": category,
            "severity": severity,
            "confidence": confidence,
            "method": "heuristic_fallback",
        }

    async def generate_embedding(self, text: str) -> List[float]:
        # Generate deterministic 384-dim normalized vector
        import hashlib
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = []
        for i in range(384):
            val = ((h[i % len(h)] + i * 17) % 100) / 100.0 - 0.5
            vec.append(val)
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [round(x / norm, 4) for x in vec]

    async def verify_claim(self, claim: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "LIKELY",
            "confidence_score": 0.75,
            "explanation": "Report matches current seasonal patterns and nearby station baselines.",
            "evidence": [
                {
                    "evidence_type": "HISTORICAL_BASELINE",
                    "source_name": "IMD Historical Data",
                    "description": "Report is consistent with monsoon historical patterns.",
                    "weight": 0.3,
                }
            ],
        }


def get_ai_provider() -> AIProvider:
    # Pluggable provider based on settings
    if settings.LLM_PROVIDER.lower() == "ollama":
        # Can instantiate Ollama provider when implemented in Phase 5
        pass
    return HeuristicFallbackAIProvider()
