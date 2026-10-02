"""
SkyPulse NLP Extractor Orchestrator
Extracts structured meteorological attributes, spatial mentions, and temporal expressions.
"""

from typing import Dict, Any, Optional
from ai.base_provider import EntityExtractionResult, AIProvider
from ai.fallback_provider import FallbackAIProvider
from ai.external_provider import ExternalAIProvider
from ai.groq_provider import GroqProvider, groq_provider


class NLPExtractor:
    """
    Extracts structured entities, metrics, and impact phrases from text.
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

    async def extract(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> EntityExtractionResult:
        return await self.provider.extract_entities(text, metadata)
