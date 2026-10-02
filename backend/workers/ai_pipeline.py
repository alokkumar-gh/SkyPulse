"""
SkyPulse AI Intelligence Pipeline Worker
Consumes notifications from 'skypulse.pending_ai'.
Orchestrates:
  1. Event Classification
  2. NLP Entity Extraction
  3. Embedding Generation
  4. Media/Image Analysis
  5. Multi-Level Deduplication & Clustering
  6. Source Trust Scoring
  7. Multi-Source Evidence Verification
  8. Anomaly Detection
  9. Canonical WeatherEvent Creation / Update
  10. DWEG Evidence Graph Update
  11. OpenSearch Indexing
  12. Downstream Publishing (skypulse.ai_processed, skypulse.verification_updates, skypulse.anomalies)
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from geoalchemy2.elements import WKTElement

from app.db.session import async_session_factory
from app.models.weather_report import WeatherReport
from app.models.weather_event import WeatherEvent
from app.models.event_evidence import EventEvidence
from app.models.verification import VerificationResult
from app.models.source import Source
from app.models.enums import ReportStatus, VerificationStatus, CorroborationType

from connectors.kafka_bus import (
    KafkaBusConsumer,
    KafkaBusProducer,
    kafka_producer,
    TOPIC_PENDING_AI,
    TOPIC_AI_PROCESSED,
    TOPIC_VERIFICATION_UPDATES,
    TOPIC_ANOMALIES,
    TOPIC_DEAD_LETTER,
)

from ai.fallback_provider import FallbackAIProvider
from ai.event_classifier import EventClassifier
from ai.nlp_extractor import NLPExtractor
from ai.image_analyzer import ImageAnalyzer
from ai.deduplicator import DeduplicationEngine
from ai.source_trust import SourceTrustEngine
from ai.verification_engine import VerificationEngine
from ai.confidence_engine import ConfidenceEngine
from ai.anomaly_detector import AnomalyDetector
from ai.dweg_service import dweg_service
from ai.opensearch_indexer import opensearch_indexer
from ml.inference_service import ml_inference_service

logger = logging.getLogger("skypulse.ai_pipeline")


async def process_report_ai(
    report_id_str: str,
    db: AsyncSession,
    producer: Optional[KafkaBusProducer] = None,
) -> Optional[WeatherReport]:
    """
    Main AI processing unit for a single WeatherReport.
    Safe, auditable, and non-destructive.
    """
    prod = producer or kafka_producer
    try:
        report_uuid = uuid.UUID(report_id_str)
    except ValueError:
        logger.error("Invalid report UUID: %s", report_id_str)
        return None

    # 1. Fetch Report & Source context
    q = select(WeatherReport).where(WeatherReport.id == report_uuid)
    res = await db.execute(q)
    report = res.scalar_one_or_none()
    if not report:
        logger.warning("Report %s not found for AI processing", report_id_str)
        return None

    report.status = ReportStatus.PROCESSING.value
    await db.flush()

    # Source trust context
    src_res = await db.execute(select(Source).where(Source.id == report.source_id))
    source = src_res.scalar_one_or_none()
    src_trust = source.trust_score if source else 0.50
    src_type = source.source_type if source else "UNKNOWN"

    text = report.normalized_text or report.raw_content or ""

    # 2. Event Classification
    classifier = EventClassifier()
    classification = await classifier.classify(
        text, metadata={"suggested_category": report.primary_category}
    )
    report.primary_category = classification.category
    report.sub_category = classification.sub_category
    report.severity = classification.severity
    report.classification_confidence = classification.confidence
    report.classification_method = classification.method

    # 3. NLP Entity Extraction
    extractor = NLPExtractor()
    extraction = await extractor.extract(text)
    report.ai_extraction = extraction.model_dump(mode="json")

    # Enrich missing location fields if extracted
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

    # 4. Dense Semantic Embedding Generation (384-dimensional)
    embedding = await ml_inference_service.generate_embedding(text)
    report.text_embedding = embedding

    # 5. Media Analysis
    image_analyzer = ImageAnalyzer()
    media_urls = report.metadata_.get("media_urls", [])
    media_res = await image_analyzer.analyze(media_urls, claimed_category=classification.category)

    # 6. Multi-Level Deduplication & Canonical Event Assignment
    # Look for recent active canonical events
    related_cats = {report.primary_category}
    if report.primary_category == "FLOODING":
        related_cats.add("RAINFALL")
    elif report.primary_category == "RAINFALL":
        related_cats.add("FLOODING")

    active_events_q = select(WeatherEvent).where(
        WeatherEvent.is_active == True,
        WeatherEvent.category.in_(list(related_cats)),
    ).order_by(WeatherEvent.last_updated_at.desc()).limit(15)
    evt_res = await db.execute(active_events_q)
    active_events = evt_res.scalars().all()

    report_dict = {
        "id": str(report.id),
        "text": text,
        "primary_category": report.primary_category,
        "latitude": report.location_lat,
        "longitude": report.location_lon,
        "event_time": report.event_time or report.ingested_at,
        "idempotency_key": report.metadata_.get("idempotency_key"),
        "phash": media_res.phash,
        "embedding": embedding,
    }

    matched_canonical_event: Optional[WeatherEvent] = None
    dup_eval = None

    for cand_event in active_events:
        cand_dict = {
            "id": str(cand_event.id),
            "canonical_event_id": str(cand_event.id),
            "category": cand_event.category,
            "latitude": cand_event.centroid_lat,
            "longitude": cand_event.centroid_lon,
            "event_time": cand_event.last_updated_at,
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
        canonical_event.last_updated_at = datetime.now(timezone.utc)
        # Update centroid if coordinates present
        if report.location_lat and report.location_lon and canonical_event.centroid_lat:
            canonical_event.centroid_lat = round((canonical_event.centroid_lat + report.location_lat) / 2.0, 4)
            canonical_event.centroid_lon = round((canonical_event.centroid_lon + report.location_lon) / 2.0, 4)
            canonical_event.centroid_point = WKTElement(
                f"POINT({canonical_event.centroid_lon} {canonical_event.centroid_lat})", srid=4326
            )

        # Register evidence relationship
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
    verifier = VerificationEngine()
    nearby_reports = [
        {"report_id": str(report.id), "category": report.primary_category}
        for _ in range(max(0, canonical_event.evidence_count - 1))
    ]
    verification_verdict = await verifier.verify_report(
        report_data=report_dict,
        nearby_reports=nearby_reports,
        source_trust=src_trust,
        media_analysis=media_res,
    )

    status_db = verification_verdict.verification_status
    if status_db == "INSUFFICIENT_EVIDENCE" or status_db not in [s.value for s in VerificationStatus]:
        status_db = VerificationStatus.UNVERIFIED.value

    canonical_event.verification_status = status_db

    # Persist or update VerificationResult record
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
    detector = AnomalyDetector()
    anomaly_result = await detector.evaluate_report(
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
    await db.commit()
    await db.refresh(report)
    await db.refresh(canonical_event)

    # 11. OpenSearch Indexing (Asynchronous)
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

    # 12. DWEG Evidence Graph Update
    await dweg_service.upsert_event_node(
        event_id=str(canonical_event.id),
        category=canonical_event.category,
        severity=canonical_event.severity,
        confidence=canonical_event.confidence_score,
        status=canonical_event.verification_status,
        lat=canonical_event.centroid_lat,
        lon=canonical_event.centroid_lon,
        city=canonical_event.primary_city,
    )
    await dweg_service.upsert_report_node(
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
    await dweg_service.link_report_to_event(
        report_id=str(report.id),
        event_id=str(canonical_event.id),
        corroboration_score=1.0 if not report.is_duplicate else 0.8,
    )

    # Propagation analysis if event has coordinates
    if canonical_event.centroid_lat and canonical_event.centroid_lon:
        await dweg_service.detect_propagation(
            event_id=str(canonical_event.id),
            category=canonical_event.category,
            lat=canonical_event.centroid_lat,
            lon=canonical_event.centroid_lon,
            occurred_at=canonical_event.first_reported_at,
        )

    # 13. Publish Processed Events to Downstream Topics
    processed_msg = {
        "report_id": str(report.id),
        "canonical_event_id": str(canonical_event.id),
        "category": report.primary_category,
        "severity": report.severity,
        "verification_status": canonical_event.verification_status,
        "confidence": canonical_event.confidence_score,
        "is_anomalous": canonical_event.is_anomalous,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    await prod.publish(TOPIC_AI_PROCESSED, processed_msg, key=str(report.id))

    # Verification updates
    verif_msg = {
        "event_id": str(canonical_event.id),
        "status": canonical_event.verification_status,
        "confidence": canonical_event.confidence_score,
        "explanation": verification_verdict.explanation,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await prod.publish(TOPIC_VERIFICATION_UPDATES, verif_msg, key=str(canonical_event.id))

    # Anomaly notifications
    if canonical_event.is_anomalous:
        anomaly_msg = {
            "event_id": str(canonical_event.id),
            "category": canonical_event.category,
            "z_score": canonical_event.anomaly_z_score,
            "anomaly_type": anomaly_result.anomaly_type,
            "description": anomaly_result.description,
            "city": canonical_event.primary_city,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        await prod.publish(TOPIC_ANOMALIES, anomaly_msg, key=str(canonical_event.id))

    # 14. Real-Time Event DNA Update Notification
    try:
        from app.services.event_dna_service import event_dna_service
        await event_dna_service.publish_dna_update_event(
            event_id=str(canonical_event.id),
            changed_fields=["confidence_score", "evidence_count", "verification_status"],
            confidence=canonical_event.confidence_score,
            evidence_coverage=min(1.0, 0.4 + 0.15 * canonical_event.evidence_count),
            event_type=canonical_event.category,
        )
    except Exception as e:
        logger.debug("Failed to emit DNA update notification: %s", e)

    # 15. Real-Time Emerging Event Hook
    try:
        from app.services.emerging_event_service import emerging_event_service
        from app.models.enums import EmergenceState
        emerging_clusters = await emerging_event_service.detect_emerging_events(
            db=db,
            lookback_minutes=60,
            category=canonical_event.category,
        )
        for emg in emerging_clusters:
            if emg.state in {EmergenceState.DEVELOPING, EmergenceState.EMERGING}:
                await emerging_event_service.broadcast_emerging_event(emg, event_subtype=emg.state.value.lower())
    except Exception as e:
        logger.debug("Emerging event evaluation hook non-fatal warning: %s", e)

    return report


class AIPipelineWorker:
    """
    Subscribes to 'skypulse.pending_ai' and executes the AI pipeline.
    """

    def __init__(self, group_id: str = "skypulse_ai_workers"):
        self.group_id = group_id
        self.consumer = KafkaBusConsumer(
            topic=TOPIC_PENDING_AI,
            group_id=self.group_id,
            dead_letter_topic=TOPIC_DEAD_LETTER,
            max_retries=3,
        )

    async def start(self) -> None:
        await self.consumer.start()
        await dweg_service.initialize()
        logger.info("AIPipelineWorker started listening on '%s'", TOPIC_PENDING_AI)

    async def stop(self) -> None:
        await self.consumer.stop()
        await dweg_service.close()
        logger.info("AIPipelineWorker stopped")

    async def step(self, timeout_seconds: float = 1.0) -> bool:
        """Consume and process one message from pending_ai."""
        async def _handler(msg: Dict[str, Any]):
            report_id = msg.get("report_id")
            if not report_id:
                raise ValueError("Message missing report_id")

            async with async_session_factory() as db:
                await process_report_ai(report_id, db=db)

        return await self.consumer.consume_one(_handler, timeout_seconds=timeout_seconds)
