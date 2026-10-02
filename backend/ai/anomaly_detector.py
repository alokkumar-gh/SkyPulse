"""
SkyPulse Multi-Factor Anomaly Detector
Detects spatial, temporal, volume, and content anomalies across weather reports.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from ai.base_provider import AnomalyResult, AIProvider
from ai.fallback_provider import FallbackAIProvider


class AnomalyDetector:
    """
    Detects unusual anomalies in weather reports:
    - Spatial anomalies: isolated extreme severity without local corroboration
    - Temporal anomalies: unseasonal meteorological events
    - Volume anomalies: abnormal burst from single source/location
    - Content anomalies: coordinated exact duplicate text across distinct accounts
    """

    def __init__(self, provider: Optional[AIProvider] = None):
        self.provider = provider or FallbackAIProvider()

    async def evaluate_report(
        self,
        category: str,
        severity: int,
        city: Optional[str] = None,
        district: Optional[str] = None,
        state: Optional[str] = None,
        event_time: Optional[datetime] = None,
        nearby_events_count: int = 0,
        recent_same_source_count: int = 1,
        is_exact_content_duplicate: bool = False,
    ) -> AnomalyResult:
        # Base anomaly evaluation
        result = await self.provider.detect_anomaly(
            category=category,
            severity=severity,
            city=city,
            district=district,
            state=state,
            event_time=event_time,
            nearby_events_count=nearby_events_count,
        )

        signals = list(result.signals)
        score = result.anomaly_score
        anomaly_type = result.anomaly_type

        # Check for Volume burst anomaly (e.g. > 15 reports from single source in 5 minutes)
        if recent_same_source_count > 10:
            signals.append(f"Volume burst: {recent_same_source_count} reports from single source in rapid succession")
            score = max(score, 0.85)
            anomaly_type = "VOLUME_BURST"

        # Check for Content duplication anomaly across distinct users
        if is_exact_content_duplicate and recent_same_source_count > 3:
            signals.append("Coordinated content anomaly: identical text broadcast across multiple accounts")
            score = max(score, 0.90)
            anomaly_type = "COORDINATED_DUPLICATE"

        is_anomalous = (score >= 0.50) or result.is_anomalous

        return AnomalyResult(
            is_anomalous=is_anomalous,
            anomaly_score=round(score, 2),
            z_score=result.z_score,
            anomaly_type=anomaly_type or ("ANOMALOUS" if is_anomalous else "NORMAL"),
            signals=signals,
            description=f"Anomaly: {', '.join(signals)}" if signals else "Consistent with normal conditions",
        )
