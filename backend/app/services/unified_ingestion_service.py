"""
SkyPulse Unified Real-Time Weather Ingestion & Processing Pipeline Service
==========================================================================
Coordinates the end-to-end execution lifecycle:
SOURCE / CONNECTOR
    ↓
CANONICAL RAW EVENT
    ↓
NORMALIZATION & MEASUREMENT EXTRACTION
    ↓
INDIA LOCATION VALIDATION & QUARANTINE
    ↓
IDEMPOTENCY & EXACT DEDUP
    ↓
POSTGRESQL WEATHER REPORT PERSISTENCE
    ↓
AI EVENT CLASSIFICATION & NLP EXTRACTION
    ↓
MEDIA / IMAGE ANALYSIS
    ↓
SPATIOTEMPORAL CLUSTERING & DEDUPLICATION (CANONICAL WEATHER EVENT)
    ↓
SOURCE TRUST & REPUTATION ENGINE
    ↓
CROSS-SOURCE VERIFICATION & CORROBORATION
    ↓
WEATHER EVENT DNA FINGERPRINT
    ↓
DYNAMIC WEATHER EVIDENCE GRAPH (DWEG)
    ↓
REALTIME EVENT BUS & WEBSOCKET FAN-OUT
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from geoalchemy2.elements import WKTElement
from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ai.anomaly_detector import AnomalyDetector
from ai.confidence_engine import ConfidenceEngine
from ai.deduplicator import DeduplicationEngine
from ai.dweg_service import dweg_service as ai_dweg_service
from ai.event_classifier import EventClassifier
from ai.image_analyzer import ImageAnalyzer
from ai.nlp_extractor import NLPExtractor
from ai.opensearch_indexer import opensearch_indexer
from ai.source_trust import SourceTrustEngine
from ai.verification_engine import VerificationEngine
from app.core.config import settings
from app.core.freshness_policy import calculate_event_expiry
from app.core.websocket_manager import build_event_envelope, ws_manager
from app.models.enums import (
    CorroborationType,
    EventLifecycleStatus,
    ReportStatus,
    SourceType,
    VerificationStatus,
    WeatherCategory,
)
from app.models.event_evidence import EventEvidence
from app.models.media import Media
from app.models.source import Source
from app.models.verification import VerificationResult
from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.services.dweg_service import dweg_service
from app.services.event_dna_service import event_dna_service
from app.services.source_reputation_service import source_reputation_service
from connectors.idempotency import idempotency_service
from connectors.kafka_bus import (
    TOPIC_AI_PROCESSED,
    TOPIC_ANOMALIES,
    TOPIC_PENDING_AI,
    TOPIC_RAW,
    TOPIC_VERIFICATION_UPDATES,
    kafka_producer,
)
from connectors.normalizer import (
    INDIAN_CITIES_REFERENCE,
    INDIAN_STATES_REFERENCE,
    normalize_category,
    normalize_raw_event,
    sanitize_text,
)
from connectors.schema import CanonicalRawEvent, NormalizedEvent
from ml.inference_service import ml_inference_service

logger = logging.getLogger("skypulse.services.unified_ingestion")


class UnifiedIngestionResult:
    """Outcome payload for a processed canonical event."""

    def __init__(
        self,
        report_id: str,
        tracking_id: str,
        category: str,
        is_india_valid: bool,
        is_quarantined: bool,
        is_duplicate: bool,
        canonical_event_id: Optional[str] = None,
        verification_status: str = "UNVERIFIED",
        confidence_score: float = 0.5,
        status: str = "SUCCESS",
        error: Optional[str] = None,
    ):
        self.report_id = report_id
        self.tracking_id = tracking_id
        self.category = category
        self.is_india_valid = is_india_valid
        self.is_quarantined = is_quarantined
        self.is_duplicate = is_duplicate
        self.canonical_event_id = canonical_event_id
        self.verification_status = verification_status
        self.confidence_score = confidence_score
        self.status = status
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "tracking_id": self.tracking_id,
            "category": self.category,
            "is_india_valid": self.is_india_valid,
            "is_quarantined": self.is_quarantined,
            "is_duplicate": self.is_duplicate,
            "canonical_event_id": self.canonical_event_id,
            "verification_status": self.verification_status,
            "confidence_score": self.confidence_score,
            "status": self.status,
            "error": self.error,
        }


class UnifiedIngestionPipelineService:
    """
    Unified end-to-end ingestion pipeline coordinator.
    Processes raw events through normalization, validation, AI classification,
    deduplication, multi-source verification, DWEG, and real-time distribution.
    """

    def __init__(self):
        self._classifier = EventClassifier()
        self._nlp_extractor = NLPExtractor()
        self._image_analyzer = ImageAnalyzer()
        self._verification_engine = VerificationEngine()
        self._anomaly_detector = AnomalyDetector()

    async def ingest_canonical_event(
        self,
        raw_event: CanonicalRawEvent,
        db: AsyncSession,
        ingestion_run_id: Optional[str] = None,
    ) -> UnifiedIngestionResult:
        """
        Executes complete unified pipeline for a single CanonicalRawEvent.
        Guarantees isolation: single record failures do not crash the batch.
        """
        try:
            # 1. Normalization & Spatial Validation
            norm = await normalize_raw_event(raw_event)

            # Check / resolve source entity in DB
            source_uuid = await self._resolve_source_id(norm.source_id, norm.source_type, norm.is_demo, db)

            # Build Point geometry only if genuine coordinates provided
            point_geom = None
            if norm.latitude is not None and norm.longitude is not None:
                point_geom = WKTElement(f"POINT({norm.longitude} {norm.latitude})", srid=4326)

            # Extract raw media URLs from media items
            media_urls = [m.url for m in norm.media if m.url]

            # 1b. Exact Article Idempotency Check: Prevent duplicate reports and events
            if norm.idempotency_key or norm.external_id:
                cutoff_recent = datetime.now(timezone.utc) - timedelta(hours=48)
                rep_res = await db.execute(
                    select(WeatherReport)
                    .where(WeatherReport.ingested_at >= cutoff_recent)
                    .order_by(WeatherReport.ingested_at.desc())
                    .limit(200)
                )
                for existing_r in rep_res.scalars().all():
                    emeta = existing_r.metadata_ or {}
                    match_idemp = norm.idempotency_key and emeta.get("idempotency_key") == norm.idempotency_key
                    match_ext = norm.external_id and emeta.get("external_id") == norm.external_id
                    if match_idemp or match_ext:
                        if existing_r.canonical_event_id:
                            ev_res = await db.execute(
                                select(WeatherEvent).where(WeatherEvent.id == existing_r.canonical_event_id)
                            )
                            ev_obj = ev_res.scalar_one_or_none()
                            if ev_obj:
                                ev_obj.last_seen_at = datetime.now(timezone.utc)
                                await db.commit()

                        return UnifiedIngestionResult(
                            report_id=str(existing_r.id),
                            tracking_id=norm.tracking_id,
                            category=existing_r.primary_category or norm.primary_category,
                            is_india_valid=True,
                            is_quarantined=False,
                            is_duplicate=True,
                            canonical_event_id=str(existing_r.canonical_event_id) if existing_r.canonical_event_id else None,
                            status="SUCCESS",
                        )

            # 2. Persist WeatherReport in PostgreSQL
            report = WeatherReport(
                id=uuid.UUID(norm.ingestion_id),
                ingested_at=norm.ingested_at,
                source_id=source_uuid,
                raw_content=norm.text,
                normalized_text=norm.text,
                primary_category=norm.primary_category,
                severity=norm.severity,
                classification_confidence=0.5 if norm.primary_category == "UNKNOWN" else 0.8,
                classification_method="CONNECTOR_RULE",
                location_point=point_geom,
                location_lat=norm.latitude,
                location_lon=norm.longitude,
                location_city=norm.city,
                location_district=norm.district,
                location_state=norm.state,
                location_confidence=norm.location_confidence,
                event_time=norm.observed_at,
                is_duplicate=norm.is_duplicate,
                status=ReportStatus.PENDING.value,
                is_demo=norm.is_demo,
                metadata_={
                    "tracking_id": norm.tracking_id,
                    "idempotency_key": norm.idempotency_key,
                    "external_id": norm.external_id,
                    "ingestion_run_id": ingestion_run_id or raw_event.raw_payload.get("ingestion_run_id"),
                    "source_family": raw_event.raw_payload.get("source_family"),
                    "raw_payload": norm.metadata.get("raw_payload", {}),
                    "media_urls": media_urls,
                },
            )
            db.add(report)
            await db.flush()

            # If foreign quarantined or non-weather, keep in DB as audit but skip canonical event creation
            if norm.is_quarantined and not norm.is_india_valid:
                report.status = ReportStatus.FAILED.value
                await db.commit()
                return UnifiedIngestionResult(
                    report_id=str(report.id),
                    tracking_id=norm.tracking_id,
                    category=norm.primary_category,
                    is_india_valid=False,
                    is_quarantined=True,
                    is_duplicate=norm.is_duplicate,
                    status="QUARANTINED",
                )

            # 3. AI Pipeline & Canonical Event Association
            canonical_event = await self.process_report_ai(report=report, db=db)

            await db.commit()

            return UnifiedIngestionResult(
                report_id=str(report.id),
                tracking_id=norm.tracking_id,
                category=report.primary_category,
                is_india_valid=norm.is_india_valid,
                is_quarantined=norm.is_quarantined,
                is_duplicate=report.is_duplicate,
                canonical_event_id=str(canonical_event.id) if canonical_event else None,
                verification_status=canonical_event.verification_status if canonical_event else "UNVERIFIED",
                confidence_score=canonical_event.confidence_score if canonical_event else 0.5,
                status="SUCCESS",
            )

        except Exception as exc:
            logger.exception("Unified ingestion pipeline error on event '%s': %s", raw_event.ingestion_id, exc)
            return UnifiedIngestionResult(
                report_id=raw_event.ingestion_id,
                tracking_id="SP-FAILED",
                category="UNKNOWN",
                is_india_valid=False,
                is_quarantined=False,
                is_duplicate=False,
                status="ERROR",
                error=str(exc),
            )

    async def process_report_ai(
        self,
        report: WeatherReport,
        db: AsyncSession,
    ) -> WeatherEvent:
        """
        Processes an existing WeatherReport through AI classification, NLP extraction,
        dense semantic embedding, Deduplication, Verification, Event DNA, DWEG,
        and real-time WebSocket broadcast.
        """
        report.status = ReportStatus.PROCESSING.value
        await db.flush()

        # 1. Source Trust Context
        src_res = await db.execute(select(Source).where(Source.id == report.source_id))
        source = src_res.scalar_one_or_none()
        src_trust = source.trust_score if source else 0.50
        src_type = source.source_type if source else "UNKNOWN"
        src_name = source.name if source else "Unknown Source"

        text = report.normalized_text or report.raw_content or ""

        # 1b. National Weather Relevance Gating & False Positive Protection
        from connectors.weather_relevance_engine import WeatherRelevanceEngine, IncidentNature
        meta_dict = report.metadata_ if isinstance(report.metadata_, dict) else {}
        raw_p = meta_dict.get("raw_payload", {}) if isinstance(meta_dict, dict) else {}
        article_title = raw_p.get("title")

        relevance_assessment = WeatherRelevanceEngine.evaluate(
            text=text,
            title=article_title,
            source_name=src_name,
            source_type=src_type,
            claimed_category=report.primary_category,
            has_gps=bool(report.location_lat and report.location_lon),
        )

        if not relevance_assessment.is_relevant:
            logger.info(
                "Report %s gated as non-weather/drill: %s (Reason: %s)",
                report.id, relevance_assessment.incident_nature.value, relevance_assessment.rejection_reason
            )
            report.status = ReportStatus.FAILED.value
            if isinstance(report.metadata_, dict):
                report.metadata_["gating_rejection"] = relevance_assessment.to_dict()
            await db.flush()
            return None

        # 2. Event Classification
        classification = await self._classifier.classify(
            text, metadata={"suggested_category": relevance_assessment.primary_category or report.primary_category}
        )
        report.primary_category = classification.category
        report.sub_category = classification.sub_category
        report.severity = classification.severity
        report.classification_confidence = classification.confidence
        report.classification_method = classification.method

        # If gated from cyclone or ungrounded
        if report.primary_category == "CYCLONE" and not relevance_assessment.is_cyclone_rigorous:
            report.primary_category = relevance_assessment.primary_category

        if isinstance(report.metadata_, dict):
            report.metadata_["incident_nature"] = relevance_assessment.incident_nature.value
            report.metadata_["relevance_assessment"] = relevance_assessment.to_dict()

        # 3. NLP Entity & Meteorological Extraction
        extraction = await self._nlp_extractor.extract(text)
        report.ai_extraction = extraction.model_dump(mode="json")

        # Enrich location if missing but NLP extracted with high confidence
        if not report.location_city and extraction.resolved_city:
            report.location_city = extraction.resolved_city
            report.location_district = extraction.resolved_district
            report.location_state = extraction.resolved_state
            if not report.location_lat and extraction.resolved_lat:
                report.location_lat = extraction.resolved_lat
                report.location_lon = extraction.resolved_lon
                report.location_point = WKTElement(
                    f"POINT({extraction.resolved_lon} {extraction.resolved_lat})", srid=4326
                )

        # 4. Dense Semantic Embedding Generation
        embedding = await ml_inference_service.generate_embedding(text)
        report.text_embedding = embedding

        # 5. Media Analysis
        media_urls = (report.metadata_ or {}).get("media_urls", [])
        media_res = await self._image_analyzer.analyze(media_urls, claimed_category=classification.category)

        related_cats = {report.primary_category}
        if report.primary_category in ("FLOODING", "RAINFALL"):
            related_cats.update(["FLOODING", "RAINFALL"])
        elif report.primary_category in ("THUNDERSTORM", "STRONG_WINDS"):
            related_cats.update(["THUNDERSTORM", "STRONG_WINDS", "RAINFALL"])
        elif report.primary_category == "CYCLONE":
            related_cats.update(["CYCLONE", "STRONG_WINDS", "RAINFALL", "FLOODING"])

        active_events_q = (
            select(WeatherEvent)
            .where(
                WeatherEvent.is_active == True,
                WeatherEvent.is_deleted == False,
            )
        )
        if report.primary_category and report.primary_category != "UNKNOWN":
            active_events_q = active_events_q.where(
                or_(
                    WeatherEvent.category.in_(list(related_cats)),
                    WeatherEvent.category == "UNKNOWN",
                )
            )
        if report.location_state:
            active_events_q = active_events_q.where(
                or_(
                    WeatherEvent.primary_state.ilike(f"%{report.location_state}%"),
                    WeatherEvent.primary_state.is_(None),
                )
            )

        active_events_q = active_events_q.order_by(WeatherEvent.last_updated_at.desc()).limit(50)
        evt_res = await db.execute(active_events_q)
        active_events = evt_res.scalars().all()

        report_dict = {
            "id": str(report.id),
            "text": text,
            "primary_category": report.primary_category,
            "latitude": report.location_lat,
            "longitude": report.location_lon,
            "state": report.location_state,
            "district": report.location_district,
            "city": report.location_city,
            "event_time": report.event_time or report.ingested_at,
            "idempotency_key": (report.metadata_ or {}).get("idempotency_key"),
            "phash": media_res.phash,
            "embedding": embedding,
        }

        matched_canonical_event: Optional[WeatherEvent] = None
        dup_eval = None

        for cand_event in active_events:
            # Query candidate event's primary report text & idempotency for precise matching
            cand_rep_q = (
                select(WeatherReport.normalized_text, WeatherReport.raw_content, WeatherReport.metadata_)
                .where(WeatherReport.canonical_event_id == cand_event.id)
                .order_by(WeatherReport.ingested_at.asc())
                .limit(1)
            )
            cand_rep_res = await db.execute(cand_rep_q)
            cand_rep_row = cand_rep_res.first()
            cand_text = ""
            cand_idemp = None
            if cand_rep_row:
                cand_text = cand_rep_row[0] or cand_rep_row[1] or ""
                cand_m = cand_rep_row[2] or {}
                cand_idemp = cand_m.get("idempotency_key")

            cand_dict = {
                "id": str(cand_event.id),
                "canonical_event_id": str(cand_event.id),
                "category": cand_event.category,
                "latitude": cand_event.centroid_lat,
                "longitude": cand_event.centroid_lon,
                "state": cand_event.primary_state,
                "district": cand_event.primary_district,
                "city": cand_event.primary_city,
                "event_time": cand_event.last_updated_at,
                "text": cand_text,
                "idempotency_key": cand_idemp,
            }
            cand_eval = DeduplicationEngine.evaluate_candidate(report_dict, cand_dict)
            if cand_eval.is_duplicate or cand_eval.verdict in ("EXACT_DUPLICATE", "NEAR_DUPLICATE"):
                matched_canonical_event = cand_event
                dup_eval = cand_eval
                break

        canonical_event: WeatherEvent

        if matched_canonical_event:
            # Corroborating duplicate assigned to existing canonical event
            canonical_event = matched_canonical_event
            report.is_duplicate = True
            report.canonical_event_id = canonical_event.id

            canonical_event.evidence_count += 1
            now_utc = datetime.now(timezone.utc)
            rep_time = report.event_time or now_utc
            if canonical_event.last_updated_at.tzinfo is None:
                canonical_event.last_updated_at = canonical_event.last_updated_at.replace(tzinfo=timezone.utc)
            if rep_time.tzinfo is None:
                rep_time = rep_time.replace(tzinfo=timezone.utc)
            if rep_time > canonical_event.last_updated_at:
                canonical_event.last_updated_at = rep_time

            canonical_event.last_seen_at = now_utc
            canonical_event.expires_at = calculate_event_expiry(
                canonical_event.category, canonical_event.last_updated_at, canonical_event.severity
            )
            canonical_event.lifecycle_status = EventLifecycleStatus.ACTIVE.value
            if report.location_lat and report.location_lon and canonical_event.centroid_lat:
                canonical_event.centroid_lat = round((canonical_event.centroid_lat + report.location_lat) / 2.0, 4)
                canonical_event.centroid_lon = round((canonical_event.centroid_lon + report.location_lon) / 2.0, 4)
                canonical_event.centroid_point = WKTElement(
                    f"POINT({canonical_event.centroid_lon} {canonical_event.centroid_lat})", srid=4326
                )

            evidence = EventEvidence(
                canonical_event_id=canonical_event.id,
                weather_report_id=report.id,
                corroboration_score=dup_eval.similarity_score if dup_eval else 0.8,
                corroboration_type=CorroborationType.CORROBORATING.value,
            )
            db.add(evidence)
        else:
            # Create new Canonical WeatherEvent
            point_geom = None
            if report.location_lat and report.location_lon:
                point_geom = WKTElement(f"POINT({report.location_lon} {report.location_lat})", srid=4326)

            now_utc = datetime.now(timezone.utc)
            obs_dt = report.event_time or now_utc
            expires_at = calculate_event_expiry(
                report.primary_category or "UNKNOWN", obs_dt, report.severity or 2
            )

            canonical_event = WeatherEvent(
                id=uuid.uuid4(),
                category=report.primary_category or "UNKNOWN",
                sub_category=report.sub_category,
                severity=report.severity or 2,
                confidence_score=report.classification_confidence or 0.6,
                verification_status=VerificationStatus.UNVERIFIED.value,
                centroid_point=point_geom,
                centroid_lat=report.location_lat,
                centroid_lon=report.location_lon,
                primary_state=report.location_state,
                primary_district=report.location_district,
                primary_city=report.location_city,
                first_reported_at=obs_dt,
                observed_at=obs_dt,
                ingested_at=now_utc,
                last_seen_at=now_utc,
                last_updated_at=obs_dt,
                expires_at=expires_at,
                lifecycle_status=EventLifecycleStatus.ACTIVE.value,
                evidence_count=1,
                is_demo=report.is_demo,
                is_active=True,
            )
            db.add(canonical_event)
            await db.flush()

            report.is_duplicate = False
            report.canonical_event_id = canonical_event.id

            evidence = EventEvidence(
                canonical_event_id=canonical_event.id,
                weather_report_id=report.id,
                corroboration_score=1.0,
                corroboration_type=CorroborationType.PRIMARY.value,
            )
            db.add(evidence)

        # 7. Verification & Corroboration Engine
        nearby_reports = [
            {"report_id": str(report.id), "category": report.primary_category}
            for _ in range(max(0, canonical_event.evidence_count - 1))
        ]
        verification_verdict = await self._verification_engine.verify_report(
            report_data=report_dict,
            nearby_reports=nearby_reports,
            source_trust=src_trust,
            media_analysis=media_res,
        )

        status_db = verification_verdict.verification_status
        if status_db == "INSUFFICIENT_EVIDENCE" or status_db not in [s.value for s in VerificationStatus]:
            status_db = VerificationStatus.UNVERIFIED.value

        canonical_event.verification_status = status_db

        # Persist or update VerificationResult
        vr_query = select(VerificationResult).where(VerificationResult.canonical_event_id == canonical_event.id)
        vr_res = await db.execute(vr_query)
        vr_record = vr_res.scalar_one_or_none()

        if not vr_record:
            vr_record = VerificationResult(
                canonical_event_id=canonical_event.id,
                status=status_db,
                confidence_score=verification_verdict.verification_confidence,
                explanation_text=verification_verdict.explanation,
                evidence_items=verification_verdict.evidence_summary,
                signal_scores=verification_verdict.signal_scores,
            )
            db.add(vr_record)
        else:
            vr_record.status = status_db
            vr_record.confidence_score = verification_verdict.verification_confidence
            vr_record.explanation_text = verification_verdict.explanation
            vr_record.evidence_items = verification_verdict.evidence_summary
            vr_record.signal_scores = verification_verdict.signal_scores

        # 8. Anomaly Detection
        anomaly_result = await self._anomaly_detector.evaluate_report(
            category=canonical_event.category,
            severity=canonical_event.severity,
            city=canonical_event.primary_city,
            district=canonical_event.primary_district,
            state=canonical_event.primary_state,
            event_time=canonical_event.first_reported_at,
            nearby_events_count=len(nearby_reports),
        )
        canonical_event.is_anomalous = anomaly_result.is_anomalous
        canonical_event.anomaly_z_score = anomaly_result.z_score

        # 9. Confidence Engine
        conf_eval = ConfidenceEngine.calculate_report_confidence(
            classification_conf=report.classification_confidence or 0.6,
            extraction_conf=extraction.confidence,
            source_trust=src_trust,
            corroboration_score=min(1.0, (canonical_event.evidence_count - 1) / 3.0),
            media_conf=media_res.confidence if media_res.has_media else None,
            has_contradictions=(verification_verdict.verification_status == "CONTRADICTED"),
        )
        canonical_event.confidence_score = conf_eval.final_confidence

        # 10. Mark Report PROCESSED
        report.status = ReportStatus.PROCESSED.value
        await db.flush()

        # 11. DWEG Evidence Graph Node & Relationship Updates
        try:
            await ai_dweg_service.upsert_event_node(
                event_id=str(canonical_event.id),
                category=canonical_event.category,
                severity=canonical_event.severity,
                confidence=canonical_event.confidence_score,
                status=canonical_event.verification_status,
                lat=canonical_event.centroid_lat,
                lon=canonical_event.centroid_lon,
                city=canonical_event.primary_city,
            )
            await ai_dweg_service.upsert_report_node(
                report_id=str(report.id),
                source_id=str(report.source_id),
                source_type=src_type,
                category=report.primary_category,
                text=text,
                confidence=conf_eval.final_confidence,
                lat=report.location_lat,
                lon=report.location_lon,
                city=report.location_city,
            )
            await ai_dweg_service.link_report_to_event(
                report_id=str(report.id),
                event_id=str(canonical_event.id),
                corroboration_score=1.0 if not report.is_duplicate else 0.8,
            )

            # Propagation analysis if event has coordinates
            if canonical_event.centroid_lat and canonical_event.centroid_lon:
                await ai_dweg_service.detect_propagation(
                    event_id=str(canonical_event.id),
                    category=canonical_event.category,
                    lat=canonical_event.centroid_lat,
                    lon=canonical_event.centroid_lon,
                    occurred_at=canonical_event.first_reported_at,
                )
        except Exception as dweg_err:
            logger.debug("DWEG graph update non-fatal error: %s", dweg_err)

        # 12. OpenSearch Indexing (Non-blocking)
        try:
            doc = {
                "id": str(report.id),
                "canonical_event_id": str(canonical_event.id),
                "normalized_text": report.normalized_text or report.raw_content,
                "primary_category": report.primary_category,
                "sub_category": report.sub_category,
                "severity": report.severity,
                "location_state": report.location_state,
                "location_district": report.location_district,
                "location_city": report.location_city,
                "location_lat": report.location_lat,
                "location_lon": report.location_lon,
                "event_time": report.event_time.isoformat() if report.event_time else datetime.now(timezone.utc).isoformat(),
                "ingested_at": report.ingested_at.isoformat() if report.ingested_at else datetime.now(timezone.utc).isoformat(),
                "verification_status": canonical_event.verification_status,
                "confidence_score": canonical_event.confidence_score,
                "source_type": src_type,
                "is_demo": report.is_demo,
                "status": report.status,
            }
            await opensearch_indexer.index_report(doc)
        except Exception:
            pass

        # 13. Publish to Kafka / In-Memory Event Bus & WebSocket Broadcast
        now_iso = datetime.now(timezone.utc).isoformat()
        obs_dt = canonical_event.effective_observed_at
        ing_dt = canonical_event.effective_ingested_at
        seen_dt = canonical_event.effective_last_seen_at
        exp_dt = canonical_event.effective_expires_at

        event_dict = {
            "id": str(canonical_event.id),
            "event_id": str(canonical_event.id),
            "report_id": str(report.id),
            "category": canonical_event.category,
            "sub_category": canonical_event.sub_category,
            "severity": canonical_event.severity,
            "confidence": canonical_event.confidence_score,
            "confidence_score": canonical_event.confidence_score,
            "verification_status": canonical_event.verification_status,
            "status": canonical_event.effective_lifecycle_status,
            "lifecycle_status": canonical_event.effective_lifecycle_status,
            "primary_city": canonical_event.primary_city,
            "primary_district": canonical_event.primary_district,
            "primary_state": canonical_event.primary_state,
            "centroid_lat": canonical_event.centroid_lat,
            "centroid_lon": canonical_event.centroid_lon,
            "latitude": canonical_event.centroid_lat,
            "longitude": canonical_event.centroid_lon,
            "location": {
                "state": canonical_event.primary_state,
                "district": canonical_event.primary_district,
                "city": canonical_event.primary_city,
                "lat": canonical_event.centroid_lat,
                "lon": canonical_event.centroid_lon,
            },
            "observed_at": obs_dt.isoformat() if obs_dt else now_iso,
            "ingested_at": ing_dt.isoformat() if ing_dt else now_iso,
            "last_seen_at": seen_dt.isoformat() if seen_dt else now_iso,
            "expires_at": exp_dt.isoformat() if exp_dt else None,
            "first_reported_at": canonical_event.first_reported_at.isoformat() if canonical_event.first_reported_at else now_iso,
            "last_updated_at": canonical_event.last_updated_at.isoformat() if canonical_event.last_updated_at else now_iso,
            "evidence_count": canonical_event.evidence_count,
            "supporting_signal_count": canonical_event.evidence_count,
            "is_anomalous": canonical_event.is_anomalous,
            "is_demo": canonical_event.is_demo,
            "is_active": canonical_event.is_active and (canonical_event.effective_lifecycle_status != "EXPIRED"),
        }

        # Kafka topics
        try:
            await kafka_producer.publish(TOPIC_AI_PROCESSED, event_dict, key=str(canonical_event.id))
            if canonical_event.verification_status in ("VERIFIED", "CONTRADICTED"):
                await kafka_producer.publish(TOPIC_VERIFICATION_UPDATES, event_dict, key=str(canonical_event.id))
            if canonical_event.is_anomalous:
                await kafka_producer.publish(TOPIC_ANOMALIES, event_dict, key=str(canonical_event.id))
        except Exception:
            pass

        # Direct WebSocket fanout to frontend
        try:
            is_new = (canonical_event.evidence_count <= 1 and not report.is_duplicate)
            primary_type = "EVENT_CREATED" if is_new else "EVENT_UPDATED"
            legacy_type = "weather_event.created" if is_new else "weather_event.updated"

            ws_envelope = build_event_envelope(
                event_type=primary_type,
                event_id=str(canonical_event.id),
                data=event_dict,
            )
            ws_envelope["legacy_type"] = legacy_type
            ws_envelope["event"] = event_dict
            ws_envelope["server_time"] = now_iso
            ws_envelope["revision"] = int(datetime.now(timezone.utc).timestamp() * 1000)

            await ws_manager.broadcast(ws_envelope)
            logger.info("Broadcasted %s for event %s (evidence=%d)", primary_type, canonical_event.id, canonical_event.evidence_count)
        except Exception as ws_err:
            logger.debug("WebSocket broadcast non-fatal exception: %s", ws_err)

        return canonical_event

    async def _resolve_source_id(
        self,
        source_id_str: str,
        source_type_str: str,
        is_demo: bool,
        db: AsyncSession,
    ) -> uuid.UUID:
        """Resolves source UUID or creates default Source record if missing with valid DB enum."""
        # 1. Map input string to valid database source_type
        st_clean = str(source_type_str or "WEATHER_API")
        st_upper = st_clean.upper()
        if is_demo or "DEMO" in st_upper:
            db_source_type = SourceType.DEMO.value
        elif "IMD" in st_upper or "GDACS" in st_upper or "GOVERNMENT_API" in st_upper:
            db_source_type = SourceType.GOVERNMENT_API.value
        elif "DATA_GOV" in st_upper or "GOVERNMENT_DATASET" in st_upper:
            db_source_type = SourceType.GOVERNMENT_DATASET.value
        elif "RSS" in st_upper or "NEWS" in st_upper:
            db_source_type = SourceType.RSS_FEED.value
        elif "CITIZEN" in st_upper or "PUBLIC_USER" in st_upper:
            db_source_type = SourceType.CITIZEN.value
        elif "SOCIAL" in st_upper or "SEARCH" in st_upper or "MASTODON" in st_upper or "PUBLIC_DATASET" in st_upper:
            db_source_type = SourceType.PUBLIC_DATASET.value
        else:
            db_source_type = SourceType.WEATHER_API.value

        # 2. Check by source UUID if provided
        try:
            s_uuid = uuid.UUID(str(source_id_str))
            src_res = await db.execute(select(Source).where(Source.id == s_uuid))
            src_obj = src_res.scalar_one_or_none()
            if src_obj:
                return src_obj.id
        except (ValueError, TypeError):
            s_uuid = None

        # 3. Dedicated name-based lookup
        default_name = f"{st_clean.replace('_', ' ').title()} Stream"
        if "00000000-0000-0000-0000-000000000008" in str(source_id_str) or "REGIONAL_RSS" in st_upper:
            default_name = "Regional News RSS Feeds"
            db_source_type = SourceType.RSS_FEED.value
        elif "00000000-0000-0000-0000-000000000003" in str(source_id_str) or "GNEWS" in st_upper:
            default_name = "Google News RSS Discovery"
            db_source_type = SourceType.RSS_FEED.value
        elif "GDACS" in st_upper:
            default_name = "GDACS Tropical Alert Stream"
            db_source_type = SourceType.GOVERNMENT_API.value
        elif "IMD" in st_upper:
            default_name = "IMD Doppler Radar & Synoptic Grid"
            db_source_type = SourceType.GOVERNMENT_API.value

        res = await db.execute(select(Source).where(Source.name == default_name, Source.is_demo == is_demo))
        found = res.scalars().first()
        if found:
            return found.id

        # 4. Fallback search by source type excluding mismatched specific named sources
        if db_source_type == SourceType.RSS_FEED.value and "GDACS" not in default_name:
            res = await db.execute(select(Source).where(
                Source.source_type == db_source_type,
                Source.is_demo == is_demo,
                ~Source.name.ilike("%GDACS%")
            ))
            found_news = res.scalars().first()
            if found_news:
                return found_news.id

        # 5. Create new distinct source
        new_id = s_uuid or uuid.uuid4()
        new_src = Source(
            id=new_id,
            name=default_name,
            source_type=db_source_type,
            connector_class=f"{st_clean}Connector",
            trust_score=0.85 if db_source_type in (SourceType.GOVERNMENT_API.value, SourceType.GOVERNMENT_DATASET.value) else 0.70,
            is_active=True,
            is_demo=is_demo,
        )
        db.add(new_src)
        await db.flush()
        return new_src.id


unified_ingestion_pipeline = UnifiedIngestionPipelineService()
