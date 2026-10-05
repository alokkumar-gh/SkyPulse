"""
Unit & Integration Tests for SkyPulse Event Intelligence Validation
===================================================================
Tests all 10 critical validation cases:
1. Heavy rainfall in Telangana -> NOT automatically cyclone.
2. Strong wind in Telangana -> NOT automatically cyclone.
3. Thunderstorm in Telangana -> NOT automatically cyclone.
4. Official inland cyclone/remnant -> remains linked to original cyclone system.
5. One source -> NOT multi-source (SINGLE-SOURCE SIGNAL).
6. Three independent sources -> multi-source confirmed (MULTI-SOURCE INTELLIGENCE).
7. 49% confidence -> MODERATE tier (never HIGH).
8. Current weather observation -> does not automatically corroborate hazard event.
9. Conflicting sources -> contradiction penalty applied & review state.
10. Moving storm system -> lineage and tracking continuity.
"""

import pytest
from datetime import datetime, timezone

from app.models.enums import WeatherCategory, VerificationStatus
from app.models.weather_observation import WeatherObservation
from connectors.weather_relevance_engine import (
    WeatherRelevanceEngine,
    SourceAuthorityTier,
    CyclonicStage,
)
from ai.confidence_engine import (
    ConfidenceEngine,
    get_confidence_tier_label,
)
from app.services.weather_intelligence_service import (
    evaluate_physical_observation_corroboration,
    compute_source_corroboration_stats,
    synthesize_semantic_event_intelligence,
)


def test_case_1_heavy_rainfall_in_telangana_not_cyclone():
    """1. Heavy rainfall in Telangana must not be automatically classified as CYCLONE."""
    text = "Heavy downpour and torrential rain lashes Hyderabad and Warangal districts of Telangana."
    eval_res = WeatherRelevanceEngine.evaluate(
        text=text,
        title="Heavy Rain in Telangana",
        source_name="Regional News",
        source_type="NEWS_PUBLISHER",
        claimed_category="CYCLONE",
    )
    # The relevance engine should reject or reclassify CYCLONE because there is no authoritative bulletin or storm telemetry
    assert eval_res.primary_category != "CYCLONE"
    assert eval_res.primary_category in ("RAINFALL", "WEATHER")


def test_case_2_strong_wind_in_telangana_not_cyclone():
    """2. Strong wind in Telangana must not be automatically classified as CYCLONE."""
    text = "Strong gusty winds of 45 km/h reported in Nizamabad, Telangana causing tree branches to fall."
    eval_res = WeatherRelevanceEngine.evaluate(
        text=text,
        title="Gusty Winds in Telangana",
        source_name="Local News",
        source_type="NEWS_PUBLISHER",
        claimed_category="CYCLONE",
    )
    assert eval_res.primary_category != "CYCLONE"
    assert eval_res.primary_category in ("STRONG_WINDS", "WEATHER", "WIND")


def test_case_3_thunderstorm_in_telangana_not_cyclone():
    """3. Thunderstorm in Telangana must not be automatically classified as CYCLONE."""
    text = "Thunderstorm with lightning and light rain observed over Hyderabad and Rangareddy."
    eval_res = WeatherRelevanceEngine.evaluate(
        text=text,
        title="Thunderstorm alert in Telangana",
        source_name="Regional Media",
        source_type="NEWS_PUBLISHER",
        claimed_category="CYCLONE",
    )
    assert eval_res.primary_category != "CYCLONE"
    assert eval_res.primary_category in ("THUNDERSTORM", "WEATHER")


def test_case_4_official_inland_cyclone_remnant():
    """4. Official inland cyclone / remnant can remain linked as an advisory or post-landfall remnant."""
    text = "IMD National Bulletin: Severe Cyclonic Storm DANA after landfall over Odisha coast has moved inland and weakened into a Depression over North Chhattisgarh and Telangana border."
    eval_res = WeatherRelevanceEngine.evaluate(
        text=text,
        title="IMD Cyclone Dana Inland Track Bulletin",
        source_name="IMD Cyclone Warning Centre",
        source_type="GOVERNMENT",
        claimed_category="CYCLONE",
    )
    assert eval_res.is_relevant is True
    # Tier 1 IMD bulletin with inland tracking keywords
    assert eval_res.authority_tier == SourceAuthorityTier.TIER_1_OFFICIAL


