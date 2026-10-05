"""
SkyPulse Weather Event DNA Service
==================================
Constructs, manages, and evaluates the persistent Weather Event DNA for
canonical weather events.

Core Capabilities:
- Persistent Event Identity & Multi-Stage Lifecycle
- Multi-Source Evidence Fingerprint Aggregation
- Transparent, Explainable Confidence Factor Decomposition
- Multi-Dimensional Evidence Coverage Analysis (distinct from Confidence)
- Dynamic Weather Evidence Graph (DWEG) Propagation Trajectory Integration
- Chronological Evidence & Verification Event Timeline
- Related Evidence-Supported Event Discovery
- Compact DNA Fingerprint Snapshot
- Role-Based Access Control (RBAC) Data Filtering
- Real-Time WebSocket Synchronization
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

from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.models.event_evidence import EventEvidence
from app.models.source import Source
from app.models.verification import VerificationResult
from app.models.duplicate_cluster import DuplicateCluster
from app.models.enums import VerificationStatus, CorroborationType
from app.schemas.dna import (
    EventDNAResponse,
    EventDNASnapshot,
    EvidenceFingerprint,
    EvidenceFingerprintSource,
    ConfidenceFactorBreakdown,
    EvidenceCoverageBreakdown,
    DNAPropagationProfile,
    DNAPropagationStage,
    DNATimelineEntry,
    RelatedEventLink,
)
from app.services.dweg_service import (
    dweg_service,
    haversine_distance_km,
    calculate_bearing_deg,
    bearing_to_cardinal,
)
from ai.confidence_engine import ConfidenceEngine
from app.core.websocket_manager import ws_manager

logger = logging.getLogger("skypulse.event_dna_service")


def _ensure_utc(dt: Optional[datetime]) -> datetime:
    """Ensures datetime is not None and is timezone-aware in UTC."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _standardize_source_bucket(source_type: Optional[str], source_name: Optional[str] = None) -> str:
    """Standardizes raw source types into clean DNA evidence categories."""
    st = (source_type or "").upper()
    sn = (source_name or "").upper()

    if "IMD" in st or "IMD" in sn:
        return "IMD"
    if "ERA5" in st or "CDS" in st or "ECMWF" in st or "REANALYSIS" in st or "ERA5" in sn:
        return "ERA5"
    if "GOV" in st or "DATA_GOV" in st or "NDMA" in st or "CWC" in sn:
        return "GOVERNMENT"
    if "CITIZEN" in st or "PUBLIC" in st or "USER" in st:
        return "CITIZEN"
    if "SOCIAL" in st or "TWITTER" in st or "X" in st or "TELEGRAM" in st:
        return "SOCIAL"
    if "AWS" in st or "AUTOMATIC_WEATHER" in st or "SENSOR" in st or "IOT" in st:
        return "WEATHER_STATION"
    if "RADAR" in st or "DOPPLER" in st:
        return "RADAR"
    if "SATELLITE" in st or "INSAT" in st:
        return "SATELLITE"
    return "OTHER"


def _determine_lifecycle_phase(
    status: str,
    evidence_count: int,
    confidence: float,
    has_propagation: bool,
    resolved_at: Optional[datetime] = None,
    contradictions_count: int = 0,
) -> str:
    """
    Evaluates the continuous lifecycle evolution phase of an Event DNA.
    Phases: DETECTED -> EMERGING -> SUPPORTED -> VERIFIED -> PROPAGATING -> SUBSIDING -> RESOLVED
    """
    if resolved_at is not None:
        return "RESOLVED"
    if status == "CONTRADICTED" or (contradictions_count > evidence_count and evidence_count > 0):
        return "CONTRADICTED"
    if status == "VERIFIED":
        if has_propagation:
            return "PROPAGATING"
        return "VERIFIED"
    if has_propagation and confidence >= 0.70:
        return "PROPAGATING"
    if confidence >= 0.80 or evidence_count >= 5:
        return "SUPPORTED"
    if evidence_count >= 2 or confidence >= 0.65:
        return "EMERGING"
    return "DETECTED"


