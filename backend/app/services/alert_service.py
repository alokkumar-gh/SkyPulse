"""
Alert Engine — SkyPulse Phase 6
================================
Generates, deduplicates, prioritizes, and persists weather alerts
derived from AI-processed weather events.

Rules:
- HIGH_SEVERITY  →  severity >= 3
- HIGH_CONFIDENCE → confidence >= 0.85
- VERIFIED_EVENT → verification_status = VERIFIED + severity >= 2
- RAPID_CLUSTER  → evidence_count jumped by >= 3 in one update
- ANOMALY_DETECTED → event is_anomalous

Priority mapping (deterministic):
  severity 4 OR (CRITICAL category + severity 3)  →  CRITICAL
  severity 3                                        →  HIGH
  severity 2 + confidence > 0.7                    →  MEDIUM
  severity 2                                        →  LOW
  everything else                                  →  INFO

Alert deduplication:
  fingerprint = SHA-256(event_id + alert_type + location_key + time_window_hour)
  Same fingerprint within cooldown window → update existing alert, no new row.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert

logger = logging.getLogger("skypulse.alert_engine")


# ---------------------------------------------------------------------------
# Priority mapping
# ---------------------------------------------------------------------------
CRITICAL_CATEGORIES = {"CYCLONE", "FLOODING", "HEATWAVE"}
ALERT_COOLDOWN_MINUTES = 30  # same fingerprint cannot re-alert within this window


def compute_priority(
    severity: int,
    confidence: float,
    category: str,
    alert_type: str,
) -> str:
    if alert_type == "ANOMALY_DETECTED":
        return "HIGH"
    if severity >= 4 or (severity >= 3 and category in CRITICAL_CATEGORIES):
        return "CRITICAL"
    if severity >= 3:
        return "HIGH"
    if severity >= 2 and confidence >= 0.70:
        return "MEDIUM"
    if severity >= 2:
        return "LOW"
    return "INFO"


def _time_window_key() -> str:
    """Returns the current UTC hour string for fingerprinting."""
    now = datetime.now(timezone.utc)
    return f"{now.year}-{now.month:02d}-{now.day:02d}-{now.hour:02d}"


def compute_fingerprint(
    event_id: str,
    alert_type: str,
    location_key: str,
) -> str:
    raw = f"{event_id}:{alert_type}:{location_key}:{_time_window_key()}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Alert message templates
# ---------------------------------------------------------------------------
_TITLES: Dict[str, str] = {
    "HIGH_SEVERITY": "⚠️ High-Severity Weather Alert",
    "HIGH_CONFIDENCE": "📡 High-Confidence Weather Report",
    "VERIFIED_EVENT": "✅ Verified Weather Event",
    "RAPID_CLUSTER_GROWTH": "📈 Rapidly Growing Weather Event",
    "FLOODING_NEAR_AREA": "🌊 Flooding Alert",
    "EXTREME_HEAT": "🔥 Extreme Heat Warning",
    "STRONG_WINDS": "💨 Strong Winds Advisory",
    "STORM_PROPAGATION": "🌀 Storm Propagation Detected",
    "ANOMALY_DETECTED": "🔬 Anomalous Weather Activity",
    "SYSTEM": "🔧 System Notification",
}

_TEMPLATES: Dict[str, str] = {
    "HIGH_SEVERITY": "{category} (severity {severity}/4) reported in {location}. Confidence: {confidence_pct}%.",
    "HIGH_CONFIDENCE": "High-confidence {category} report in {location}. Confidence: {confidence_pct}%.",
    "VERIFIED_EVENT": "Verified {category} event in {location}. Severity {severity}/4.",
    "RAPID_CLUSTER_GROWTH": "{category} in {location} now has {evidence_count} corroborating reports.",
    "FLOODING_NEAR_AREA": "Flooding reported in {location}. Severity {severity}/4. Take precautions.",
    "EXTREME_HEAT": "Extreme heat event in {location}. Severity {severity}/4. Stay hydrated.",
    "STRONG_WINDS": "Strong winds reported in {location}. Severity {severity}/4.",
    "STORM_PROPAGATION": "Storm propagation detected from {location}. Monitor downstream areas.",
    "ANOMALY_DETECTED": "Anomalous weather activity detected in {location}. Severity {severity}/4.",
    "SYSTEM": "{message}",
}


def _fmt(template: str, **kwargs: Any) -> str:
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def _location_label(data: Dict[str, Any]) -> str:
    parts = [data.get("primary_city"), data.get("primary_district"), data.get("primary_state")]
    return ", ".join(p for p in parts if p) or "Unknown location"


# ---------------------------------------------------------------------------
# Alert Service
# ---------------------------------------------------------------------------
class AlertEngine:
    """
    Generates alerts from processed weather events.
    Handles deduplication, priority, and persistence.
    Does NOT send WebSocket messages directly — that is the caller's responsibility.
    """

    async def evaluate_event(
        self,
        session: AsyncSession,
        event_data: Dict[str, Any],
    ) -> Optional[Alert]:
        """
        Evaluate a processed event and create/update alert if warranted.
        Returns the Alert row (new or updated), or None if no alert needed.
        """
        event_id = str(event_data.get("event_id", ""))
        category = event_data.get("category", "UNKNOWN")
        severity = int(event_data.get("severity", 1))
        confidence = float(event_data.get("confidence_score", 0.0))
        verification_status = event_data.get("verification_status", "UNVERIFIED")
        evidence_count = int(event_data.get("evidence_count", 1))
        is_anomalous = event_data.get("is_anomalous", False)
        location_key = f"{event_data.get('primary_state', '')}:{event_data.get('primary_city', '')}"
        location_label = _location_label(event_data)

        # Determine which alert type to raise (highest priority wins)
        alert_type = self._determine_alert_type(
            category=category,
            severity=severity,
            confidence=confidence,
            verification_status=verification_status,
            evidence_count=evidence_count,
            is_anomalous=is_anomalous,
        )

        if alert_type is None:
            return None  # No alert needed

        priority = compute_priority(severity, confidence, category, alert_type)
        fingerprint = compute_fingerprint(event_id, alert_type, location_key)

        # Check deduplication — existing alert with same fingerprint?
        existing = await session.execute(
            select(Alert).where(Alert.fingerprint == fingerprint)
        )
        existing_alert = existing.scalars().first()

        if existing_alert:
            if existing_alert.status in ("CANCELLED", "EXPIRED"):
                pass  # Allow re-creation for expired alerts
            else:
                # Update existing alert's priority and status, don't spam
                logger.debug("Alert dedup: fingerprint=%s exists, updating.", fingerprint)
                await session.execute(
                    update(Alert)
                    .where(Alert.id == existing_alert.id)
                    .values(
                        priority=priority,
                        severity=severity,
                        confidence=confidence,
                    )
                )
                await session.commit()
                return existing_alert

        confidence_pct = int(confidence * 100)
        title = _TITLES.get(alert_type, "Weather Alert")
        message = _fmt(
            _TEMPLATES.get(alert_type, "{category} in {location}"),
            category=category,
            severity=severity,
            confidence_pct=confidence_pct,
            location=location_label,
            evidence_count=evidence_count,
            message=event_data.get("message", ""),
        )

        alert = Alert(
            event_id=uuid.UUID(event_id) if event_id else None,
            alert_type=alert_type,
            priority=priority,
            status="CREATED",
            title=title,
            message=message,
            location_city=event_data.get("primary_city"),
            location_district=event_data.get("primary_district"),
            location_state=event_data.get("primary_state"),
            location_lat=event_data.get("centroid_lat"),
            location_lon=event_data.get("centroid_lon"),
            severity=severity,
            confidence=confidence,
            fingerprint=fingerprint,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
            extra_data={
                "category": category,
                "evidence_count": evidence_count,
                "verification_status": verification_status,
                "is_anomalous": is_anomalous,
            },
        )
        session.add(alert)
        await session.commit()
        await session.refresh(alert)
        logger.info("Alert created: %s type=%s priority=%s", alert.id, alert_type, priority)
        return alert

    def _determine_alert_type(
        self,
        *,
        category: str,
        severity: int,
        confidence: float,
        verification_status: str,
        evidence_count: int,
        is_anomalous: bool,
    ) -> Optional[str]:
        if is_anomalous:
            return "ANOMALY_DETECTED"
        if severity >= 3 and category == "FLOODING":
            return "FLOODING_NEAR_AREA"
        if severity >= 3 and category == "HEATWAVE":
            return "EXTREME_HEAT"
        if severity >= 3 and category == "STRONG_WINDS":
            return "STRONG_WINDS"
        if severity >= 3:
            return "HIGH_SEVERITY"
        if verification_status == "VERIFIED" and severity >= 2:
            return "VERIFIED_EVENT"
        if confidence >= 0.85 and severity >= 2:
            return "HIGH_CONFIDENCE"
        if evidence_count >= 5:
            return "RAPID_CLUSTER_GROWTH"
        return None  # Below threshold

    async def acknowledge_alert(
        self,
        session: AsyncSession,
        alert_id: uuid.UUID,
    ) -> Optional[Alert]:
        result = await session.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalars().first()
        if not alert:
            return None
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(alert)
        return alert

    async def expire_old_alerts(self, session: AsyncSession) -> int:
        """Mark past-expiry alerts as EXPIRED. Returns count updated."""
        now = datetime.now(timezone.utc)
        result = await session.execute(
            update(Alert)
            .where(Alert.expires_at < now, Alert.status.in_(["CREATED", "DELIVERED"]))
            .values(status="EXPIRED")
        )
        await session.commit()
        return result.rowcount


alert_engine = AlertEngine()
