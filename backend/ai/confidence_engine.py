"""
SkyPulse Transparent Confidence Engine
Calculates normalized multi-factor confidence scores for weather reports and canonical events.
Maintains granular component scores for full analyst auditability and explainability.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class ConfidenceComponents(BaseModel):
    classification: float = Field(ge=0.0, le=1.0)
    extraction: float = Field(ge=0.0, le=1.0)
    source_trust: float = Field(ge=0.0, le=1.0)
    corroboration: float = Field(ge=0.0, le=1.0)
    spatial_consistency: float = Field(ge=0.0, le=1.0)
    temporal_consistency: float = Field(ge=0.0, le=1.0)
    media: float = Field(ge=0.0, le=1.0)
    contradiction_penalty: float = Field(ge=0.0, le=1.0)


class ConfidenceEvaluation(BaseModel):
    final_confidence: float = Field(ge=0.0, le=1.0)
    components: ConfidenceComponents
    explanation: str


class ConfidenceEngine:
    """
    Computes explainable, normalized confidence scores for reports and canonical events.
    Weights:
      Classification: 0.20
      Extraction:     0.10
      Source Trust:   0.20
      Corroboration:  0.20
      Spatial:        0.10
      Temporal:       0.10
      Media:          0.10
    """

    @classmethod
    def calculate_report_confidence(
        cls,
        classification_conf: float = 0.5,
        extraction_conf: float = 0.5,
        source_trust: float = 0.5,
        corroboration_score: float = 0.0,
        spatial_consistency: float = 0.8,
        temporal_consistency: float = 0.85,
        media_conf: Optional[float] = None,
        has_contradictions: bool = False,
    ) -> ConfidenceEvaluation:
        # Default media to neutral if no media attached
        media_val = 0.5 if media_conf is None else media_conf

        penalty = 0.35 if has_contradictions else 0.0

        raw_score = (
            0.20 * classification_conf
            + 0.10 * extraction_conf
            + 0.20 * source_trust
            + 0.20 * corroboration_score
            + 0.10 * spatial_consistency
            + 0.10 * temporal_consistency
            + 0.10 * media_val
            - penalty
        )

        final_conf = max(0.05, min(0.99, raw_score))

        components = ConfidenceComponents(
            classification=round(classification_conf, 2),
            extraction=round(extraction_conf, 2),
            source_trust=round(source_trust, 2),
            corroboration=round(corroboration_score, 2),
            spatial_consistency=round(spatial_consistency, 2),
            temporal_consistency=round(temporal_consistency, 2),
            media=round(media_val, 2),
            contradiction_penalty=round(penalty, 2),
        )

        explanation = (
            f"Confidence: {final_conf:.0%}. "
            f"Classifier ({classification_conf:.0%}), Trust ({source_trust:.0%}), "
            f"Corroboration ({corroboration_score:.0%})"
            + (f", Contradiction Penalty applied (-{penalty:.0%})" if has_contradictions else "")
        )

        return ConfidenceEvaluation(
            final_confidence=round(final_conf, 2),
            components=components,
            explanation=explanation,
        )
