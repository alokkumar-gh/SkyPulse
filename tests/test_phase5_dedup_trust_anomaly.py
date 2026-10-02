"""
SkyPulse Phase 5 Tests — Deduplication, Source Trust, Anomaly Detection & Confidence
Tests 4-level deduplication, dynamic source trust updates, multi-factor anomaly detection,
and explainable confidence calculation.
"""

import pytest
from datetime import datetime, timezone, timedelta

from ai.deduplicator import DeduplicationEngine, cosine_similarity, haversine_distance_km
from ai.source_trust import SourceTrustEngine
from ai.confidence_engine import ConfidenceEngine
from ai.anomaly_detector import AnomalyDetector
from ai.verification_engine import VerificationEngine
from ai.fallback_provider import FallbackAIProvider


@pytest.mark.asyncio
async def test_deduplication_exact_idempotency_hash():
    """Level 1: Exact duplicate identified via idempotency hash."""
    rep1 = {
        "id": "rep-001",
        "text": "Waterlogging in Hindmata",
        "idempotency_key": "sha256_hash_12345",
        "latitude": 19.0067,
        "longitude": 72.8427,
    }
    rep2 = {
        "id": "rep-002",
        "text": "Waterlogging in Hindmata Mumbai",
        "idempotency_key": "sha256_hash_12345",
        "latitude": 19.0067,
        "longitude": 72.8427,
    }

    eval_res = DeduplicationEngine.evaluate_candidate(rep1, rep2)
    assert eval_res.verdict == "EXACT_DUPLICATE"
    assert eval_res.is_duplicate is True
    assert eval_res.similarity_score == 1.0
    assert eval_res.level_matched == "IDEMPOTENCY_HASH"


@pytest.mark.asyncio
async def test_deduplication_near_duplicate_spatiotemporal():
    """Level 3: Same category within 15km and 2 hours is classified as NEAR_DUPLICATE."""
    now = datetime.now(timezone.utc)
    rep1 = {
        "id": "rep-101",
        "text": "Torrential rain in Dadar, roads flooded",
        "primary_category": "FLOODING",
        "latitude": 19.0178,
        "longitude": 72.8478,
        "event_time": now,
    }
    # Candidate in Parel (2.5 km away, 45 mins earlier)
    candidate = {
        "id": "rep-102",
        "text": "Heavy water accumulation around Parel flyover",
        "category": "FLOODING",
        "latitude": 18.9982,
        "longitude": 72.8364,
        "event_time": now - timedelta(minutes=45),
        "canonical_event_id": "evt-mumbai-flood-1",
    }

    eval_res = DeduplicationEngine.evaluate_candidate(rep1, candidate)
    assert eval_res.verdict in ("NEAR_DUPLICATE", "RELATED_REPORT")
    assert eval_res.spatial_distance_km is not None
    assert eval_res.spatial_distance_km <= 5.0
    assert eval_res.time_delta_hours <= 1.0


@pytest.mark.asyncio
async def test_deduplication_unique_unrelated_reports():
    """Reports separated by geography or event category are marked UNIQUE."""
    now = datetime.now(timezone.utc)
    rep_delhi = {
        "id": "rep-delhi",
        "text": "Dense fog in Delhi",
        "primary_category": "FOG",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "event_time": now,
    }
    rep_chennai = {
        "id": "rep-chennai",
        "text": "Severe cyclone winds in Chennai",
        "primary_category": "STRONG_WINDS",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "event_time": now,
    }

    eval_res = DeduplicationEngine.evaluate_candidate(rep_delhi, rep_chennai)
    assert eval_res.verdict == "UNIQUE"
    assert eval_res.is_duplicate is False
    assert eval_res.spatial_distance_km > 1000.0


@pytest.mark.asyncio
async def test_dense_semantic_embedding_cosine_similarity():
    """Verify 384-dimensional dense embeddings produce high cosine similarity for related texts."""
    provider = FallbackAIProvider()

    v1 = await provider.generate_embedding("Heavy monsoon rainfall and street flooding in Mumbai")
    v2 = await provider.generate_embedding("Severe waterlogging and continuous rain in Mumbai city")
    v3 = await provider.generate_embedding("Extreme scorching heatwave and dry winds in Rajasthan desert")

    assert len(v1) == 384
    assert len(v2) == 384

    sim_related = cosine_similarity(v1, v2)
    sim_unrelated = cosine_similarity(v1, v3)

    assert sim_related > sim_unrelated
    assert sim_related >= 0.50


