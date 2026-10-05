"""
SkyPulse Evidence-Based Verification Engine
Synthesizes multi-source evidence: citizen reports, official bulletins, nearby sensors,
source trust, and media signals into an explainable verification verdict.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from ai.base_provider import EvidenceAssessmentResult, MediaAnalysisResult, AIProvider
from ai.fallback_provider import FallbackAIProvider


class VerificationVerdict(BaseModel):
    verification_status: str  # VERIFIED, LIKELY, UNVERIFIED, CONTRADICTED, REQUIRES_REVIEW, INSUFFICIENT_EVIDENCE
    verification_confidence: float = Field(ge=0.0, le=1.0)
    evidence_count: int
    signal_scores: Dict[str, float] = Field(default_factory=dict)
    evidence_summary: List[Dict[str, Any]] = Field(default_factory=list)
    explanation: str


class VerificationEngine:
    """
    Evidence-based verification engine for SkyPulse.
    """

    def __init__(self, provider: Optional[AIProvider] = None):
        self.provider = provider or FallbackAIProvider()

    async def verify_report(
        self,
        report_data: Dict[str, Any],
        official_data: Optional[Dict[str, Any]] = None,
        nearby_reports: Optional[List[Dict[str, Any]]] = None,
        source_trust: float = 0.5,
        media_analysis: Optional[MediaAnalysisResult] = None,
        physical_observation: Optional[Dict[str, Any]] = None,
    ) -> VerificationVerdict:
        assessment: EvidenceAssessmentResult = await self.provider.assess_evidence(
            report_data=report_data,
            official_data=official_data,
            nearby_reports=nearby_reports,
            source_trust=source_trust,
            media_analysis=media_analysis,
            physical_observation=physical_observation,
        )

        evidence_count = 1  # Base report
        if official_data:
            evidence_count += 1
        if nearby_reports:
            evidence_count += len(nearby_reports)
        if media_analysis and media_analysis.has_media:
            evidence_count += 1

        status = assessment.verification_status
        if evidence_count == 1 and status == "UNVERIFIED":
            status = "INSUFFICIENT_EVIDENCE"

        return VerificationVerdict(
            verification_status=status,
            verification_confidence=assessment.verification_confidence,
            evidence_count=evidence_count,
            signal_scores=assessment.signal_scores,
            evidence_summary=assessment.evidence_summary,
            explanation=assessment.explanation,
        )
