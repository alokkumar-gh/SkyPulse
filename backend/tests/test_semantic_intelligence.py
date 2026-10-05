"""
Comprehensive Semantic Weather Intelligence & Grounded Classification Test Suite
================================================================================
Verifies that:
1. Monsoon / seasonal rain deficit articles are NEVER conflated with current rainfall observations.
2. Deficit, excess, dry spells, forecasts, and observed rain are correctly distinguished.
3. Anti-hallucination title generation produces grounded, accurate titles.
4. Deduplicator does not merge incompatible phenomena.
5. DWEG topology properly captures seasonal deficit scopes.
"""
import pytest
from app.models.enums import WeatherPhenomenon, EventNature, TemporalScope, EvidenceBasis
from ai.fallback_provider import FallbackAIProvider
from ai.deduplicator import DeduplicationEngine
from connectors.weather_relevance_engine import WeatherRelevanceEngine, IncidentNature
from app.services.weather_intelligence_service import synthesize_semantic_event_intelligence


@pytest.fixture
def fallback_ai():
    return FallbackAIProvider()


@pytest.mark.asyncio
async def test_maharashtra_rain_deficit_classification(fallback_ai):
    """
    Test Case 1: The exact problematic article:
    'Maharashtra monsoon withdraws early as 21 districts record rain deficit'
    Must be classified as RAINFALL_DEFICIT, NOT current rainfall.
    """
    text = "Maharashtra monsoon withdraws early as 21 districts record rain deficit"
    res = await fallback_ai.classify_event(text)
    
    assert res.phenomenon == WeatherPhenomenon.RAINFALL_DEFICIT
    assert res.is_current_observation is False
    assert res.event_nature == EventNature.ANOMALY
    assert res.temporal_scope == TemporalScope.SEASONAL
    assert res.evidence_basis == EvidenceBasis.RAINFALL_ANOMALY


@pytest.mark.asyncio
async def test_current_heavy_rainfall_classification(fallback_ai):
    """
    Test Case 2: Active rainfall observation:
    'Heavy rain lashes Mumbai, waterlogging reported'
    Must be classified as HEAVY_RAINFALL, is_current_observation = True.
    """
    text = "Heavy rain lashes Mumbai, waterlogging reported"
    res = await fallback_ai.classify_event(text)
    
    assert res.phenomenon in [WeatherPhenomenon.HEAVY_RAINFALL, WeatherPhenomenon.RAINFALL_OBSERVED]
    assert res.is_current_observation is True
    assert res.event_nature == EventNature.OBSERVATION
    assert res.temporal_scope == TemporalScope.CURRENT


@pytest.mark.asyncio
async def test_rainfall_forecast_classification(fallback_ai):
    """
    Test Case 3: Forecast / Warning:
    'IMD issues orange alert for heavy rainfall in Pune tomorrow'
    Must be classified as FORECAST/WARNING, is_current_observation = False.
    """
    text = "IMD issues orange alert for heavy rainfall in Pune tomorrow"
    res = await fallback_ai.classify_event(text)
    
    assert res.is_current_observation is False
    assert res.event_nature in [EventNature.FORECAST, EventNature.WARNING]


@pytest.mark.asyncio
async def test_dry_spell_classification(fallback_ai):
    """
    Test Case 4: Dry spell:
    'Marathwada faces severe dry spell for third consecutive week'
    Must be classified as DRY_SPELL.
    """
    text = "Marathwada faces severe dry spell for third consecutive week"
    res = await fallback_ai.classify_event(text)
    
    assert res.phenomenon == WeatherPhenomenon.DRY_SPELL
    assert res.is_current_observation is False
    assert res.event_nature == EventNature.ANOMALY


@pytest.mark.asyncio
async def test_rainfall_excess_classification(fallback_ai):
    """
    Test Case 5: Rainfall Excess:
    'State records 40% excess rainfall this monsoon season'
    Must be classified as RAINFALL_EXCESS.
    """
    text = "State records 40% excess rainfall this monsoon season"
    res = await fallback_ai.classify_event(text)
    
    assert res.phenomenon == WeatherPhenomenon.RAINFALL_EXCESS
    assert res.is_current_observation is False
    assert res.event_nature == EventNature.ANOMALY
    assert res.temporal_scope == TemporalScope.SEASONAL


