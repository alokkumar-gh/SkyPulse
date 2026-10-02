"""
SkyPulse AI Intelligence Package
"""

from ai.base_provider import (
    AIProvider,
    ClassificationResult,
    EntityExtractionResult,
    MediaAnalysisResult,
    AnomalyResult,
    EvidenceAssessmentResult,
)
from ai.fallback_provider import FallbackAIProvider
from ai.external_provider import ExternalAIProvider
from ai.groq_provider import GroqProvider, groq_provider
from ai.event_classifier import EventClassifier
from ai.nlp_extractor import NLPExtractor
from ai.image_analyzer import ImageAnalyzer
from ai.deduplicator import DeduplicationEngine, DuplicateEvaluation
from ai.source_trust import SourceTrustEngine, SourceTrustEvaluation
from ai.verification_engine import VerificationEngine, VerificationVerdict
from ai.confidence_engine import ConfidenceEngine, ConfidenceEvaluation
from ai.anomaly_detector import AnomalyDetector
from ai.dweg_service import DWEGService, dweg_service
from ai.opensearch_indexer import OpenSearchIndexer, opensearch_indexer


def get_active_ai_provider() -> AIProvider:
    """
    Returns the configured primary AI provider (Groq if configured, else Fallback).
    """
    from app.core.config import settings
    provider_choice = getattr(settings, "AI_PROVIDER", "auto").lower()
    if provider_choice == "groq" or (provider_choice == "auto" and groq_provider.is_configured):
        return groq_provider
    elif provider_choice == "openai" and ExternalAIProvider().is_configured:
        return ExternalAIProvider()
    return FallbackAIProvider()


__all__ = [
    "AIProvider",
    "ClassificationResult",
    "EntityExtractionResult",
    "MediaAnalysisResult",
    "AnomalyResult",
    "EvidenceAssessmentResult",
    "FallbackAIProvider",
    "ExternalAIProvider",
    "GroqProvider",
    "groq_provider",
    "get_active_ai_provider",
    "EventClassifier",
    "NLPExtractor",
    "ImageAnalyzer",
    "DeduplicationEngine",
    "DuplicateEvaluation",
    "SourceTrustEngine",
    "SourceTrustEvaluation",
    "VerificationEngine",
    "VerificationVerdict",
    "ConfidenceEngine",
    "ConfidenceEvaluation",
    "AnomalyDetector",
    "DWEGService",
    "dweg_service",
    "OpenSearchIndexer",
    "opensearch_indexer",
]

