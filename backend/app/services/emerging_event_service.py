"""
SkyPulse Emerging Weather Event Detection Service
=================================================
Identifies early convergence of weak multi-source weather signals before
normal event lifecycle reaches a mature canonical state.

Evaluates:
1. Spatial Convergence (Density, Centroid, Bounded Radius)
2. Temporal Acceleration (Signal velocity in current vs previous time window)
3. Source Diversity (Independent corroboration: IMD, Gov, Citizen, Sensor, Radar, etc.)
4. Category-Specific Meteorological Consistency
5. Meteorological Sensor / Baseline Support
6. Anomaly Intensity
7. Geographical Corridor Continuity
8. Dynamic Weather Evidence Graph (DWEG) Connectivity
9. Contradiction Penalty
10. Evidence Freshness Decay

Deterministic Emergence States:
SIGNAL -> DEVELOPING -> EMERGING -> CONFIRMED -> DISSIPATING -> EXPIRED
"""

from __future__ import annotations

import math
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.orm import selectinload

from app.models.weather_report import WeatherReport
from app.models.weather_event import WeatherEvent
from app.models.event_evidence import EventEvidence
from app.models.source import Source
from app.models.enums import (
    EmergenceState,
    WeatherCategory,
    EventSeverity,
    VerificationStatus,
    SourceType,
)
from app.schemas.emerging import (
    EmergenceFactorBreakdown,
    EmergingSignalItem,
    EmergingTimelineMilestone,
    EmergingEventResponse,
    EmergingEventListResponse,
    EmergingEventSignalsResponse,
    EmergingEventTimelineResponse,
    EmergingEventEvidenceResponse,
)
from app.services.dweg_service import (
    haversine_distance_km,
    dweg_service,
)
from ai.confidence_engine import ConfidenceEngine
from app.core.websocket_manager import ws_manager

logger = logging.getLogger("skypulse.emerging_event_service")