class EventDNAService:
    """Core intelligence engine for generating and tracking Weather Event DNA."""

    @classmethod
    async def get_event_dna(
        cls,
        event_id: str,
        db: AsyncSession,
        role: str = "PUBLIC",
    ) -> Optional[EventDNAResponse]:
        """
        Generates the comprehensive, persistent Weather Event DNA for a canonical event.
        Answers identity, evolution, evidence footprint, credibility, and propagation.
        """
        try:
            e_uuid = uuid.UUID(event_id)
        except ValueError:
            return None

        # 1. Fetch Canonical Event with relationships
        q = (
            select(WeatherEvent)
            .options(
                selectinload(WeatherEvent.evidence_links),
                selectinload(WeatherEvent.verification_result),
                selectinload(WeatherEvent.duplicate_cluster),
            )
            .where(WeatherEvent.id == e_uuid, WeatherEvent.is_deleted == False)
        )
        res = await db.execute(q)
        event = res.scalars().first()
        if not event:
            return None

        # 2. Fetch all contributing WeatherReports and their Sources
        report_ids = [el.weather_report_id for el in event.evidence_links]
        reports: List[WeatherReport] = []
        if report_ids:
            rq = (
                select(WeatherReport)
                .options(selectinload(WeatherReport.source))
                .where(WeatherReport.id.in_(report_ids))
                .order_by(WeatherReport.ingested_at.asc())
            )
            r_res = await db.execute(rq)
            reports = list(r_res.scalars().all())

        # Build evidence lookup
        evidence_by_report_id: Dict[uuid.UUID, EventEvidence] = {
            el.weather_report_id: el for el in event.evidence_links
        }

        # 3. Aggregate Evidence Fingerprint by Source
        fingerprint = cls._build_evidence_fingerprint(event, reports, evidence_by_report_id)

        # 4. Compute Explainable Confidence Factor Decomposition
        confidence_breakdown = cls._calculate_confidence_breakdown(event, reports, fingerprint)

        # 5. Compute Multi-Dimensional Evidence Coverage Breakdown
        coverage_breakdown = cls._calculate_evidence_coverage(event, reports, fingerprint)

        # 6. Reconstruct Propagation Profile from DWEG & Evidence Trajectory
        propagation_profile = await cls._build_propagation_profile(event, reports, db)

        # 7. Generate Event Evolution Timeline
        timeline = cls._build_event_timeline(event, reports, evidence_by_report_id, propagation_profile)

        # 8. Discover Related Events via DWEG & Proximity
        related_events = await cls._discover_related_events(event, db)

        # 9. Determine Lifecycle Phase & Spatial Footprint
        contradictions = fingerprint.contradicting_evidence_count
        lifecycle_phase = _determine_lifecycle_phase(
            status=event.verification_status,
            evidence_count=fingerprint.total_evidence_count,
            confidence=event.confidence_score,
            has_propagation=propagation_profile.has_propagation,
            resolved_at=event.resolved_at,
            contradictions_count=contradictions,
        )

        origin_lat = reports[0].location_lat if reports and reports[0].location_lat else event.centroid_lat
        origin_lon = reports[0].location_lon if reports and reports[0].location_lon else event.centroid_lon
        curr_lat = event.centroid_lat or origin_lat
        curr_lon = event.centroid_lon or origin_lon

        # Spatial footprint calculation
        max_dist_km = 0.0
        if curr_lat and curr_lon:
            for r in reports:
                if r.location_lat and r.location_lon:
                    d = haversine_distance_km(curr_lat, curr_lon, r.location_lat, r.location_lon)
                    if d > max_dist_km:
                        max_dist_km = d
        spatial_radius = round(max(max_dist_km, 5.0), 2)
        spatial_footprint = round(math.pi * (spatial_radius ** 2), 2)

        # 10. Compact Snapshot & Observation Corroboration
        from app.services.weather_intelligence_service import (
            synthesize_semantic_event_intelligence,
            evaluate_physical_observation_corroboration,
        )
        from app.models.weather_observation import WeatherObservation
        from ai.confidence_engine import get_confidence_tier_label

        # Lookup matched physical observation
        matched_obs = None
        if event.primary_state:
            obs_stmt = select(WeatherObservation).where(WeatherObservation.state.ilike(f"%{event.primary_state}%"))
            if event.primary_district:
                obs_stmt = obs_stmt.where(WeatherObservation.district.ilike(f"%{event.primary_district}%"))
            obs_stmt = obs_stmt.order_by(WeatherObservation.observed_at.desc()).limit(1)
            obs_res = await db.execute(obs_stmt)
            matched_obs = obs_res.scalar_one_or_none()
            if not matched_obs:
                obs_stmt2 = select(WeatherObservation).where(WeatherObservation.state.ilike(f"%{event.primary_state}%")).order_by(WeatherObservation.observed_at.desc()).limit(1)
                obs_res2 = await db.execute(obs_stmt2)
                matched_obs = obs_res2.scalar_one_or_none()

        obs_eval = evaluate_physical_observation_corroboration(event.category, event.sub_category, matched_obs)
        conf_tier = get_confidence_tier_label(event.confidence_score)

        # Source Claim Label
        indep_count = fingerprint.unique_sources_count
        corrob_count = fingerprint.supporting_evidence_count if indep_count > 1 else 0
        if indep_count >= 2 and fingerprint.cross_source_corroborated:
            claim_label = "MULTI-SOURCE INTELLIGENCE"
        elif indep_count >= 2:
            claim_label = "LIMITED CORROBORATION"
        else:
            claim_label = "SINGLE-SOURCE SIGNAL"

        raw_report_texts = [r.raw_content or r.normalized_text or "" for r in reports]
        semantic_intel = synthesize_semantic_event_intelligence(
            category=event.category,
            sub_category=event.sub_category,
            state=event.primary_state,
            district=event.primary_district,
            city=event.primary_city,
            evidence_texts=raw_report_texts,
            publishers=[r.source.name for r in reports if r.source and r.source.name],
            evidence_count=max(len(reports), event.evidence_count),
        )

        snapshot = EventDNASnapshot(
            event_id=str(event.id),
            event_type=event.category,
            phenomenon=semantic_intel["phenomenon"],
            event_nature=semantic_intel["event_nature"],
            temporal_scope=semantic_intel["temporal_scope"],
            is_current_observation=obs_eval["is_current_observation"],
            is_current_observation_supported=obs_eval["is_current_observation_supported"],
            evidence_basis=semantic_intel["evidence_basis"],
            status=event.verification_status,
            severity=event.severity,
            source_count=fingerprint.unique_sources_count,
            independent_source_count=indep_count,
            corroborating_source_count=corrob_count,
            source_claim_label=claim_label,
            confidence_tier_label=conf_tier,
            observation_status_label=obs_eval["observation_status_label"],
            evidence_count=fingerprint.total_evidence_count,
            conflict_count=fingerprint.contradicting_evidence_count,
            duplicate_count=fingerprint.duplicate_count,
            propagation_stages=propagation_profile.stage_count,
            confidence_score=round(event.confidence_score, 2),
            evidence_coverage_score=coverage_breakdown.overall_coverage_score,
            first_observed_at=event.first_reported_at,
            last_updated_at=event.last_updated_at,
        )

        # 11. Assemble Full Response
        response = EventDNAResponse(
            event_id=str(event.id),
            event_type=event.category,
            sub_category=semantic_intel["sub_category"],
            phenomenon=semantic_intel["phenomenon"],
            event_nature=semantic_intel["event_nature"],
            temporal_scope=semantic_intel["temporal_scope"],
            is_current_observation=obs_eval["is_current_observation"],
            is_current_observation_supported=obs_eval["is_current_observation_supported"],
            observation_summary=obs_eval["observation_summary"],
            observation_status_label=obs_eval["observation_status_label"],
            source_claim_label=claim_label,
            confidence_tier_label=conf_tier,
            evidence_basis=semantic_intel["evidence_basis"],
            status=event.verification_status,
            lifecycle_phase=lifecycle_phase,
            severity=event.severity,
            first_observed_at=event.first_reported_at,
            last_observed_at=event.last_updated_at,
            resolved_at=event.resolved_at,
            origin_latitude=origin_lat,
            origin_longitude=origin_lon,
            current_latitude=curr_lat,
            current_longitude=curr_lon,
            primary_city=event.primary_city,
            primary_district=event.primary_district,
            primary_state=event.primary_state,
            spatial_radius_km=spatial_radius,
            spatial_footprint_km=spatial_footprint,
            confidence=confidence_breakdown,
            evidence_coverage=coverage_breakdown,
            evidence=fingerprint,
            propagation=propagation_profile,
            timeline=timeline,
            related_events=related_events,
            dweg_node_id=event.dweg_node_id,
            snapshot=snapshot,
            created_at=event.created_at,
            updated_at=event.updated_at,
        )

        # Apply RBAC restrictions for non-analysts
        if role in ["PUBLIC", "CITIZEN"]:
            # Public gets high-level evidence and journey, without internal reviewer notes
            for t in response.timeline:
                t.source_name = None

        return response

    @classmethod
    def _build_evidence_fingerprint(
        cls,
        event: WeatherEvent,
        reports: List[WeatherReport],
        evidence_by_report_id: Dict[uuid.UUID, EventEvidence],
    ) -> EvidenceFingerprint:
        """Groups contributing reports by standardized source categories with corroboration metrics."""
        sources_map: Dict[str, EvidenceFingerprintSource] = {}
        total_evidence = max(len(reports), event.evidence_count)
        supporting_count = 0
        contradicting_count = 0
        unverified_count = 0
        duplicate_count = 0

        event_lat = event.centroid_lat
        event_lon = event.centroid_lon

        for r in reports:
            st = r.source.source_type if r.source else "UNKNOWN"
            sn = r.source.name if r.source else ""
            bucket = _standardize_source_bucket(st, sn)

            if bucket not in sources_map:
                sources_map[bucket] = EvidenceFingerprintSource(
                    source_type=bucket,
                    total_observations=0,
                    supporting_observations=0,
                    contradicting_observations=0,
                    unverified_observations=0,
                    latest_observation_at=None,
                    spatial_coverage_km=0.0,
                    confidence_weight=r.source.trust_score if r.source else 0.5,
                )

            src_obj = sources_map[bucket]
            src_obj.total_observations += 1

            if r.is_duplicate:
                duplicate_count += 1

            # Check corroboration type
            ev_link = evidence_by_report_id.get(r.id)
            c_type = ev_link.corroboration_type if ev_link else CorroborationType.PRIMARY.value

            if c_type == CorroborationType.CONTRADICTING.value:
                contradicting_count += 1
                src_obj.contradicting_observations += 1
            elif c_type in [CorroborationType.PRIMARY.value, CorroborationType.CORROBORATING.value]:
                supporting_count += 1
                src_obj.supporting_observations += 1
            else:
                unverified_count += 1
                src_obj.unverified_observations += 1

            # Update latest observation timestamp
            obs_time = r.event_time or r.ingested_at
            if src_obj.latest_observation_at is None or obs_time > src_obj.latest_observation_at:
                src_obj.latest_observation_at = obs_time

            # Spatial coverage for this source
            if event_lat and event_lon and r.location_lat and r.location_lon:
                d = haversine_distance_km(event_lat, event_lon, r.location_lat, r.location_lon)
                if d > src_obj.spatial_coverage_km:
                    src_obj.spatial_coverage_km = round(d, 2)

        # Fallback for events with missing raw reports
        if not reports and event.evidence_count > 0:
            sources_map["PRIMARY_SOURCE"] = EvidenceFingerprintSource(
                source_type="PRIMARY_SOURCE",
                total_observations=event.evidence_count,
                supporting_observations=event.evidence_count,
                contradicting_observations=0,
                unverified_observations=0,
                latest_observation_at=event.last_updated_at,
                spatial_coverage_km=5.0,
                confidence_weight=0.7,
            )
            supporting_count = event.evidence_count

        return EvidenceFingerprint(
            total_evidence_count=max(total_evidence, supporting_count + contradicting_count + unverified_count),
            supporting_evidence_count=supporting_count,
            contradicting_evidence_count=contradicting_count,
            unverified_evidence_count=unverified_count,
            duplicate_count=duplicate_count,
            unique_sources_count=len(sources_map),
            sources=sources_map,
            cross_source_corroborated=len(sources_map) >= 2 and supporting_count >= 2,
        )

    @classmethod
    def _calculate_confidence_breakdown(
        cls,
        event: WeatherEvent,
        reports: List[WeatherReport],
        fingerprint: EvidenceFingerprint,
    ) -> ConfidenceFactorBreakdown:
        """Deconstructs the actual confidence score into explainable components."""
        # 1. Source Reliability (mean trust)
        trust_scores = [
            r.source.trust_score for r in reports if r.source and r.source.trust_score is not None
        ]
        source_rel = sum(trust_scores) / len(trust_scores) if trust_scores else 0.60

        # 2. Cross-Source Corroboration
        num_srcs = fingerprint.unique_sources_count
        cross_source_score = min(1.0, 0.35 * num_srcs) if fingerprint.cross_source_corroborated else 0.20

        # 3. Spatial Consistency
        spatial_score = 0.85
        if event.centroid_lat and event.centroid_lon and len(reports) > 1:
            distances = [
                haversine_distance_km(event.centroid_lat, event.centroid_lon, r.location_lat, r.location_lon)
                for r in reports
                if r.location_lat and r.location_lon
            ]
            if distances:
                avg_dist = sum(distances) / len(distances)
                # Within 30km is high consistency
                spatial_score = max(0.40, min(0.98, 1.0 - (avg_dist / 100.0)))

        # 4. Temporal Consistency
        temporal_score = 0.85
        if len(reports) > 1:
            times = [r.event_time or r.ingested_at for r in reports]
            span_hours = (max(times) - min(times)).total_seconds() / 3600.0
            if span_hours <= 3.0:
                temporal_score = 0.95
            elif span_hours <= 12.0:
                temporal_score = 0.85
            else:
                temporal_score = 0.70

        # 5. Meteorological & Classification Score
        meteo_scores = [
            r.classification_confidence for r in reports if r.classification_confidence is not None
        ]
        meteo_score = sum(meteo_scores) / len(meteo_scores) if meteo_scores else 0.75

        # 6. Media Score
        media_score = 0.50
        has_media = any(r.metadata_ and r.metadata_.get("media_urls") for r in reports)
        if has_media:
            media_score = 0.85

        # 7. Contradiction Penalty
        penalty = 0.0
        if fingerprint.contradicting_evidence_count > 0:
            penalty = min(0.40, 0.15 * fingerprint.contradicting_evidence_count)

        final_conf = round(event.confidence_score, 2)

        explanation = (
            f"Event Confidence {final_conf:.0%}: "
            f"Source Trust ({source_rel:.0%}), Cross-Source Support ({cross_source_score:.0%}), "
            f"Spatial ({spatial_score:.0%}), Temporal ({temporal_score:.0%})"
        )
        if penalty > 0:
            explanation += f", Contradiction Penalty (-{penalty:.0%})"

        return ConfidenceFactorBreakdown(
            source_reliability_score=round(source_rel, 2),
            cross_source_support_score=round(cross_source_score, 2),
            spatial_consistency_score=round(spatial_score, 2),
            temporal_consistency_score=round(temporal_score, 2),
            meteorological_score=round(meteo_score, 2),
            media_score=round(media_score, 2),
            contradiction_penalty=round(penalty, 2),
            final_confidence=final_conf,
            explanation=explanation,
        )

    @classmethod
    def _calculate_evidence_coverage(
        cls,
        event: WeatherEvent,
        reports: List[WeatherReport],
        fingerprint: EvidenceFingerprint,
    ) -> EvidenceCoverageBreakdown:
        """
        Calculates the multi-dimensional Evidence Coverage score (0.0 - 1.0).
        Measures completeness of observation across independent dimensions.
        """
        active_dims = 0

        # 1. Temporal Coverage (freshness + sustained tracking)
        temp_cov = 0.0
        if reports:
            active_dims += 1
            times = [r.event_time or r.ingested_at for r in reports]
            span_hrs = (max(times) - min(times)).total_seconds() / 3600.0
            if span_hrs >= 2.0 or len(reports) >= 3:
                temp_cov = 0.90
            elif len(reports) >= 1:
                temp_cov = 0.60

        # 2. Spatial Coverage (coordinate resolution + spread)
        spat_cov = 0.0
        has_coords = [r for r in reports if r.location_lat and r.location_lon]
        if has_coords:
            active_dims += 1
            if len(has_coords) >= 3:
                spat_cov = 0.95
            elif len(has_coords) >= 1:
                spat_cov = 0.70

        # 3. Source Diversity Coverage
        src_cov = 0.0
        num_srcs = fingerprint.unique_sources_count
        if num_srcs > 0:
            active_dims += 1
            if num_srcs >= 4:
                src_cov = 1.0
            elif num_srcs == 3:
                src_cov = 0.85
            elif num_srcs == 2:
                src_cov = 0.65
            else:
                src_cov = 0.35

        # 4. Meteorological Observation Coverage
        met_cov = 0.0
        has_met = any(
            r.primary_category in ["RAINFALL", "THUNDERSTORM", "FLOODING", "HEATWAVE", "STRONG_WINDS"]
            for r in reports
        )
        if has_met:
            active_dims += 1
            met_cov = 0.80

        # 5. Official / Institutional Validation Coverage
        off_cov = 0.0
        has_official = any(k in ["IMD", "GOVERNMENT", "ERA5"] for k in fingerprint.sources.keys())
        if has_official:
            active_dims += 1
            off_cov = 0.90
        elif len(reports) > 0:
            active_dims += 1
            off_cov = 0.20

        # 6. Corroboration Ratio Coverage
        cor_cov = 0.0
        if fingerprint.total_evidence_count > 0:
            active_dims += 1
            ratio = fingerprint.supporting_evidence_count / float(fingerprint.total_evidence_count)
            cor_cov = round(ratio, 2)

        # Dimension weights
        weights = [0.20, 0.20, 0.20, 0.15, 0.15, 0.10]
        dim_values = [temp_cov, spat_cov, src_cov, met_cov, off_cov, cor_cov]
        overall = sum(w * v for w, v in zip(weights, dim_values))
        overall = round(max(0.05, min(0.99, overall)), 2)

        explanation = (
            f"Evidence Coverage {overall:.0%}: Supported across {active_dims}/6 observational dimensions "
            f"(Sources: {num_srcs}, Official: {'YES' if has_official else 'PENDING'}, "
            f"Spatial: {spat_cov:.0%}, Temporal: {temp_cov:.0%})"
        )

        return EvidenceCoverageBreakdown(
            overall_coverage_score=overall,
            temporal_coverage=round(temp_cov, 2),
            spatial_coverage=round(spat_cov, 2),
            source_diversity_coverage=round(src_cov, 2),
            meteorological_coverage=round(met_cov, 2),
            official_validation_coverage=round(off_cov, 2),
            corroboration_coverage=round(cor_cov, 2),
            active_dimensions_count=active_dims,
            explanation=explanation,
        )

    @classmethod
    async def _build_propagation_profile(
        cls,
        event: WeatherEvent,
        reports: List[WeatherReport],
        db: AsyncSession,
    ) -> DNAPropagationProfile:
        """Constructs the spatial propagation profile and recorded stages from DWEG & evidence points."""
        stages: List[DNAPropagationStage] = []

        # 1. Reconstruct stages chronologically from geolocated evidence reports
        geo_reports = [r for r in reports if r.location_lat and r.location_lon]
        geo_reports.sort(key=lambda r: r.event_time or r.ingested_at)

        if len(geo_reports) >= 2:
            first_r = geo_reports[0]
            total_dist = 0.0
            last_lat = first_r.location_lat
            last_lon = first_r.location_lon
            last_time = first_r.event_time or first_r.ingested_at

            for i, r in enumerate(geo_reports, start=1):
                cur_lat = r.location_lat
                cur_lon = r.location_lon
                cur_time = _ensure_utc(r.event_time or r.ingested_at)

                d_km = haversine_distance_km(first_r.location_lat, first_r.location_lon, cur_lat, cur_lon)
                bearing = calculate_bearing_deg(last_lat, last_lon, cur_lat, cur_lon) if (cur_lat != last_lat or cur_lon != last_lon) else None
                cardinal = bearing_to_cardinal(bearing) if bearing is not None else "STATIONARY"

                dt_hrs = (_ensure_utc(cur_time) - _ensure_utc(last_time)).total_seconds() / 3600.0
                step_dist = haversine_distance_km(last_lat, last_lon, cur_lat, cur_lon)
                speed = round(step_dist / dt_hrs, 1) if dt_hrs > 0.05 else 0.0

                stage_obj = DNAPropagationStage(
                    stage_number=i,
                    timestamp=cur_time,
                    center_latitude=cur_lat,
                    center_longitude=cur_lon,
                    direction_name=cardinal,
                    direction_deg=bearing,
                    estimated_speed_kmh=speed,
                    distance_from_origin_km=round(d_km, 2),
                    confidence=0.85,
                    supporting_evidence_count=1,
                    stage_description=f"Cluster observation at {r.location_city or r.location_district or 'location'}",
                )
                stages.append(stage_obj)
                total_dist += step_dist
                last_lat = cur_lat
                last_lon = cur_lon
                last_time = cur_time

            has_prop = total_dist > 5.0 and len(stages) >= 2
            avg_speed = sum(s.estimated_speed_kmh for s in stages) / len(stages) if stages else 0.0
            overall_dir = stages[-1].direction_name if stages else "STATIONARY"

            return DNAPropagationProfile(
                has_propagation=has_prop,
                stage_count=len(stages),
                stages=stages,
                overall_direction=overall_dir,
                average_speed_kmh=round(avg_speed, 1),
                total_distance_km=round(total_dist, 2),
            )

        # 2. Query existing DWEG propagation timeline fallback
        try:
            dweg_timeline = await dweg_service.get_propagation_timeline(str(event.id), db)
            if dweg_timeline and dweg_timeline.propagation_steps:
                total_dist = 0.0
                origin_lat = event.centroid_lat or 0.0
                origin_lon = event.centroid_lon or 0.0

                for i, step in enumerate(dweg_timeline.propagation_steps, start=1):
                    loc_dict = step.location or {}
                    s_lat = loc_dict.get("lat") or loc_dict.get("latitude") or origin_lat
                    s_lon = loc_dict.get("lon") or loc_dict.get("longitude") or origin_lon

                    dist_orig = 0.0
                    if origin_lat and origin_lon and s_lat and s_lon:
                        dist_orig = haversine_distance_km(origin_lat, origin_lon, s_lat, s_lon)

                    stage_obj = DNAPropagationStage(
                        stage_number=i,
                        timestamp=_ensure_utc(step.timestamp),
                        center_latitude=s_lat,
                        center_longitude=s_lon,
                        direction_name=step.propagation_direction or "STATIONARY",
                        direction_deg=None,
                        estimated_speed_kmh=0.0,
                        distance_from_origin_km=round(dist_orig, 2),
                        confidence=0.85,
                        supporting_evidence_count=max(1, step.evidence_count),
                        stage_description=f"DWEG Propagation step {step.step}",
                    )
                    stages.append(stage_obj)

                overall_dir = stages[-1].direction_name if stages else "STATIONARY"

                return DNAPropagationProfile(
                    has_propagation=len(stages) >= 2 or dweg_timeline.is_still_propagating,
                    stage_count=len(stages),
                    stages=stages,
                    overall_direction=overall_dir,
                    average_speed_kmh=0.0,
                    total_distance_km=round(total_dist, 2),
                )
        except Exception as e:
            logger.debug("DWEG propagation query fallback: %s", e)

        # Stationary single-point stage
        lat = event.centroid_lat or 0.0
        lon = event.centroid_lon or 0.0
        single_stage = DNAPropagationStage(
            stage_number=1,
            timestamp=event.first_reported_at,
            center_latitude=lat,
            center_longitude=lon,
            direction_name="STATIONARY",
            direction_deg=0.0,
            estimated_speed_kmh=0.0,
            distance_from_origin_km=0.0,
            confidence=round(event.confidence_score, 2),
            supporting_evidence_count=max(1, event.evidence_count),
            stage_description="Initial observation location",
        )
        return DNAPropagationProfile(
            has_propagation=False,
            stage_count=1,
            stages=[single_stage],
            overall_direction="STATIONARY",
            average_speed_kmh=0.0,
            total_distance_km=0.0,
        )

    @classmethod
    def _build_event_timeline(
        cls,
        event: WeatherEvent,
        reports: List[WeatherReport],
        evidence_by_report_id: Dict[uuid.UUID, EventEvidence],
        propagation: DNAPropagationProfile,
    ) -> List[DNATimelineEntry]:
        """Synthesizes a chronological event milestone journey from evidence and verification events."""
        entries: List[DNATimelineEntry] = []

        # 1. First Detection Milestone
        first_rep = reports[0] if reports else None
        first_time = _ensure_utc(first_rep.event_time or first_rep.ingested_at if first_rep else event.first_reported_at)
        st_first = first_rep.source.source_type if first_rep and first_rep.source else "UNKNOWN"
        sn_first = first_rep.source.name if first_rep and first_rep.source else "System Ingestion"

        entries.append(
            DNATimelineEntry(
                timestamp=first_time,
                phase="DETECTED",
                title=f"Initial {event.category} report detected",
                description=f"First observation registered via {sn_first} ({st_first}). Initial severity level {event.severity}.",
                source_type=st_first,
                source_name=sn_first,
                confidence_at_step=0.55,
                evidence_count_at_step=1,
                location_summary=f"{event.primary_city or event.primary_district or 'Region'}, {event.primary_state or 'India'}",
            )
        )

        # 2. Intermediate Corroborating / Contradicting Reports
        running_evidence = 1
        for i, r in enumerate(reports[1:], start=2):
            running_evidence += 1
            r_time = _ensure_utc(r.event_time or r.ingested_at)
            st = r.source.source_type if r.source else "UNKNOWN"
            sn = r.source.name if r.source else "Reporter"
            ev = evidence_by_report_id.get(r.id)
            c_type = ev.corroboration_type if ev else CorroborationType.CORROBORATING.value

            if c_type == CorroborationType.CONTRADICTING.value:
                entries.append(
                    DNATimelineEntry(
                        timestamp=r_time,
                        phase="CONTRADICTED",
                        title=f"Contradictory evidence received from {sn}",
                        description=f"Conflicting report flagged for analyst review. Claimed category: {r.primary_category}.",
                        source_type=st,
                        source_name=sn,
                        confidence_at_step=max(0.2, event.confidence_score - 0.15),
                        evidence_count_at_step=running_evidence,
                        location_summary=r.location_city or r.location_district,
                    )
                )
            else:
                entries.append(
                    DNATimelineEntry(
                        timestamp=r_time,
                        phase="SUPPORTED",
                        title=f"Independent corroboration from {sn}",
                        description=f"Corroborating observation added to Event DNA. Corroboration score: {ev.corroboration_score if ev else 0.8:.2f}.",
                        source_type=st,
                        source_name=sn,
                        confidence_at_step=round(min(0.95, 0.55 + 0.08 * i), 2),
                        evidence_count_at_step=running_evidence,
                        location_summary=r.location_city or r.location_district,
                    )
                )

        # 3. Verification Milestone (if verified)
        if event.verification_status == VerificationStatus.VERIFIED.value:
            v_time = _ensure_utc(event.verification_result.updated_at if event.verification_result else event.last_updated_at)
            entries.append(
                DNATimelineEntry(
                    timestamp=v_time,
                    phase="VERIFIED",
                    title="Event status upgraded to VERIFIED",
                    description=f"Multi-source evidence criteria met. Confidence score reached {event.confidence_score:.0%}.",
                    source_type="VERIFICATION_ENGINE",
                    source_name="SkyPulse Verification Engine",
                    confidence_at_step=event.confidence_score,
                    evidence_count_at_step=running_evidence,
                    location_summary=f"{event.primary_district}, {event.primary_state}",
                )
            )

        # 4. Propagation Stages Milestones
        if propagation.has_propagation and len(propagation.stages) >= 2:
            for stage in propagation.stages[1:]:
                entries.append(
                    DNATimelineEntry(
                        timestamp=_ensure_utc(stage.timestamp),
                        phase="PROPAGATING",
                        title=f"Propagation detected ({stage.direction_name})",
                        description=f"Event centroid shifted {stage.distance_from_origin_km} km at ~{stage.estimated_speed_kmh} km/h.",
                        source_type="DWEG",
                        source_name="Dynamic Weather Evidence Graph",
                        confidence_at_step=stage.confidence,
                        evidence_count_at_step=running_evidence,
                        location_summary=f"Lat {stage.center_latitude:.2f}, Lon {stage.center_longitude:.2f}",
                    )
                )

        # 5. Resolution Milestone (if resolved)
        if event.resolved_at:
            entries.append(
                DNATimelineEntry(
                    timestamp=event.resolved_at,
                    phase="RESOLVED",
                    title="Weather phenomenon subsiding / resolved",
                    description="Event resolved. Meteorological indicators returned below alert thresholds.",
                    source_type="SYSTEM",
                    source_name="Lifecycle Monitor",
                    confidence_at_step=event.confidence_score,
                    evidence_count_at_step=running_evidence,
                    location_summary=f"{event.primary_district}, {event.primary_state}",
                )
            )

        # Sort entries chronologically
        entries.sort(key=lambda x: x.timestamp)
        return entries

    @classmethod
    async def _discover_related_events(
        cls,
        event: WeatherEvent,
        db: AsyncSession,
    ) -> List[RelatedEventLink]:
        """Discovers related canonical events through DWEG edges and spatial-temporal adjacency."""
        links: List[RelatedEventLink] = []

        if not event.centroid_lat or not event.centroid_lon:
            return links

        # Query active adjacent events within 100km occurring within 24 hours
        time_window_start = event.first_reported_at - timedelta(hours=24)
        time_window_end = event.last_updated_at + timedelta(hours=24)

        q = (
            select(WeatherEvent)
            .where(
                WeatherEvent.id != event.id,
                WeatherEvent.is_deleted == False,
                WeatherEvent.first_reported_at.between(time_window_start, time_window_end),
                WeatherEvent.centroid_lat.isnot(None),
                WeatherEvent.centroid_lon.isnot(None),
            )
            .limit(20)
        )
        res = await db.execute(q)
        candidates = res.scalars().all()

        for cand in candidates:
            dist = haversine_distance_km(
                event.centroid_lat, event.centroid_lon, cand.centroid_lat, cand.centroid_lon
            )
            if dist <= 120.0:
                dt_mins = int(abs((cand.first_reported_at - event.first_reported_at).total_seconds() / 60.0))

                # Determine relationship type
                rel_type = "SPATIALLY_ADJACENT"
                if event.category == cand.category:
                    if dist <= 40.0:
                        rel_type = "CORROBORATES"
                    elif dist <= 90.0 and dt_mins >= 30:
                        rel_type = "PROPAGATES_TO"
                elif event.category == "RAINFALL" and cand.category == "FLOODING":
                    rel_type = "SUPPORTS"
                elif event.category == "FLOODING" and cand.category == "RAINFALL":
                    rel_type = "SUPPORTS"

                link = RelatedEventLink(
                    event_id=str(cand.id),
                    category=cand.category,
                    severity=cand.severity,
                    verification_status=cand.verification_status,
                    relationship_type=rel_type,
                    distance_km=round(dist, 1),
                    time_delta_minutes=dt_mins,
                    confidence=round(cand.confidence_score, 2),
                    evidence_count=cand.evidence_count,
                )
                links.append(link)

        # Sort by proximity
        links.sort(key=lambda x: x.distance_km or 999.0)
        return links[:8]

    @classmethod
    async def publish_dna_update_event(
        cls,
        event_id: str,
        changed_fields: List[str],
        confidence: float,
        evidence_coverage: float,
        event_type: str = "RAINFALL",
    ) -> None:
        """Publishes a compact weather_event.dna_updated event over WebSocket."""
        payload = {
            "type": "weather_event.dna_updated",
            "data": {
                "event_id": event_id,
                "event_type": event_type,
                "changed_fields": changed_fields,
                "confidence_score": round(confidence, 2),
                "evidence_coverage_score": round(evidence_coverage, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
        try:
            await ws_manager.broadcast(payload)
            logger.debug("Broadcasted weather_event.dna_updated for event %s", event_id)
        except Exception as e:
            logger.warning("Failed to broadcast weather_event.dna_updated: %s", e)


event_dna_service = EventDNAService()
