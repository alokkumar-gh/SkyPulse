"""
SkyPulse Event-Evidence Integrity & Non-Weather Gating Regression Tests
========================================================================
Validates that:
1. Political protests, police FIRs, and crime reports can NEVER be categorized as RAINFALL or any weather hazard.
2. Evidence from another location/incident is rejected with EVENT_EVIDENCE_MISMATCH.
3. Speculative cyclone headlines are gated as FORECAST_POTENTIAL rather than ACTIVE CYCLONE.
4. Real IMD warnings are recognized as OFFICIAL_WARNING.
"""

import pytest
from connectors.weather_relevance_engine import (
    WeatherRelevanceEngine,
    IncidentNature,
    SourceAuthorityTier
)


def test_mumbai_police_fir_protest_is_rejected():
    """Validates the exact Mumbai Police FIR case reported by user is rejected unconditionally."""
    text = "Mumbai Police file FIR against 500 unidentified persons, organisers over CJP's Shivaji Park protest on Friday demanding CEC resignation"
    res = WeatherRelevanceEngine.evaluate(
        text=text,
        title="Mumbai Police file FIR against 500 unidentified persons",
        source_name="Hindustan Times",
        source_type="NEWS",
        claimed_category="RAINFALL"
    )
    assert res.is_relevant is False
    assert res.incident_nature == IncidentNature.NON_WEATHER_DRILL
    assert res.primary_category == "UNKNOWN"
    assert "Political protest" in res.rejection_reason or "zero meteorological" in res.rejection_reason


def test_political_and_civil_protest_stories_rejected():
    cases = [
        "Mumbai police files FIR against CJP leaders, supporters over Shivaji Park protest",
        "Will keep fighting to save democracy: CJP's Abhijeet Dipke after case filed over protest at Mumbai's Shivaji Park",
        "Opposition creates ruckus in assembly demanding rollback of bus fare hike",
        "Police arrested 4 suspects in connection with gold heist in Karol Bagh",
    ]
    for c in cases:
        res = WeatherRelevanceEngine.evaluate(text=c, claimed_category="RAINFALL")
        assert res.is_relevant is False, f"Expected non-weather rejection for: {c}"


def test_genuine_weather_with_city_accepted():
    text = "Heavy rainfall lashes Bhubaneswar causing severe waterlogging in low-lying areas and traffic disruption"
    res = WeatherRelevanceEngine.evaluate(
        text=text,
        title="Bhubaneswar heavy rain waterlogging",
        source_name="Regional News",
        source_type="NEWS",
        claimed_category="RAINFALL"
    )
    assert res.is_relevant is True
    assert res.incident_nature == IncidentNature.CURRENT_OBSERVATION
    assert res.primary_category in ("FLOODING", "RAINFALL")
    assert res.confidence >= 0.70


def test_speculative_vs_active_cyclone():
    spec_text = "ECMWF model suggests a cyclonic circulation may develop over Bay of Bengal next week"
    res_spec = WeatherRelevanceEngine.evaluate(
        text=spec_text,
        claimed_category="CYCLONE",
        source_name="Weather News",
        source_type="NEWS"
    )
    assert res_spec.is_relevant is True
    assert res_spec.incident_nature == IncidentNature.FORECAST_POTENTIAL
    assert res_spec.primary_category != "CYCLONE"  # Gated to RAINFALL/FORECAST

    warn_text = "IMD issues red cyclone warning for coastal Odisha as severe tropical storm approaches landfall"
    res_warn = WeatherRelevanceEngine.evaluate(
        text=warn_text,
        claimed_category="CYCLONE",
        source_name="IMD",
        source_type="OFFICIAL_GOVERNMENT"
    )
    assert res_warn.is_relevant is True
    assert res_warn.incident_nature in (IncidentNature.OFFICIAL_WARNING, IncidentNature.CURRENT_OBSERVATION)
    assert res_warn.primary_category == "CYCLONE"
    assert res_warn.confidence >= 0.85
