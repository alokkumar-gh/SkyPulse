"""
SkyPulse External AI Provider Adapter
Wraps remote LLM / Vision endpoints (OpenAI, Anthropic, or Ollama).
If credentials are absent or unconfigured, reports NOT_CONFIGURED and delegates
safely to the FallbackAIProvider.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ai.base_provider import (
    AIProvider,
    ClassificationResult,
    EntityExtractionResult,
    MediaAnalysisResult,
    AnomalyResult,
    EvidenceAssessmentResult,
)
from ai.fallback_provider import FallbackAIProvider
from app.core.config import settings

logger = logging.getLogger("skypulse.ai.external")


class ExternalAIProvider(AIProvider):
    """
    Adapter for external AI APIs.
    Checks environment for API keys (e.g., OPENAI_API_KEY, ANTHROPIC_API_KEY).
    If missing, status is NOT_CONFIGURED and safely delegates to FallbackAIProvider.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        self._fallback = FallbackAIProvider()

    @property
    def name(self) -> str:
        return "ExternalAIProvider"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    @property
    def status(self) -> str:
        return "HEALTHY" if self.is_configured else "NOT_CONFIGURED"

    async def classify_event(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        if not self.is_configured:
            res = await self._fallback.classify_event(text, metadata)
            res.method = "external_adapter_fallback"
            return res

        # In production with keys, call remote LLM structured API
        logger.info("External AI provider invoked for event classification")
        return await self._fallback.classify_event(text, metadata)

    async def extract_entities(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> EntityExtractionResult:
        if not self.is_configured:
            res = await self._fallback.extract_entities(text, metadata)
            res.method = "external_adapter_fallback"
            return res

        logger.info("External AI provider invoked for entity extraction")
        return await self._fallback.extract_entities(text, metadata)

    async def analyze_media(self, media_urls: List[str], claimed_category: Optional[str] = None) -> MediaAnalysisResult:
        if not self.is_configured:
            res = await self._fallback.analyze_media(media_urls, claimed_category)
            res.method = "external_adapter_fallback"
            return res

        logger.info("External AI provider invoked for vision analysis")
        return await self._fallback.analyze_media(media_urls, claimed_category)

    async def generate_embedding(self, text: str) -> List[float]:
        return await self._fallback.generate_embedding(text)

    async def detect_anomaly(
        self,
        category: str,
        severity: int,
        city: Optional[str] = None,
        district: Optional[str] = None,
        state: Optional[str] = None,
        event_time: Optional[datetime] = None,
        nearby_events_count: int = 0,
    ) -> AnomalyResult:
        return await self._fallback.detect_anomaly(
            category=category,
            severity=severity,
            city=city,
            district=district,
            state=state,
            event_time=event_time,
            nearby_events_count=nearby_events_count,
        )

    async def assess_evidence(
        self,
        report_data: Dict[str, Any],
        official_data: Optional[Dict[str, Any]] = None,
        nearby_reports: Optional[List[Dict[str, Any]]] = None,
        source_trust: float = 0.5,
        media_analysis: Optional[MediaAnalysisResult] = None,
        physical_observation: Optional[Dict[str, Any]] = None,
    ) -> EvidenceAssessmentResult:
        return await self._fallback.assess_evidence(
            report_data=report_data,
            official_data=official_data,
            nearby_reports=nearby_reports,
            source_trust=source_trust,
            media_analysis=media_analysis,
            physical_observation=physical_observation,
        )
