"""
SkyPulse Dynamic Source Trust Engine
Calculates dynamic source reputation and trust scores based on historical verification outcomes,
source types, and spatial-temporal consistency.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


BASE_TRUST_SCORES = {
    "GOVERNMENT_API": 0.88,
    "GOVERNMENT_DATASET": 0.85,
    "WEATHER_API": 0.82,
    "RSS_FEED": 0.70,
    "PUBLIC_DATASET": 0.75,
    "PUBLIC_JSON": 0.70,
    "PUBLIC_WEB": 0.60,
    "SOCIAL_API": 0.60,
    "SOCIAL_FEED": 0.50,
    "CITIZEN": 0.55,
    "DEMO": 0.50,
    "ANONYMOUS": 0.40,
}

OUTCOME_DELTAS = {
    "VERIFIED": 0.05,
    "LIKELY": 0.02,
    "UNVERIFIED": 0.00,
    "CONTRADICTED": -0.10,
    "REQUIRES_REVIEW": -0.03,
}


class SourceTrustEvaluation(BaseModel):
    source_id: str
    source_trust_score: float = Field(ge=0.1, le=0.99)
    trust_level: str  # HIGH, MODERATE, LOW, UNPROVEN
    total_reports: int = 0
    verified_reports: int = 0
    contradicted_reports: int = 0
    reasons: List[str] = Field(default_factory=list)


class SourceTrustEngine:
    """
    Evaluates source trust dynamically.
    Combines initial source credentials with historical accuracy and moving average adjustments.
    """

    @staticmethod
    def calculate_initial_trust(source_type: str, is_official: bool = False) -> float:
        base = BASE_TRUST_SCORES.get(source_type.upper(), 0.50)
        if is_official and base < 0.85:
            base = 0.85
        return round(base, 2)

    @staticmethod
    def update_trust(
        current_score: float,
        outcome: str,
        total_reports: int = 1,
        verified_count: int = 0,
        contradicted_count: int = 0,
        source_type: str = "CITIZEN",
    ) -> SourceTrustEvaluation:
        """
        Dynamically adjusts trust score with weighted learning rate.
        Never permanently zeroes a source on a single report. Floor: 0.10, Ceiling: 0.99.
        """
        outcome_upper = outcome.upper()
        delta = OUTCOME_DELTAS.get(outcome_upper, 0.0)

        # Learning rate decays slightly as report volume grows to stabilize established sources
        lr = max(0.05, 0.20 / (1.0 + 0.05 * total_reports))
        new_score = current_score + (delta * lr * 5.0)
        clamped_score = max(0.10, min(0.99, new_score))

        reasons = []
        if source_type in ("GOVERNMENT_API", "GOVERNMENT_DATASET", "WEATHER_API"):
            reasons.append("Official/authorized weather data feed")

        if outcome_upper == "VERIFIED":
            reasons.append("Report successfully verified with multi-source corroboration")
        elif outcome_upper == "CONTRADICTED":
            reasons.append("Report contradicted by official sensors or majority ground truth")

        if total_reports >= 10:
            accuracy_rate = (verified_count / total_reports) if total_reports > 0 else 0.5
            reasons.append(f"Historical verification rate: {accuracy_rate:.0%}")

        # Trust level categorization
        if clamped_score >= 0.75:
            trust_level = "HIGH"
        elif clamped_score >= 0.50:
            trust_level = "MODERATE"
        elif clamped_score >= 0.30:
            trust_level = "LOW"
        else:
            trust_level = "UNPROVEN"

        return SourceTrustEvaluation(
            source_id="",
            source_trust_score=round(clamped_score, 2),
            trust_level=trust_level,
            total_reports=total_reports,
            verified_reports=verified_count,
            contradicted_reports=contradicted_count,
            reasons=reasons,
        )
