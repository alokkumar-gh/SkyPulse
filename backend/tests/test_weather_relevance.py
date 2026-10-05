import pytest
from connectors.weather_relevance_engine import (
    WeatherRelevanceEngine,
    IncidentNature,
    SourceAuthorityTier
)

def test_realistic_negative_cases():
    # CASE 1: "cyclone may form next week" -> FORECAST/POTENTIAL, NOT ACTIVE CYCLONE
    res1 = WeatherRelevanceEngine.evaluate(
        text="IMD expects a cyclone may form next week over the Bay of Bengal",
        claimed_category="CYCLONE",
        source_name="Regional News",
        source_type="NEWS"
    )
    assert res1.is_relevant is True
    assert res1.incident_nature == IncidentNature.FORECAST_POTENTIAL
    assert res1.is_cyclone_rigorous is False
    assert res1.primary_category in ["FORECAST", "RAINFALL", "UNKNOWN"]

    # CASE 2: "cyclone preparedness drill in Puri" -> NOT A CYCLONE EVENT (DRILL)
    res2 = WeatherRelevanceEngine.evaluate(
        text="Mock cyclone preparedness drill conducted in Puri ahead of monsoon season",
        claimed_category="CYCLONE",
        source_name="District Admin",
        source_type="GOVERNMENT"
    )
    assert res2.incident_nature == IncidentNature.NON_WEATHER_DRILL
    assert res2.is_relevant is False

    # CASE 3: "cyclone-prone Odisha" -> GENERAL CONTEXT / HISTORICAL STUDY
    res3 = WeatherRelevanceEngine.evaluate(
        text="A study examines why coastal Odisha remains cyclone-prone historically",
        claimed_category="CYCLONE",
        source_name="Science Journal",
        source_type="RESEARCH"
    )
    assert res3.incident_nature == IncidentNature.HISTORICAL_STUDY
    assert res3.is_relevant is False

    # CASE 4: "IMD issues cyclone warning for coastal Odisha" -> WARNING / CURRENT
    res4 = WeatherRelevanceEngine.evaluate(
        text="IMD issues red cyclone warning for coastal Odisha as severe storm approaches",
        claimed_category="CYCLONE",
        source_name="IMD",
        source_type="OFFICIAL_GOVERNMENT"
    )
    assert res4.is_relevant is True
    assert res4.incident_nature in [IncidentNature.OFFICIAL_WARNING, IncidentNature.CURRENT_OBSERVATION]
    assert res4.primary_category == "CYCLONE"
    assert res4.confidence >= 0.85
    assert res4.authority_tier == SourceAuthorityTier.TIER_1_OFFICIAL

    # CASE 5: "cyclone has made landfall near Paradip" -> CYCLONE event if source and timing support it
    res5 = WeatherRelevanceEngine.evaluate(
        text="Tropical Cyclone has made landfall near Paradip coast with 120kmph winds",
        claimed_category="CYCLONE",
        source_name="IMD",
        source_type="OFFICIAL_GOVERNMENT"
    )
    assert res5.is_relevant is True
    assert res5.primary_category == "CYCLONE"
    assert res5.confidence >= 0.85

    # CASE 6: "historic cyclone affected Puri in 1999" -> HISTORICAL
    res6 = WeatherRelevanceEngine.evaluate(
        text="Remembering the historic super cyclone that struck Odisha in 1999",
        claimed_category="CYCLONE",
        source_name="News Feature",
        source_type="NEWS"
    )
    assert res6.incident_nature == IncidentNature.HISTORICAL_STUDY
    assert res6.is_relevant is False

    # CASE 7: "citizen reports strong winds" -> UNVERIFIED SIGNAL unless corroborated
    res7 = WeatherRelevanceEngine.evaluate(
        text="Citizen reports strong winds and dark clouds near Cuttack",
        claimed_category="SEVERE_STORM",
        source_name="Citizen App",
        source_type="CITIZEN_REPORT"
    )
    assert res7.is_relevant is True
    assert res7.incident_nature in [IncidentNature.UNVERIFIED_SIGNAL, IncidentNature.CURRENT_OBSERVATION]
    assert res7.authority_tier == SourceAuthorityTier.TIER_5_CITIZEN_SOCIAL

def test_telecom_and_non_weather_filter():
    res = WeatherRelevanceEngine.evaluate(
        text="Telecom companies fortify mobile towers against cyclone wind speeds report",
        claimed_category="CYCLONE",
        source_name="Tech News",
        source_type="NEWS"
    )
    assert res.is_relevant is False
    assert res.incident_nature == IncidentNature.NON_WEATHER_DRILL
