"""
SkyPulse Phase 5 Tests — Classification & NLP Entity Extraction
Tests event classification across all seven required categories, severity scoring,
NLP entity and metric extraction, and media visual analysis.
"""

import pytest
from ai.fallback_provider import FallbackAIProvider
from ai.external_provider import ExternalAIProvider
from ai.event_classifier import EventClassifier
from ai.nlp_extractor import NLPExtractor
from ai.image_analyzer import ImageAnalyzer


@pytest.mark.asyncio
async def test_classification_all_seven_categories():
    """Verify classification accurately identifies all 7 core categories with high confidence."""
    classifier = EventClassifier()

    test_cases = [
        ("Heavy continuous monsoon rain recorded over Mumbai causing waterlogging", "RAINFALL"),
        ("Severe thunderstorm with active lightning strikes and loud thunder in Kolkata", "THUNDERSTORM"),
        ("Streets submerged under knee-deep flood waters in Guwahati after river breach", "FLOODING"),
        ("Extreme heatwave conditions with loo winds blowing over Nagpur, temp 45°C", "HEATWAVE"),
        ("Dense radiation fog at Delhi airport reducing runway visibility to under 100m", "FOG"),
        ("Blinding dust storm swept across Bikaner darkening the sky with high dust winds", "DUST_STORM"),
        ("Gale force squally winds exceeding 75 km/h recorded along the Chennai coast", "STRONG_WINDS"),
    ]

    for text, expected_category in test_cases:
        res = await classifier.classify(text)
        assert res.category == expected_category, f"Failed for text: '{text}'. Got {res.category}"
        assert res.confidence >= 0.50
        assert len(res.evidence_signals) >= 1
        assert 1 <= res.severity <= 4


@pytest.mark.asyncio
async def test_classification_ambiguous_and_unknown():
    """Verify ambiguous or non-weather texts yield UNKNOWN category with low confidence."""
    classifier = EventClassifier()

    res = await classifier.classify("Normal quiet evening with regular traffic downtown.")
    assert res.category == "UNKNOWN"
    assert res.confidence <= 0.40
    assert res.severity == 1


@pytest.mark.asyncio
async def test_classification_severity_levels():
    """Verify severity estimation ranges from 1 (minor) to 4 (cloudburst/catastrophic)."""
    classifier = EventClassifier()

    catastrophic = await classifier.classify("Devastating cloudburst and flash flood in Kedarnath causing severe casualties")
    assert catastrophic.severity >= 3

    minor = await classifier.classify("Passing light drizzle in Bangalore with mild breeze")
    assert minor.severity <= 2


@pytest.mark.asyncio
async def test_nlp_entity_extraction_spatial_and_metrics():
    """Verify NLPExtractor extracts Indian cities, rainfall mm, wind speed, and temperatures."""
    extractor = NLPExtractor()

    sample_text = (
        "In Chennai, Tamil Nadu, 140 mm rainfall was recorded during evening hours. "
        "Wind speed reached 65 km/h with localized waterlogging on major roads."
    )
    res = await extractor.extract(sample_text)

    # Location resolution
    assert res.resolved_city == "Chennai"
    assert res.resolved_state == "Tamil Nadu"
    assert res.resolved_lat is not None
    assert res.resolved_lon is not None

    # Weather attributes
    attr_names = [a.name for a in res.weather_attributes]
    assert "rainfall_amount" in attr_names
    assert "wind_speed" in attr_names

    rain_attr = next(a for a in res.weather_attributes if a.name == "rainfall_amount")
    assert rain_attr.value == 140.0
    assert rain_attr.unit == "mm"

    wind_attr = next(a for a in res.weather_attributes if a.name == "wind_speed")
    assert wind_attr.value == 65.0

    # Temporal & Impact
    assert "evening" in res.temporal_mentions
    assert "waterlogging" in res.impact_mentions
    assert res.confidence >= 0.70


@pytest.mark.asyncio
async def test_nlp_entity_extraction_heatwave_and_flood_depth():
    """Verify temperature and flood depth extraction."""
    extractor = NLPExtractor()

    text_heat = "Scorching heatwave in Ahmedabad, temperature reached 44.5 C yesterday afternoon."
    res_heat = await extractor.extract(text_heat)
    temp_attr = next((a for a in res_heat.weather_attributes if a.name == "temperature"), None)
    assert temp_attr is not None
    assert temp_attr.value == 44.5

    text_flood = "Roads submerged under 4 feet water in Kochi."
    res_flood = await extractor.extract(text_flood)
    depth_attr = next((a for a in res_flood.weather_attributes if a.name == "flood_depth"), None)
    assert depth_attr is not None
    assert depth_attr.value == 4.0


@pytest.mark.asyncio
async def test_image_analyzer_metadata_and_phash():
    """Verify ImageAnalyzer extracts perceptual hash and detects visual signals."""
    analyzer = ImageAnalyzer()

    # Image with rain keywords in URL
    res = await analyzer.analyze(
        media_urls=["https://storage.skypulse.in/reports/mumbai_flood_street_water.jpg"],
        claimed_category="FLOODING",
    )
    assert res.has_media is True
    assert res.phash is not None
    assert len(res.phash) == 16
    assert res.supports_claimed_event is True
    assert "standing_water" in res.signals

    # Empty media
    empty_res = await analyzer.analyze(media_urls=[])
    assert empty_res.has_media is False
    assert empty_res.phash is None


@pytest.mark.asyncio
async def test_external_provider_unconfigured_fallback():
    """Verify ExternalAIProvider reports NOT_CONFIGURED when keys absent and uses fallback."""
    provider = ExternalAIProvider(api_key=None)
    assert provider.is_configured is False
    assert provider.status == "NOT_CONFIGURED"

    res = await provider.classify_event("Heavy thunderstorm in Pune")
    assert res.category == "THUNDERSTORM"
    assert res.confidence >= 0.5