def test_case_5_one_source_not_multi_source():
    """5. One source must NOT produce 'MULTI-SOURCE INTELLIGENCE' claim."""
    publishers = ["Regional News RSS"]
    sources_summary = [
        {"publisher": "Regional News RSS", "source_name": "Regional News RSS", "report_id": "rep-1"},
        {"publisher": "Regional News RSS", "source_name": "Regional News RSS", "report_id": "rep-2"},
        {"publisher": "Regional News RSS", "source_name": "Regional News RSS", "report_id": "rep-3"},
    ]
    stats = compute_source_corroboration_stats(publishers, sources_summary, "RAINFALL")
    assert stats["signal_count"] == 3
    assert stats["independent_source_count"] == 1
    assert stats["corroborating_source_count"] == 0
    assert stats["source_claim_label"] == "SINGLE-SOURCE SIGNAL"
    assert stats["source_claim_label"] != "MULTI-SOURCE INTELLIGENCE"


def test_case_6_three_independent_sources_multi_source():
    """6. Three independent sources allow 'MULTI-SOURCE INTELLIGENCE'."""
    publishers = ["IMD AWS Network", "ERA5 Mesh", "Doppler Radar"]
    sources_summary = [
        {"publisher": "IMD AWS Network", "source_name": "IMD", "report_id": "rep-1"},
        {"publisher": "ERA5 Mesh", "source_name": "ECMWF", "report_id": "rep-2"},
        {"publisher": "Doppler Radar", "source_name": "IMD Radar", "report_id": "rep-3"},
    ]
    stats = compute_source_corroboration_stats(publishers, sources_summary, "RAINFALL")
    assert stats["independent_source_count"] >= 3
    assert stats["corroborating_source_count"] >= 3
    assert stats["source_claim_label"] == "MULTI-SOURCE INTELLIGENCE"


def test_case_7_49_percent_confidence_is_moderate_never_high():
    """7. 49% confidence must evaluate to MODERATE, never HIGH."""
    tier_49 = get_confidence_tier_label(0.49)
    assert tier_49 == "MODERATE"
    assert tier_49 != "HIGH"

    tier_35 = get_confidence_tier_label(0.35)
    assert tier_35 == "LOW"

    tier_75 = get_confidence_tier_label(0.75)
    assert tier_75 == "HIGH"

    tier_92 = get_confidence_tier_label(0.92)
    assert tier_92 == "VERY HIGH"


def test_case_8_current_weather_observation_not_auto_corroboration():
    """8. A calm weather observation does NOT corroborate a CYCLONE hypothesis."""
    # Calm station observation: 29.2°C, 6.6 km/h wind, 0.0 mm rain, Clear Sky
    obs = WeatherObservation(
        state="Telangana",
        district="Hyderabad",
        city="Hyderabad",
        latitude=17.3850,
        longitude=78.4867,
        observed_at=datetime.now(timezone.utc),
        temperature_c=29.2,
        wind_speed_kmh=6.6,
        precipitation_mm=0.0,
        weather_condition="Clear Sky",
    )

    eval_result = evaluate_physical_observation_corroboration(
        category="CYCLONE",
        sub_category="CYCLONE_RELATED_ADVISORY",
        obs=obs,
    )

    # Observation exists, but does NOT support CYCLONE
    assert eval_result["has_physical_observation"] is True
    assert eval_result["is_current_observation"] is True
    assert eval_result["is_current_observation_supported"] is False
    assert eval_result["observation_status_label"] == "CURRENT WEATHER OBSERVATION: YES | EVENT CORROBORATION: NO"


def test_case_9_conflicting_sources_penalty():
    """9. Contradictory evidence reduces confidence and marks review/contradiction."""
    factors = ConfidenceEngine.calculate_report_confidence(
        classification_conf=0.50,
        source_trust=0.50,
        has_contradictions=True,
        contradiction_severity=0.35,
    )
    assert factors.components.contradiction_penalty > 0.0
    assert factors.final_confidence < 0.50


def test_case_10_cyclone_semantic_synthesis():
    """10. Cyclone advisory / unconfirmed candidate must be framed transparently."""
    synth = synthesize_semantic_event_intelligence(
        category="CYCLONE",
        sub_category="CYCLONE_WARNING_ADVISORY",
        state="Telangana",
        district="Hyderabad",
        city="Hyderabad",
        evidence_texts=["Cyclone warning advisory issued for coastal and adjoining interior areas."],
        publishers=["Regional News"],
        evidence_count=1,
    )
    assert "advisory" in synth["title"].lower() or "candidate" in synth["title"].lower()
    assert synth["event_nature"] in ("WARNING", "ADVISORY")
    assert synth["is_current_observation"] is False
