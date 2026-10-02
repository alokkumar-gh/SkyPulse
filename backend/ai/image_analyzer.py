"""
SkyPulse Media and Image Intelligence Analyzer
Analyzes media items attached to weather reports, computing perceptual hashes
and identifying visual weather indicators.
"""

from typing import List, Optional
from ai.base_provider import MediaAnalysisResult, AIProvider
from ai.fallback_provider import FallbackAIProvider
from ai.external_provider import ExternalAIProvider
from ai.groq_provider import GroqProvider, groq_provider


class ImageAnalyzer:
    """
    Performs visual weather signal analysis and perceptual hashing on media items.
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

    async def analyze(self, media_urls: List[str], claimed_category: Optional[str] = None) -> MediaAnalysisResult:
        return await self.provider.analyze_media(media_urls, claimed_category)