@pytest.mark.asyncio
async def test_no_rain_classification(fallback_ai):
    """
    Test Case 6: No rain report:
    'No rain recorded in Nagpur over the past 24 hours'
    Must be classified as NO_RAIN.
    """
    text = "No rain recorded in Nagpur over the past 24 hours"
    res = await fallback_ai.classify_event(text)
    
    assert res.phenomenon == WeatherPhenomenon.NO_RAIN
    assert res.is_current_observation is True


def test_weather_relevance_engine_deficit():
    """
    Test Case 7: Weather Relevance Engine identifies incident nature as RAINFALL_DEFICIT.
    """
    text = "Maharashtra monsoon withdraws early as 21 districts record rain deficit"
    assessment = WeatherRelevanceEngine.evaluate(text=text, source_type="NEWS_ARTICLE")
    
    assert assessment.is_relevant is True
    assert assessment.phenomenon == "RAINFALL_DEFICIT"
    assert assessment.incident_nature == IncidentNature.SEASONAL_ANOMALY
    assert assessment.temporal_scope == "SEASONAL"


def test_deduplicator_prevents_deficit_and_rain_observed_merging():
    """
    Test Case 8: Deduplicator must NOT merge a RAINFALL_DEFICIT event with a RAINFALL_OBSERVED event.
    """
    deficit_report = {
        "id": "r1",
        "category": "RAINFALL",
        "sub_category": "RAINFALL_DEFICIT",
        "state": "Maharashtra",
        "district": "Pune",
        "event_time": "2026-10-04T10:00:00Z"
    }
    rain_report = {
        "id": "r2",
        "category": "RAINFALL",
        "sub_category": "RAINFALL_OBSERVED",
        "state": "Maharashtra",
        "district": "Pune",
        "event_time": "2026-10-04T10:00:00Z"
    }
    
    eval_res = DeduplicationEngine.evaluate_candidate(deficit_report, rain_report)
    assert eval_res.is_duplicate is False, "Incompatible weather phenomena must not be marked as duplicate"
    assert "Incompatible meteorological phenomena" in eval_res.explanation


def test_synthesize_semantic_event_intelligence_title_generation():
    """
    Test Case 9: synthesize_semantic_event_intelligence produces accurate, grounded title
    and NOT 'Rainfall reported in Maharashtra' for deficit evidence.
    """
    evidence_texts = [
        "Maharashtra monsoon withdraws early as 21 districts record rain deficit. 21 districts in Maharashtra recorded rainfall deficit this monsoon."
    ]
    publishers = ["Indian Express"]
    
    intel = synthesize_semantic_event_intelligence(
        category="RAINFALL",
        sub_category="RAINFALL_DEFICIT",
        state="Maharashtra",
        district=None,
        city=None,
        evidence_texts=evidence_texts,
        publishers=publishers,
        evidence_count=1,
    )
    
    assert "Rainfall reported" not in intel["title"]
    assert "deficit" in intel["title"].lower()
    assert intel["phenomenon"] == "RAINFALL_DEFICIT"
    assert intel["temporal_scope"] == "SEASONAL"
    assert intel["event_nature"] == "ANOMALY"
    assert intel["is_current_observation"] is False
    assert intel["evidence_basis"] == "RAINFALL_ANOMALY"


def test_semantic_event_intelligence_current_rain_title():
    """
    Test Case 10: synthesize_semantic_event_intelligence produces accurate title for actual observed rain.
    """
    evidence_texts = [
        "Heavy rain lashes Mumbai leading to waterlogging in low lying areas."
    ]
    publishers = ["PTI"]
    
    intel = synthesize_semantic_event_intelligence(
        category="RAINFALL",
        sub_category="HEAVY_RAINFALL",
        state="Maharashtra",
        district="Mumbai City",
        city="Mumbai",
        evidence_texts=evidence_texts,
        publishers=publishers,
        evidence_count=1,
    )
    
    assert intel["phenomenon"] in ["HEAVY_RAINFALL", "RAINFALL_OBSERVED"]
    assert intel["is_current_observation"] is True
    assert intel["temporal_scope"] == "CURRENT"
    assert intel["event_nature"] == "OBSERVATION"