@pytest.mark.asyncio
async def test_source_trust_dynamic_scoring():
    """Verify source trust initial scores and dynamic evolution based on verification outcomes."""
    # 1. Initial trust by source type
    gov_trust = SourceTrustEngine.calculate_initial_trust("GOVERNMENT_API")
    citizen_trust = SourceTrustEngine.calculate_initial_trust("CITIZEN")
    anon_trust = SourceTrustEngine.calculate_initial_trust("ANONYMOUS")

    assert gov_trust >= 0.85
    assert citizen_trust >= 0.50
    assert citizen_trust > anon_trust

    # 2. Dynamic adjustment: VERIFIED outcome increases trust
    eval_verified = SourceTrustEngine.update_trust(
        current_score=citizen_trust,
        outcome="VERIFIED",
        total_reports=5,
        verified_count=4,
    )
    assert eval_verified.source_trust_score > citizen_trust
    assert eval_verified.trust_level in ("HIGH", "MODERATE")

    # 3. Dynamic adjustment: CONTRADICTED outcome lowers trust without zeroing out
    eval_contradicted = SourceTrustEngine.update_trust(
        current_score=citizen_trust,
        outcome="CONTRADICTED",
        total_reports=5,
        contradicted_count=2,
    )
    assert eval_contradicted.source_trust_score < citizen_trust
    assert eval_contradicted.source_trust_score >= 0.10


@pytest.mark.asyncio
async def test_evidence_verification_engine():
    """Verify multi-source evidence verification: corroborated vs contradicted vs insufficient."""
    verifier = VerificationEngine()

    rep = {"primary_category": "FLOODING"}

    # 1. Corroborated with official data and nearby reports -> VERIFIED
    verdict_verified = await verifier.verify_report(
        report_data=rep,
        official_data={"category": "FLOODING"},
        nearby_reports=[{"id": "r1"}, {"id": "r2"}, {"id": "r3"}],
        source_trust=0.85,
    )
    assert verdict_verified.verification_status == "VERIFIED"
    assert verdict_verified.verification_confidence >= 0.75
    assert verdict_verified.evidence_count >= 4

    # 2. Official contradiction with zero nearby corroborations -> CONTRADICTED
    verdict_contradicted = await verifier.verify_report(
        report_data=rep,
        official_data={"category": "CLEAR_SKY"},
        nearby_reports=[],
        source_trust=0.30,
    )
    assert verdict_contradicted.verification_status == "CONTRADICTED"

    # 3. Insufficient evidence -> INSUFFICIENT_EVIDENCE
    verdict_insufficient = await verifier.verify_report(
        report_data=rep,
        official_data=None,
        nearby_reports=[],
        source_trust=0.40,
    )
    assert verdict_insufficient.verification_status == "INSUFFICIENT_EVIDENCE"
    assert verdict_insufficient.evidence_count == 1


@pytest.mark.asyncio
async def test_confidence_engine_components_and_penalty():
    """Verify confidence model computes 0.0-1.0 score and stores component breakdown."""
    conf = ConfidenceEngine.calculate_report_confidence(
        classification_conf=0.90,
        extraction_conf=0.85,
        source_trust=0.80,
        corroboration_score=0.75,
        spatial_consistency=0.90,
        temporal_consistency=0.95,
        media_conf=0.80,
        has_contradictions=False,
    )

    assert 0.75 <= conf.final_confidence <= 0.99
    assert conf.components.classification == 0.90
    assert conf.components.contradiction_penalty == 0.0

    # With contradiction penalty
    conf_penalized = ConfidenceEngine.calculate_report_confidence(
        classification_conf=0.90,
        extraction_conf=0.85,
        source_trust=0.80,
        corroboration_score=0.75,
        has_contradictions=True,
    )
    assert conf_penalized.final_confidence < conf.final_confidence
    assert conf_penalized.components.contradiction_penalty == 0.35


@pytest.mark.asyncio
async def test_anomaly_detection_temporal_and_volume_burst():
    """Verify anomaly detector detects unseasonal events and volume bursts."""
    detector = AnomalyDetector()

    # Temporal anomaly: Heatwave in January
    jan_date = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    res_unseasonal = await detector.evaluate_report(
        category="HEATWAVE",
        severity=3,
        city="Shimla",
        event_time=jan_date,
    )
    assert res_unseasonal.is_anomalous is True
    assert res_unseasonal.anomaly_type == "TEMPORAL"
    assert res_unseasonal.z_score >= 2.0

    # Volume burst anomaly (> 15 reports from single source in rapid succession)
    res_burst = await detector.evaluate_report(
        category="RAINFALL",
        severity=2,
        city="Mumbai",
        recent_same_source_count=18,
    )
    assert res_burst.is_anomalous is True
    assert res_burst.anomaly_type == "VOLUME_BURST"
    assert res_burst.anomaly_score >= 0.80