def _ensure_utc(dt: Optional[datetime]) -> datetime:
    """Ensures datetime is timezone-aware UTC."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _standardize_source_type(st: Optional[str], sn: Optional[str] = None) -> str:
    """Standardizes source type into distinct independent evidence buckets."""
    s_type = (st or "").upper()
    s_name = (sn or "").upper()

    if "IMD" in s_type or "IMD" in s_name:
        return "IMD"
    if "ERA5" in s_type or "CDS" in s_type or "ECMWF" in s_name or "REANALYSIS" in s_type:
        return "ERA5"
    if "GOV" in s_type or "DATA_GOV" in s_type or "NDMA" in s_name or "CWC" in s_name:
        return "GOVERNMENT"
    if "CITIZEN" in s_type or "PUBLIC" in s_type or "USER" in s_type:
        return "CITIZEN"
    if "AWS" in s_type or "AUTOMATIC_WEATHER" in s_type or "SENSOR" in s_type or "IOT" in s_type:
        return "WEATHER_STATION"
    if "RADAR" in s_type or "DOPPLER" in s_type:
        return "RADAR"
    if "SATELLITE" in s_type or "INSAT" in s_type:
        return "SATELLITE"
    if "SOCIAL" in s_type or "TWITTER" in s_type or "X" in s_type:
        return "SOCIAL"
    return "WEATHER_API"


# Category Compatibility Map for Meteorological Synergy
CATEGORY_SYNERGIES: Dict[str, Set[str]] = {
    "RAINFALL": {"RAINFALL", "FLOODING", "THUNDERSTORM"},
    "FLOODING": {"FLOODING", "RAINFALL", "CYCLONE"},
    "THUNDERSTORM": {"THUNDERSTORM", "STRONG_WINDS", "HAILSTORM", "RAINFALL"},
    "STRONG_WINDS": {"STRONG_WINDS", "THUNDERSTORM", "DUST_STORM", "CYCLONE"},
    "HEATWAVE": {"HEATWAVE", "SMOG"},
    "FOG": {"FOG", "SMOG"},
    "DUST_STORM": {"DUST_STORM", "STRONG_WINDS"},
    "CYCLONE": {"CYCLONE", "STRONG_WINDS", "RAINFALL", "FLOODING"},
    "HAILSTORM": {"HAILSTORM", "THUNDERSTORM", "RAINFALL"},
    "SNOWFALL": {"SNOWFALL", "FOG"},
    "SMOG": {"SMOG", "FOG", "HEATWAVE"},
}


class EmergingEventService:
    """
    Core engine for identifying, scoring, clustering, tracking, and broadcasting
    Emerging Weather Events across India.
    """

    def __init__(self, confidence_engine: Optional[ConfidenceEngine] = None):
        self.confidence_engine = confidence_engine or ConfidenceEngine()

    async def detect_emerging_events(
        self,
        db: AsyncSession,
        lookback_minutes: int = 120,
        cluster_radius_km: float = 65.0,
        category: Optional[str] = None,
        state: Optional[str] = None,
        min_emergence_score: Optional[float] = None,
        min_confidence: Optional[float] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[EmergingEventResponse]:
        """
        Scans recent ingestion signals, groups compatible observations,
        evaluates spatiotemporal emergence factors, and returns active emerging events.
        """
        now = datetime.now(timezone.utc)
        time_to = _ensure_utc(end_time) if end_time else now
        time_from = _ensure_utc(start_time) if start_time else (time_to - timedelta(minutes=lookback_minutes))

        # 1. Fetch non-duplicate recent reports in time window
        query = (
            select(WeatherReport)
            .options(selectinload(WeatherReport.source))
            .where(
                and_(
                    WeatherReport.ingested_at >= time_from,
                    WeatherReport.ingested_at <= time_to,
                    WeatherReport.location_lat.isnot(None),
                    WeatherReport.location_lon.isnot(None),
                )
            )
            .order_by(desc(WeatherReport.ingested_at))
        )

        if category:
            cat_upper = category.upper()
            query = query.where(WeatherReport.primary_category == cat_upper)

        if state:
            state_clean = state.strip().lower()
            query = query.where(func.lower(WeatherReport.location_state) == state_clean)

        result = await db.execute(query)
        reports = list(result.scalars().all())

        if not reports:
            return []

        # 2. Fetch recent active canonical WeatherEvents to match existing formations
        ev_query = (
            select(WeatherEvent)
            .where(
                and_(
                    WeatherEvent.first_reported_at >= time_from - timedelta(hours=6),
                    WeatherEvent.centroid_lat.isnot(None),
                    WeatherEvent.centroid_lon.isnot(None),
                )
            )
        )
        ev_result = await db.execute(ev_query)
        active_events = list(ev_result.scalars().all())

        # 3. Form Spatiotemporal Signal Clusters
        clusters = self._cluster_reports_spatiotemporal(
            reports=reports,
            cluster_radius_km=cluster_radius_km,
            time_from=time_from,
            time_to=time_to,
        )

        emerging_events: List[EmergingEventResponse] = []

        for cluster_id, cluster_reports in clusters.items():
            # A single report cannot establish multi-signal emergence
            if len(cluster_reports) < 2:
                continue

            event_resp = await self._evaluate_cluster_emergence(
                cluster_id=cluster_id,
                reports=cluster_reports,
                time_from=time_from,
                time_to=time_to,
                active_events=active_events,
                db=db,
            )

            if event_resp is not None:
                # Filter by score thresholds if specified
                if min_emergence_score is not None and event_resp.emergence_score < min_emergence_score:
                    continue
                if min_confidence is not None and event_resp.confidence_score < min_confidence:
                    continue
                emerging_events.append(event_resp)

        # Sort by emergence score descending
        emerging_events.sort(key=lambda x: x.emergence_score, reverse=True)
        return emerging_events

    def _cluster_reports_spatiotemporal(
        self,
        reports: List[WeatherReport],
        cluster_radius_km: float,
        time_from: datetime,
        time_to: datetime,
    ) -> Dict[str, List[WeatherReport]]:
        """
        Aggregates reports into spatiotemporal clusters by geographic proximity
        and meteorological category compatibility.
        """
        clusters: Dict[str, List[WeatherReport]] = {}
        assigned_reports: Set[str] = set()

        for report in reports:
            r_id = str(report.id)
            if r_id in assigned_reports:
                continue

            r_cat = (report.primary_category or "UNKNOWN").upper()
            r_lat = report.location_lat
            r_lon = report.location_lon
            if r_lat is None or r_lon is None:
                continue

            compat_categories = CATEGORY_SYNERGIES.get(r_cat, {r_cat})

            # Start a new cluster
            cluster_key = f"emg-{r_cat.lower()}-{r_lat:.2f}-{r_lon:.2f}"
            cluster_list: List[WeatherReport] = [report]
            assigned_reports.add(r_id)

            # Find compatible neighboring reports
            for candidate in reports:
                c_id = str(candidate.id)
                if c_id in assigned_reports:
                    continue

                c_cat = (candidate.primary_category or "UNKNOWN").upper()
                c_lat = candidate.location_lat
                c_lon = candidate.location_lon
                if c_lat is None or c_lon is None:
                    continue

                # Check category compatibility
                if c_cat not in compat_categories and r_cat not in CATEGORY_SYNERGIES.get(c_cat, {c_cat}):
                    continue

                # Check spatial distance
                dist_km = haversine_distance_km(r_lat, r_lon, c_lat, c_lon)
                if dist_km <= cluster_radius_km:
                    cluster_list.append(candidate)
                    assigned_reports.add(c_id)

            clusters[cluster_key] = cluster_list

        return clusters

    async def _evaluate_cluster_emergence(
        self,
        cluster_id: str,
        reports: List[WeatherReport],
        time_from: datetime,
        time_to: datetime,
        active_events: List[WeatherEvent],
        db: AsyncSession,
    ) -> Optional[EmergingEventResponse]:
        """
        Evaluates a cluster of reports against the 9-dimensional emergence model.
        """
        if not reports:
            return None

        # Filter out duplicates from artificially inflating signal counts
        unique_reports: List[WeatherReport] = []
        seen_contents: Set[str] = set()
        duplicate_count = 0

        for r in reports:
            # Strictly ignore marked duplicates
            if getattr(r, "is_duplicate", False):
                duplicate_count += 1
                continue
            # Hash or normalize raw content
            text_val = r.normalized_text or r.raw_content or ""
            content_key = f"{r.source_id}:{r.location_lat:.3f}:{r.location_lon:.3f}:{text_val.strip()[:50]}"
            if content_key in seen_contents:
                duplicate_count += 1
                continue
            seen_contents.add(content_key)
            unique_reports.append(r)

        if len(unique_reports) < 2:
            return None

        # Sort chronologically
        unique_reports.sort(key=lambda r: _ensure_utc(r.ingested_at))

        # 1. Geographic Centroid & Spatial Footprint
        lats = [r.location_lat for r in unique_reports if r.location_lat is not None]
        lons = [r.location_lon for r in unique_reports if r.location_lon is not None]
        centroid_lat = sum(lats) / len(lats)
        centroid_lon = sum(lons) / len(lons)

        distances = [haversine_distance_km(centroid_lat, centroid_lon, r.location_lat, r.location_lon) for r in unique_reports if r.location_lat is not None and r.location_lon is not None]
        spatial_radius_km = max(distances) if distances else 0.0
        spatial_footprint_km2 = math.pi * (spatial_radius_km ** 2)

        # 2. Category & Dominant Event Type
        cat_counts: Dict[str, int] = defaultdict(int)
        for r in unique_reports:
            cat_counts[(r.primary_category or "UNKNOWN").upper()] += 1
        dominant_category_str = max(cat_counts, key=cat_counts.get)
        try:
            dominant_category = WeatherCategory(dominant_category_str)
        except ValueError:
            dominant_category = WeatherCategory.UNKNOWN

        # 3. Source Breakdown & Diversity
        source_types: Dict[str, int] = defaultdict(int)
        source_names: Set[str] = set()
        official_count = 0
        sensor_count = 0

        for r in unique_reports:
            st = _standardize_source_type(r.source.source_type if r.source else None, r.source.name if r.source else None)
            source_types[st] += 1
            if r.source and r.source.name:
                source_names.add(r.source.name)
            if st in {"IMD", "GOVERNMENT", "ERA5"}:
                official_count += 1
            if st in {"WEATHER_STATION", "RADAR", "SATELLITE"}:
                sensor_count += 1

        unique_source_count = len(source_names) or len(source_types)

        # 4. Temporal Acceleration (Half-window comparison)
        mid_time = time_from + (time_to - time_from) / 2
        older_count = sum(1 for r in unique_reports if _ensure_utc(r.ingested_at) < mid_time)
        recent_count = sum(1 for r in unique_reports if _ensure_utc(r.ingested_at) >= mid_time)

        if older_count == 0:
            acceleration_indicator = float(recent_count)
            temporal_acc_score = min(1.0, recent_count / 3.0)
        else:
            ratio = recent_count / max(1, older_count)
            acceleration_indicator = round(ratio, 2)
            temporal_acc_score = min(1.0, (ratio / 2.0))

        # 5. Spatial Convergence Score
        # Tight cluster with high count = high convergence
        if spatial_radius_km <= 15.0:
            spatial_conv_score = 0.95
        elif spatial_radius_km <= 35.0:
            spatial_conv_score = 0.80
        elif spatial_radius_km <= 65.0:
            spatial_conv_score = 0.60
        else:
            spatial_conv_score = max(0.20, 1.0 - (spatial_radius_km / 120.0))

        # 6. Source Diversity Score (Independent providers)
        diversity_buckets = len(source_types)
        source_diversity_score = min(1.0, diversity_buckets / 3.0)

        # 7. Category Consistency Score
        dominant_ratio = cat_counts[dominant_category_str] / len(unique_reports)
        category_consistency_score = dominant_ratio

        # 8. Meteorological & Official Support Score
        meteorological_support_score = min(1.0, (official_count * 0.4) + (sensor_count * 0.3) + 0.1)

        # 9. Anomaly Strength Score
        anomalous_reports = sum(1 for r in unique_reports if getattr(r, "is_anomalous", False) or (r.severity or 1) >= 3)
        anomaly_strength_score = min(1.0, anomalous_reports / max(1, len(unique_reports) * 0.5))

        # 10. DWEG Connectivity (Estimate from connected graph neighbors)
        dweg_connectivity_score = min(1.0, (len(unique_reports) / 10.0) + (0.2 if official_count > 0 else 0.0))

        # 11. Evidence Freshness Decay
        first_signal_at = _ensure_utc(unique_reports[0].ingested_at)
        latest_signal_at = _ensure_utc(unique_reports[-1].ingested_at)
        time_since_latest_min = (time_to - latest_signal_at).total_seconds() / 60.0

        if time_since_latest_min <= 15:
            freshness_score = 1.0
        elif time_since_latest_min <= 45:
            freshness_score = 0.85
        elif time_since_latest_min <= 90:
            freshness_score = 0.50
        else:
            freshness_score = max(0.1, 1.0 - (time_since_latest_min / 180.0))

        # 12. Contradiction Penalty
        contradicting_count = sum(1 for r in unique_reports if (getattr(r, "status", "") == "FLAGGED" or (r.primary_category and "CLEAR" in r.primary_category)))
        contradiction_penalty = min(0.5, (contradicting_count / len(unique_reports)) * 0.6)

        # 13. Synthesize Emergence Score (Explainable 9-factor model)
        raw_emergence = (
            (0.22 * spatial_conv_score)
            + (0.22 * temporal_acc_score)
            + (0.18 * source_diversity_score)
            + (0.12 * category_consistency_score)
            + (0.10 * meteorological_support_score)
            + (0.08 * anomaly_strength_score)
            + (0.04 * dweg_connectivity_score)
            + (0.04 * freshness_score)
            - contradiction_penalty
        )
        final_emergence_score = max(0.0, min(1.0, round(raw_emergence, 3)))

        # 14. Confidence Score (Distinct credibility metric)
        raw_conf = (
            (0.35 * (source_diversity_score * 0.8 + 0.2))
            + (0.30 * spatial_conv_score)
            + (0.20 * category_consistency_score)
            + (0.15 * meteorological_support_score)
            - (contradiction_penalty * 0.8)
        )
        final_confidence = max(0.1, min(0.98, round(raw_conf, 3)))

        # 15. Check Link with Existing Canonical WeatherEvents
        canonical_event_id: Optional[str] = None
        matched_event: Optional[WeatherEvent] = None

        for ev in active_events:
            if ev.centroid_lat is not None and ev.centroid_lon is not None:
                dist = haversine_distance_km(centroid_lat, centroid_lon, ev.centroid_lat, ev.centroid_lon)
                if dist <= (spatial_radius_km + 15.0) and (ev.category == dominant_category_str):
                    canonical_event_id = str(ev.id)
                    matched_event = ev
                    break

        # 16. Determine Emergence State Deterministically
        if time_since_latest_min > 90:
            state = EmergenceState.EXPIRED
        elif time_since_latest_min > 45 and acceleration_indicator <= 0.3:
            state = EmergenceState.DISSIPATING
        elif canonical_event_id is not None or (matched_event and matched_event.verification_status == VerificationStatus.VERIFIED.value):
            state = EmergenceState.CONFIRMED
        elif final_emergence_score >= 0.65 and len(unique_reports) >= 4 and diversity_buckets >= 2:
            state = EmergenceState.EMERGING
        elif final_emergence_score >= 0.40 and len(unique_reports) >= 3:
            state = EmergenceState.DEVELOPING
        else:
            state = EmergenceState.SIGNAL

        # Explanation generation (transparent, human-readable bullet points)
        explanation_bullets: List[str] = []
        explanation_bullets.append(f"{len(unique_reports)} compatible signal(s) observed in the last {int((time_to - time_from).total_seconds() / 60)} minutes.")
        explanation_bullets.append(f"{diversity_buckets} independent source stream(s) corroborating ({', '.join(source_types.keys())}).")
        explanation_bullets.append(f"Spatial footprint bounded within {spatial_radius_km:.1f} km radius around ({centroid_lat:.3f}, {centroid_lon:.3f}).")
        
        if acceleration_indicator > 1.2:
            explanation_bullets.append(f"Temporal velocity accelerating (+{int((acceleration_indicator - 1.0) * 100)}% incoming rate increase).")
        elif acceleration_indicator <= 0.5 and len(unique_reports) > 2:
            explanation_bullets.append("Temporal velocity decelerating (signal arrival rate decaying).")

        if official_count > 0:
            explanation_bullets.append(f"{official_count} official meteorological reading(s) confirm signal baseline.")
        if contradiction_penalty > 0:
            explanation_bullets.append(f"Contradiction penalty of -{int(contradiction_penalty * 100)}% applied due to conflicting observations.")

        factors = EmergenceFactorBreakdown(
            spatial_convergence_score=round(spatial_conv_score, 3),
            temporal_acceleration_score=round(temporal_acc_score, 3),
            source_diversity_score=round(source_diversity_score, 3),
            category_consistency_score=round(category_consistency_score, 3),
            meteorological_support_score=round(meteorological_support_score, 3),
            anomaly_strength_score=round(anomaly_strength_score, 3),
            dweg_connectivity_score=round(dweg_connectivity_score, 3),
            evidence_freshness_score=round(freshness_score, 3),
            contradiction_penalty=round(contradiction_penalty, 3),
            final_emergence_score=final_emergence_score,
            explanation_bullets=explanation_bullets,
        )

        # Build Signal Items
        signal_items: List[EmergingSignalItem] = []
        for r in unique_reports:
            r_dist = haversine_distance_km(centroid_lat, centroid_lon, r.location_lat, r.location_lon) if r.location_lat is not None and r.location_lon is not None else 0.0
            is_contra = (getattr(r, "status", "") == "FLAGGED")
            signal_items.append(
                EmergingSignalItem(
                    report_id=str(r.id),
                    source_id=str(r.source_id) if r.source_id else None,
                    source_name=r.source.name if r.source else "Unknown Source",
                    source_type=_standardize_source_type(r.source.source_type if r.source else None, r.source.name if r.source else None),
                    source_trust_score=float(r.source.trust_score) if (r.source and r.source.trust_score is not None) else 1.0,
                    category=(r.primary_category or "UNKNOWN").upper(),
                    severity=int(r.severity or 1),
                    latitude=float(r.location_lat or 0.0),
                    longitude=float(r.location_lon or 0.0),
                    location_name=f"{r.location_district or ''}, {r.location_state or ''}".strip(", "),
                    event_time=_ensure_utc(r.event_time or r.ingested_at),
                    ingested_at=_ensure_utc(r.ingested_at),
                    raw_text=r.normalized_text or r.raw_content,
                    confidence_score=float(r.classification_confidence or 0.5),
                    is_contradictory=is_contra,
                    weight=1.0,
                    distance_from_centroid_km=round(r_dist, 2),
                )
            )

        # Build Milestone Timeline
        timeline: List[EmergingTimelineMilestone] = []
        timeline.append(
            EmergingTimelineMilestone(
                timestamp=first_signal_at,
                state=EmergenceState.SIGNAL,
                title="First Signal Detected",
                description=f"Initial signal registered from {unique_reports[0].source.name if unique_reports[0].source else 'field observation'}.",
                emergence_score=min(0.35, final_emergence_score),
                signal_count=1,
            )
        )

        if len(unique_reports) >= 3:
            timeline.append(
                EmergingTimelineMilestone(
                    timestamp=first_signal_at + (latest_signal_at - first_signal_at) / 2,
                    state=EmergenceState.DEVELOPING,
                    title="Cluster Formation",
                    description=f"Spatial cluster recognized with {len(unique_reports) // 2} corroborating reports.",
                    emergence_score=min(0.55, final_emergence_score),
                    signal_count=len(unique_reports) // 2,
                )
            )

        timeline.append(
            EmergingTimelineMilestone(
                timestamp=latest_signal_at,
                state=state,
                title=f"Current State: {state.value}",
                description=f"Emergence evaluated at score {final_emergence_score * 100:.0f}% with {len(unique_reports)} signals.",
                emergence_score=final_emergence_score,
                signal_count=len(unique_reports),
            )
        )

        # Location details
        first_rep = unique_reports[0]
        state_name = first_rep.location_state
        district = first_rep.location_district
        location_summary = f"{district or ''}, {state_name or 'India'}".strip(", ") or "India"

        # Severity estimate
        max_sev = max((r.severity or 1) for r in unique_reports)
        try:
            severity = EventSeverity(max_sev)
        except ValueError:
            severity = EventSeverity.MODERATE

        now_utc = datetime.now(timezone.utc)
        clean_cluster_id = f"emg-{abs(hash(cluster_id)) % 100000000:08d}"

        return EmergingEventResponse(
            id=clean_cluster_id,
            dominant_category=dominant_category,
            sub_category=None,
            severity=severity,
            state=state,
            emergence_score=final_emergence_score,
            confidence_score=final_confidence,
            evidence_count=len(unique_reports),
            source_count=unique_source_count,
            unique_source_types=list(source_types.keys()),
            spatial_centroid_lat=round(centroid_lat, 4),
            spatial_centroid_lon=round(centroid_lon, 4),
            spatial_radius_km=round(spatial_radius_km, 2),
            spatial_footprint_km2=round(spatial_footprint_km2, 2),
            temporal_window_minutes=int((time_to - time_from).total_seconds() / 60),
            acceleration_indicator=acceleration_indicator,
            location_summary=location_summary,
            state_name=state_name,
            district=district,
            first_signal_at=first_signal_at,
            latest_signal_at=latest_signal_at,
            factors=factors,
            signals=signal_items,
            timeline=timeline,
            canonical_event_id=canonical_event_id,
            event_dna_id=canonical_event_id,
            dweg_node_id=f"node-emg-{clean_cluster_id}",
            detected_at=first_signal_at,
            updated_at=now_utc,
        )

    async def get_emerging_event_by_id(
        self,
        db: AsyncSession,
        emerging_id: str,
    ) -> Optional[EmergingEventResponse]:
        """
        Retrieves a single emerging event by its deterministic ID.
        """
        events = await self.detect_emerging_events(db=db, lookback_minutes=180)
        for ev in events:
            if ev.id == emerging_id:
                return ev
        return None

    async def broadcast_emerging_event(
        self,
        event: EmergingEventResponse,
        event_subtype: str = "detected",
    ) -> None:
        """
        Publishes a real-time WebSocket event payload for emerging event state changes.
        """
        event_type = f"emerging_event.{event_subtype}"
        payload = {
            "type": event_type,
            "emerging_event_id": event.id,
            "category": event.dominant_category.value,
            "state": event.state.value,
            "emergence_score": event.emergence_score,
            "confidence_score": event.confidence_score,
            "evidence_count": event.evidence_count,
            "source_count": event.source_count,
            "centroid": {
                "lat": event.spatial_centroid_lat,
                "lon": event.spatial_centroid_lon,
            },
            "radius_km": event.spatial_radius_km,
            "acceleration_indicator": event.acceleration_indicator,
            "detected_at": event.detected_at.isoformat(),
            "updated_at": event.updated_at.isoformat(),
            "location_summary": event.location_summary,
        }

        try:
            await ws_manager.broadcast(payload)
            logger.info("Broadcasted WebSocket event: %s for emerging event %s", event_type, event.id)
        except Exception as exc:
            logger.warning("Failed to broadcast emerging event WebSocket message: %s", exc)


# Singleton Service Instance
emerging_event_service = EmergingEventService()
