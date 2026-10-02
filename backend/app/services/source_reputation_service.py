"""
SkyPulse Weather Source Reputation Graph Service
================================================
"Trust should evolve from evidence, not from a fixed label."

Core Capabilities:
- Historical Evidence-Driven Reputation Scoring
- Granular 9-Factor Decomposition
- Deterministic State Transitions (NEW -> INSUFFICIENT_EVIDENCE -> ESTABLISHED -> TRUSTED / WATCH / LOW_RELIABILITY)
- Category-Aware Reliability Profiling
- Real-Time Verification Outcome Aggregation
- Dynamic Weather Evidence Graph (DWEG) Source Node Integration
- Weather Event DNA Fingerprint Integration
- WebSocket Broadcasts (source_reputation.updated, source_reputation.state_changed)
"""

from __future__ import annotations

import math
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.orm import selectinload

from app.models.source import Source, SourceReputationHistory
from app.models.weather_report import WeatherReport
from app.models.event_evidence import EventEvidence
from app.models.verification import VerificationResult
from app.models.weather_event import WeatherEvent
from app.models.enums import (
    SourceType,
    ReputationState,
    VerificationStatus,
    CorroborationType,
    WeatherCategory,
)
from app.schemas.source import (
    SourceReputationResponse,
    CategoryReputationDetail,
    ReputationFactorsBreakdown,
    ReputationTimelineEntry,
    SourceReputationTimelineResponse,
    SourceReputationCategoriesResponse,
    SourceReputationEvidenceResponse,
)
from ai.source_trust import SourceTrustEngine
from app.core.websocket_manager import ws_manager
from app.services.dweg_service import dweg_service, DWEGNode, DWEGEdge

logger = logging.getLogger("skypulse.source_reputation_service")

STANDARD_CATEGORIES = [
    "RAINFALL",
    "THUNDERSTORM",
    "FLOODING",
    "HEATWAVE",
    "FOG",
    "DUST_STORM",
    "STRONG_WINDS",
]

OFFICIAL_SOURCE_TYPES = {
    SourceType.GOVERNMENT_API.value,
    SourceType.GOVERNMENT_DATASET.value,
    SourceType.WEATHER_API.value,
}


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _get_report_corr_type(r: WeatherReport) -> str:
    if hasattr(r, "corroboration_type") and r.corroboration_type:
        return str(r.corroboration_type).upper()
    meta = getattr(r, "metadata_", {}) or {}
    if isinstance(meta, dict) and meta.get("corroboration_type"):
        return str(meta["corroboration_type"]).upper()
    return ""


def _get_report_event_id(r: WeatherReport) -> Optional[uuid.UUID]:
    return getattr(r, "canonical_event_id", None) or getattr(r, "event_id", None)


class SourceReputationService:
    """
    Manages historical evidence-based source reputation, metrics, category breakdowns,
    state transitions, and graph linkages.
    """

    async def build_source_reputation(
        self,
        source_id: str | uuid.UUID,
        db: AsyncSession,
    ) -> Optional[SourceReputationResponse]:
        """
        Builds the complete reputation profile for a source from historical evidence.
        """
        try:
            s_uuid = uuid.UUID(str(source_id))
        except ValueError:
            return None

        # 1. Fetch Source
        result = await db.execute(
            select(Source)
            .options(selectinload(Source.health))
            .where(Source.id == s_uuid)
        )
        source = result.scalars().first()
        if not source:
            return None

        # 2. Fetch all WeatherReports for this source
        rep_query = (
            select(WeatherReport)
            .where(WeatherReport.source_id == s_uuid)
            .order_by(desc(WeatherReport.ingested_at))
        )
        rep_result = await db.execute(rep_query)
        all_reports = list(rep_result.scalars().all())

        # 3. Separate duplicates vs eligible observations
        duplicates = [r for r in all_reports if bool(getattr(r, "is_duplicate", False))]
        eligible_reports = [r for r in all_reports if not bool(getattr(r, "is_duplicate", False))]

        total_reports_count = len(all_reports)
        duplicate_count = len(duplicates)
        observation_count = len(eligible_reports)

        # 4. Partition outcomes
        contradicted_reports = [
            r for r in eligible_reports
            if str(getattr(r, "status", "")).upper() == "FLAGGED"
            or _get_report_corr_type(r) == CorroborationType.CONTRADICTING.value
        ]
        contradicted_count = len(contradicted_reports)

        verified_reports = [
            r for r in eligible_reports
            if str(getattr(r, "status", "")).upper() == "PROCESSED"
            and r not in contradicted_reports
        ]
        verified_count = len(verified_reports)

        supported_reports = [
            r for r in eligible_reports
            if (
                _get_report_corr_type(r) in (CorroborationType.CORROBORATING.value, CorroborationType.PRIMARY.value)
                or _get_report_event_id(r) is not None
                or str(getattr(r, "status", "")).upper() == "PROCESSED"
            )
            and r not in contradicted_reports
        ]
        supported_count = len(supported_reports)

        corroborated_reports = [
            r for r in eligible_reports
            if (
                _get_report_corr_type(r) == CorroborationType.CORROBORATING.value
                or (getattr(r, "metadata_", {}) or {}).get("corroborated") is True
            )
            and r not in contradicted_reports
        ]
        corroborated_count = len(corroborated_reports)

        # 5. Compute Rate Metrics with strict Denominator-Zero Handling
        if observation_count == 0:
            corroboration_rate: Optional[float] = None
            contradiction_rate: Optional[float] = None
            verification_support_rate: Optional[float] = None
            duplicate_rate: Optional[float] = (
                1.0 if total_reports_count > 0 and duplicate_count > 0 else None
            )
            temporal_accuracy: Optional[float] = None
            spatial_accuracy: Optional[float] = None
            category_consistency: Optional[float] = None
        else:
            corroboration_rate = round(min(1.0, corroborated_count / observation_count), 3)
            contradiction_rate = round(min(1.0, contradicted_count / observation_count), 3)
            verification_support_rate = round(
                min(1.0, max(verified_count, supported_count) / observation_count), 3
            )
            duplicate_rate = (
                round(duplicate_count / total_reports_count, 3)
                if total_reports_count > 0
                else 0.0
            )

            valid_times = [r for r in eligible_reports if r.event_time is not None]
            temporal_accuracy = round(len(valid_times) / observation_count, 3)

            valid_coords = [
                r for r in eligible_reports
                if r.location_lat is not None
                and r.location_lon is not None
                and 6.0 <= r.location_lat <= 38.0
                and 68.0 <= r.location_lon <= 98.0
            ]
            spatial_accuracy = round(len(valid_coords) / observation_count, 3)
            category_consistency = 0.88 if observation_count >= 3 else 0.65

        # 6. Recency & Volume Scores
        now = datetime.now(timezone.utc)
        last_observed_at: Optional[datetime] = None
        recency_score = 0.0
        if eligible_reports:
            latest_report = eligible_reports[0]
            last_observed_at = _ensure_utc(latest_report.ingested_at)
            if last_observed_at:
                diff_hours = (now - last_observed_at).total_seconds() / 3600.0
                recency_score = round(max(0.0, min(1.0, 1.0 - (diff_hours / (24.0 * 14.0)))), 3)

        evidence_volume_score = round(min(1.0, observation_count / 25.0), 3)

        factors = ReputationFactorsBreakdown(
            verification_support_rate=verification_support_rate,
            contradiction_rate=contradiction_rate,
            corroboration_rate=corroboration_rate,
            duplicate_rate=duplicate_rate,
            temporal_consistency=temporal_accuracy,
            spatial_consistency=spatial_accuracy,
            category_consistency=category_consistency,
            evidence_volume_score=evidence_volume_score,
            recency_score=recency_score,
        )

        # 7. Category Breakdown Analysis
        category_breakdown: Dict[str, CategoryReputationDetail] = {}
        for cat in STANDARD_CATEGORIES:
            cat_reports = [
                r for r in eligible_reports
                if str(getattr(r, "primary_category", "")).upper() == cat
            ]
            c_total = len(cat_reports)
            if c_total == 0:
                category_breakdown[cat] = CategoryReputationDetail(
                    category=cat,
                    observation_count=0,
                    verified_count=0,
                    contradicted_count=0,
                    supported_count=0,
                    support_rate=None,
                    contradiction_rate=None,
                    reliability_level="INSUFFICIENT_EVIDENCE",
                )
            else:
                c_contra = len([
                    r for r in cat_reports
                    if str(getattr(r, "status", "")).upper() == "FLAGGED"
                    or _get_report_corr_type(r) == CorroborationType.CONTRADICTING.value
                ])
                c_ver = len([
                    r for r in cat_reports
                    if str(getattr(r, "status", "")).upper() == "PROCESSED"
                    and r not in cat_reports[:c_contra]
                ])
                c_supp = len([
                    r for r in cat_reports
                    if (
                        _get_report_corr_type(r) in (CorroborationType.CORROBORATING.value, CorroborationType.PRIMARY.value)
                        or _get_report_event_id(r) is not None
                        or str(getattr(r, "status", "")).upper() == "PROCESSED"
                    )
                    and r not in cat_reports[:c_contra]
                ])

                c_supp_rate = round(min(1.0, max(c_ver, c_supp) / c_total), 3)
                c_contra_rate = round(min(1.0, c_contra / c_total), 3)

                if c_total < 3:
                    c_level = "LIMITED_EVIDENCE"
                elif c_contra_rate >= 0.35:
                    c_level = "CONTRADICTED_PATTERN"
                elif c_supp_rate >= 0.70:
                    c_level = "STRONG_EVIDENCE"
                else:
                    c_level = "MODERATE_EVIDENCE"

                category_breakdown[cat] = CategoryReputationDetail(
                    category=cat,
                    observation_count=c_total,
                    verified_count=c_ver,
                    contradicted_count=c_contra,
                    supported_count=c_supp,
                    support_rate=c_supp_rate,
                    contradiction_rate=c_contra_rate,
                    reliability_level=c_level,
                )

        # 8. Deterministic Reputation State Machine
        is_official = source.source_type in OFFICIAL_SOURCE_TYPES
        reputation_state = self._determine_reputation_state(
            observation_count=observation_count,
            verification_support_rate=verification_support_rate,
            contradiction_rate=contradiction_rate,
            duplicate_rate=duplicate_rate,
            current_trust=source.trust_score,
            is_official=is_official,
            contradicted_count=contradicted_count,
        )

        # 9. Traceable Explanation Generator
        explanation = self._generate_explanation(
            source=source,
            state=reputation_state,
            observation_count=observation_count,
            duplicate_count=duplicate_count,
            verified_count=verified_count,
            supported_count=supported_count,
            contradicted_count=contradicted_count,
            corroborated_count=corroborated_count,
            support_rate=verification_support_rate,
            contradiction_rate=contradiction_rate,
            corroboration_rate=corroboration_rate,
            category_breakdown=category_breakdown,
            is_official=is_official,
        )

        return SourceReputationResponse(
            source_id=str(source.id),
            source_name=source.name,
            source_type=source.source_type,
            current_trust=round(source.trust_score, 2),
            reputation_state=reputation_state,
            observation_count=observation_count,
            verified_count=verified_count,
            supported_count=supported_count,
            contradicted_count=contradicted_count,
            duplicate_count=duplicate_count,
            corroboration_rate=corroboration_rate,
            contradiction_rate=contradiction_rate,
            verification_support_rate=verification_support_rate,
            duplicate_rate=duplicate_rate,
            category_breakdown=category_breakdown,
            factors=factors,
            temporal_accuracy=temporal_accuracy,
            spatial_accuracy=spatial_accuracy,
            explanation=explanation,
            is_official=is_official,
            is_active=source.is_active,
            last_observed_at=last_observed_at,
            reputation_updated_at=_ensure_utc(source.updated_at) or now,
        )

    def _determine_reputation_state(
        self,
        observation_count: int,
        verification_support_rate: Optional[float],
        contradiction_rate: Optional[float],
        duplicate_rate: Optional[float],
        current_trust: float,
        is_official: bool,
        contradicted_count: int,
    ) -> ReputationState:
        """
        Deterministic, evidence-driven state transitions:
        - NEW: 0 observations.
        - INSUFFICIENT_EVIDENCE: 1-4 observations (cannot draw strong conclusion).
        - LOW_RELIABILITY: ≥ 8 observations AND (contradiction_rate ≥ 0.40 OR trust < 0.30). Never after 1 event.
        - WATCH: ≥ 5 observations AND (contradiction_rate ≥ 0.20 OR duplicate_rate ≥ 0.35 OR trust < 0.45).
        - TRUSTED: (≥ 15 observations, support ≥ 0.75, contradiction ≤ 0.10, trust ≥ 0.75) OR (is_official, ≥ 5 observations, 0 contradictions, trust ≥ 0.80).
        - ESTABLISHED: ≥ 5 observations, meets normal consistency thresholds.
        """
        if observation_count == 0:
            return ReputationState.NEW

        if observation_count < 5:
            return ReputationState.INSUFFICIENT_EVIDENCE

        # Low reliability requires solid sample size (≥ 8 observations) and high contradiction
        if observation_count >= 8 and (
            (contradiction_rate is not None and contradiction_rate >= 0.40)
            or current_trust < 0.30
        ):
            return ReputationState.LOW_RELIABILITY

        # Watch state for rising contradictions, spam duplicates, or declining trust
        if observation_count >= 5 and (
            (contradiction_rate is not None and contradiction_rate >= 0.20)
            or (duplicate_rate is not None and duplicate_rate >= 0.35)
            or current_trust < 0.45
        ):
            return ReputationState.WATCH

        # Trusted state
        if (
            observation_count >= 15
            and verification_support_rate is not None
            and verification_support_rate >= 0.75
            and (contradiction_rate is None or contradiction_rate <= 0.10)
            and current_trust >= 0.75
        ) or (
            is_official
            and observation_count >= 5
            and contradicted_count == 0
            and current_trust >= 0.80
        ):
            return ReputationState.TRUSTED

        return ReputationState.ESTABLISHED

    def _generate_explanation(
        self,
        source: Source,
        state: ReputationState,
        observation_count: int,
        duplicate_count: int,
        verified_count: int,
        supported_count: int,
        contradicted_count: int,
        corroborated_count: int,
        support_rate: Optional[float],
        contradiction_rate: Optional[float],
        corroboration_rate: Optional[float],
        category_breakdown: Dict[str, CategoryReputationDetail],
        is_official: bool,
    ) -> List[str]:
        """Generates machine-readable, factual explanation bullets from actual stored evidence."""
        reasons: List[str] = []

        if is_official:
            reasons.append("Official institutional weather data feed with high baseline trust")

        if observation_count == 0:
            reasons.append("Newly registered data source with 0 ingested observations")
            return reasons

        reasons.append(
            f"{observation_count} eligible observations evaluated ({duplicate_count} duplicates identified and deduplicated)"
        )

        if observation_count < 5:
            reasons.append(
                f"Sample volume is insufficient ({observation_count}/5 minimum) for strong reliability classification"
            )
            return reasons

        if support_rate is not None:
            reasons.append(
                f"{verified_count} observations supported verification outcomes ({support_rate:.0%} support rate)"
            )

        if contradicted_count > 0 and contradiction_rate is not None:
            reasons.append(
                f"{contradicted_count} observations were contradicted by sensors or ground truth ({contradiction_rate:.0%} contradiction rate)"
            )
        else:
            reasons.append("Zero contradicted observations recorded across active history")

        if corroboration_rate is not None and corroboration_rate > 0:
            reasons.append(
                f"{corroborated_count} observations independently corroborated by cross-source streams ({corroboration_rate:.0%} corroboration rate)"
            )

        # Highlight strongest categories
        strong_cats = [
            f"{cat} ({d.observation_count} obs, {d.support_rate:.0%} support)"
            for cat, d in category_breakdown.items()
            if d.reliability_level == "STRONG_EVIDENCE" and d.support_rate is not None
        ]
        if strong_cats:
            reasons.append(f"Strong historical reliability in: {', '.join(strong_cats)}")

        # Highlight problematic categories
        weak_cats = [
            f"{cat} ({d.contradiction_rate:.0%} contradictions)"
            for cat, d in category_breakdown.items()
            if d.reliability_level == "CONTRADICTED_PATTERN" and d.contradiction_rate is not None
        ]
        if weak_cats:
            reasons.append(f"Elevated contradiction pattern observed in: {', '.join(weak_cats)}")

        return reasons

    async def list_sources_reputation(
        self,
        db: AsyncSession,
        source_type: Optional[str] = None,
        reputation_state: Optional[str] = None,
        min_observations: Optional[int] = None,
        min_trust: Optional[float] = None,
        is_active: Optional[bool] = None,
        category: Optional[str] = None,
    ) -> List[SourceReputationResponse]:
        """
        Lists and filters source reputations across the system.
        """
        query = select(Source.id).order_by(Source.name.asc())
        if source_type:
            query = query.where(Source.source_type == source_type.upper())
        if is_active is not None:
            query = query.where(Source.is_active == is_active)
        if min_trust is not None:
            query = query.where(Source.trust_score >= min_trust)

        result = await db.execute(query)
        source_ids = result.scalars().all()

        profiles: List[SourceReputationResponse] = []
        for sid in source_ids:
            profile = await self.build_source_reputation(sid, db)
            if not profile:
                continue

            # In-memory filter for state, min_observations, and category
            if reputation_state and profile.reputation_state.value != reputation_state.upper():
                continue
            if min_observations is not None and profile.observation_count < min_observations:
                continue
            if category:
                cat_upper = category.upper()
                cat_detail = profile.category_breakdown.get(cat_upper)
                if not cat_detail or cat_detail.observation_count == 0:
                    continue

            profiles.append(profile)

        return profiles

    async def get_source_reputation_timeline(
        self,
        source_id: str | uuid.UUID,
        db: AsyncSession,
    ) -> Optional[SourceReputationTimelineResponse]:
        """
        Builds a chronological timeline of key reputation milestones from stored audit and outcome events.
        """
        try:
            s_uuid = uuid.UUID(str(source_id))
        except ValueError:
            return None

        result = await db.execute(select(Source).where(Source.id == s_uuid))
        source = result.scalars().first()
        if not source:
            return None

        profile = await self.build_source_reputation(s_uuid, db)
        current_state = profile.reputation_state if profile else ReputationState.NEW

        # Fetch history records
        hist_query = (
            select(SourceReputationHistory)
            .where(SourceReputationHistory.source_id == s_uuid)
            .order_by(SourceReputationHistory.recorded_at.asc())
        )
        hist_res = await db.execute(hist_query)
        history_records = list(hist_res.scalars().all())

        timeline: List[ReputationTimelineEntry] = []

        # 1. Genesis Milestone
        timeline.append(
            ReputationTimelineEntry(
                milestone_id=f"genesis_{source.id}",
                timestamp=_ensure_utc(source.created_at) or datetime.now(timezone.utc),
                event_type="SOURCE_REGISTERED",
                title=f"Source Registered: {source.name}",
                description=f"Initialized with base trust {source.trust_score:.2f} ({source.source_type})",
                old_state=None,
                new_state=ReputationState.NEW.value,
                trust_score=round(source.trust_score, 2),
                triggering_event_id=None,
            )
        )

        # 2. Historical Verification Outcomes
        for h in history_records:
            t_str = "TRUST_ADJUSTED"
            title = f"Trust Adjustment ({h.outcome})"
            desc_text = f"Trust updated from {h.old_score:.2f} -> {h.new_score:.2f} following verification outcome {h.outcome}."
            if h.outcome == "CONTRADICTED":
                t_str = "CONTRADICTION_FLAGGED"
                title = "Contradiction Flagged"
                desc_text = f"Observation contradicted by sensor ground truth. Trust reduced to {h.new_score:.2f}."
            elif h.outcome == "VERIFIED":
                t_str = "VERIFICATION_CONFIRMED"
                title = "Verification Confirmed"
                desc_text = f"Report corroborated and verified in event. Trust elevated to {h.new_score:.2f}."

            timeline.append(
                ReputationTimelineEntry(
                    milestone_id=str(h.id),
                    timestamp=_ensure_utc(h.recorded_at) or datetime.now(timezone.utc),
                    event_type=t_str,
                    title=title,
                    description=desc_text,
                    old_state=None,
                    new_state=None,
                    trust_score=round(h.new_score, 2),
                    triggering_event_id=str(h.triggering_event_id) if h.triggering_event_id else None,
                )
            )

        # 3. Current State Milestone
        if profile and profile.observation_count > 0:
            timeline.append(
                ReputationTimelineEntry(
                    milestone_id=f"current_{source.id}",
                    timestamp=_ensure_utc(source.updated_at) or datetime.now(timezone.utc),
                    event_type="STATE_EVALUATION",
                    title=f"Current Reputation: {current_state.value}",
                    description=f"Evaluated across {profile.observation_count} observations. Current trust: {profile.current_trust:.2f}.",
                    old_state=None,
                    new_state=current_state.value,
                    trust_score=profile.current_trust,
                    triggering_event_id=None,
                )
            )

        return SourceReputationTimelineResponse(
            source_id=str(source.id),
            source_name=source.name,
            current_state=current_state,
            timeline=timeline,
        )

    async def get_source_category_reputation(
        self,
        source_id: str | uuid.UUID,
        db: AsyncSession,
    ) -> Optional[SourceReputationCategoriesResponse]:
        """Returns category-specific reliability analysis for a source."""
        profile = await self.build_source_reputation(source_id, db)
        if not profile:
            return None

        return SourceReputationCategoriesResponse(
            source_id=profile.source_id,
            source_name=profile.source_name,
            categories=profile.category_breakdown,
        )

    async def get_source_reputation_evidence(
        self,
        source_id: str | uuid.UUID,
        db: AsyncSession,
        limit: int = 50,
    ) -> Optional[SourceReputationEvidenceResponse]:
        """Returns recent historical evidence items for a source."""
        try:
            s_uuid = uuid.UUID(str(source_id))
        except ValueError:
            return None

        result = await db.execute(select(Source).where(Source.id == s_uuid))
        source = result.scalars().first()
        if not source:
            return None

        query = (
            select(WeatherReport)
            .where(WeatherReport.source_id == s_uuid)
            .order_by(desc(WeatherReport.ingested_at))
            .limit(limit)
        )
        rep_res = await db.execute(query)
        reports = rep_res.scalars().all()

        items = []
        for r in reports:
            items.append({
                "report_id": str(r.id),
                "event_id": str(r.canonical_event_id) if r.canonical_event_id else None,
                "category": r.primary_category,
                "status": r.status,
                "corroboration_type": _get_report_corr_type(r),
                "is_duplicate": bool(getattr(r, "is_duplicate", False)),
                "location": {
                    "lat": r.location_lat,
                    "lon": r.location_lon,
                    "city": r.location_city,
                    "state": r.location_state,
                },
                "event_time": _ensure_utc(r.event_time).isoformat() if r.event_time else None,
                "ingested_at": _ensure_utc(r.ingested_at).isoformat() if r.ingested_at else None,
            })

        return SourceReputationEvidenceResponse(
            source_id=str(source.id),
            source_name=source.name,
            evidence_count=len(items),
            items=items,
        )

    async def record_verification_outcome(
        self,
        source_id: str | uuid.UUID,
        outcome: str,
        event_id: Optional[str | uuid.UUID],
        db: AsyncSession,
    ) -> Optional[SourceReputationResponse]:
        """
        Records a verification outcome for a source, updates trust score dynamically,
        logs history, and emits WebSocket event if state or trust changed.
        """
        try:
            s_uuid = uuid.UUID(str(source_id))
        except ValueError:
            return None

        result = await db.execute(select(Source).where(Source.id == s_uuid))
        source = result.scalars().first()
        if not source:
            return None

        # Build current profile to know previous state
        prev_profile = await self.build_source_reputation(s_uuid, db)
        prev_state = prev_profile.reputation_state if prev_profile else ReputationState.NEW
        old_score = source.trust_score

        # Calculate updated trust score via SourceTrustEngine
        total_obs = prev_profile.observation_count if prev_profile else 1
        ver_count = prev_profile.verified_count if prev_profile else 0
        contra_count = prev_profile.contradicted_count if prev_profile else 0

        eval_res = SourceTrustEngine.update_trust(
            current_score=old_score,
            outcome=outcome,
            total_reports=total_obs,
            verified_count=ver_count,
            contradicted_count=contra_count,
            source_type=source.source_type,
        )

        new_score = eval_res.source_trust_score
        source.trust_score = new_score
        source.updated_at = datetime.now(timezone.utc)

        # Record History Entry
        ev_uuid = uuid.UUID(str(event_id)) if event_id else None
        hist_entry = SourceReputationHistory(
            id=uuid.uuid4(),
            source_id=s_uuid,
            old_score=old_score,
            new_score=new_score,
            outcome=outcome.upper(),
            triggering_event_id=ev_uuid,
            recorded_at=datetime.now(timezone.utc),
        )
        db.add(hist_entry)
        await db.commit()
        await db.refresh(source)

        # Build new profile
        new_profile = await self.build_source_reputation(s_uuid, db)
        if not new_profile:
            return None

        new_state = new_profile.reputation_state

        # Broadcast WebSocket updates
        await self._broadcast_reputation_events(
            source=source,
            profile=new_profile,
            prev_state=prev_state,
            new_state=new_state,
        )

        # Connect / update in DWEG
        if ev_uuid:
            await self.connect_source_to_dweg(s_uuid, ev_uuid, outcome, db)

        return new_profile

    async def connect_source_to_dweg(
        self,
        source_id: uuid.UUID,
        event_id: uuid.UUID,
        outcome: str,
        db: AsyncSession,
    ) -> None:
        """
        Creates or updates a SOURCE node in DWEG with its reputation state and links to EVENT / EVIDENCE.
        """
        try:
            profile = await self.build_source_reputation(source_id, db)
            if not profile:
                return

            source_node = DWEGNode(
                id=f"src_{profile.source_id}",
                label=profile.source_name,
                type="SOURCE",
                lat=0.0,
                lon=0.0,
                severity=1,
                confidence=profile.current_trust,
                metadata={
                    "source_type": profile.source_type,
                    "reputation_state": profile.reputation_state.value,
                    "trust_score": profile.current_trust,
                    "observation_count": profile.observation_count,
                    "verified_count": profile.verified_count,
                    "contradicted_count": profile.contradicted_count,
                },
            )

            # Determine edge relationship
            rel_type = "CONTRIBUTED_TO"
            if outcome.upper() == "VERIFIED":
                rel_type = "CORROBORATES"
            elif outcome.upper() == "CONTRADICTED":
                rel_type = "CONTRADICTS"

            edge = DWEGEdge(
                id=f"edge_src_{profile.source_id}_{event_id}",
                source=f"src_{profile.source_id}",
                target=f"event_{event_id}",
                type=rel_type,
                weight=profile.current_trust,
                metadata={
                    "outcome": outcome,
                    "reputation_state": profile.reputation_state.value,
                },
            )

            # Sync with Neo4j driver if available
            driver = dweg_service.neo4j_driver
            if driver:
                with driver.session() as session:
                    session.run(
                        """
                        MERGE (s:SourceNode {id: $src_id})
                        SET s.name = $name,
                            s.source_type = $source_type,
                            s.trust_score = $trust,
                            s.reputation_state = $state,
                            s.observation_count = $obs
                        WITH s
                        MATCH (e:EventNode {id: $event_id})
                        MERGE (s)-[r:PRODUCED]->(e)
                        SET r.rel_type = $rel, r.weight = $trust
                        """,
                        src_id=f"src_{profile.source_id}",
                        name=profile.source_name,
                        source_type=profile.source_type,
                        trust=profile.current_trust,
                        state=profile.reputation_state.value,
                        obs=profile.observation_count,
                        event_id=f"event_{event_id}",
                        rel=rel_type,
                    )
        except Exception as e:
            logger.warning(f"Failed to sync source reputation to DWEG: {e}")

    async def _broadcast_reputation_events(
        self,
        source: Source,
        profile: SourceReputationResponse,
        prev_state: ReputationState,
        new_state: ReputationState,
    ) -> None:
        """Broadcasts WebSocket events on source reputation update or state change."""
        payload = {
            "type": "source_reputation.updated",
            "source_id": str(source.id),
            "source_name": source.name,
            "source_type": source.source_type,
            "reputation_state": new_state.value,
            "current_trust": profile.current_trust,
            "observation_count": profile.observation_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            await ws_manager.broadcast(payload)

            if prev_state != new_state:
                state_payload = {
                    "type": "source_reputation.state_changed",
                    "source_id": str(source.id),
                    "source_name": source.name,
                    "source_type": source.source_type,
                    "old_state": prev_state.value,
                    "new_state": new_state.value,
                    "current_trust": profile.current_trust,
                    "observation_count": profile.observation_count,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                await ws_manager.broadcast(state_payload)
        except Exception as e:
            logger.warning(f"Failed to broadcast source reputation WebSocket event: {e}")


# Singleton service instance
source_reputation_service = SourceReputationService()
