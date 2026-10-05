"""
Unit and integration tests for the SkyPulse Regional Discovery Engine.
"""

import pytest
from connectors.weather_discovery.regional_rss import is_weather_relevant, RSSFeedConfig, RSS_FEEDS
from connectors.weather_discovery.india_locations import lookup_location, validate_location
from connectors.normalizer import normalize_category
from connectors.weather_discovery.query_engine import QueryEngine, DiscoveryQuery


def test_weather_relevance_filter():
    # Meteorological terms
    assert is_weather_relevant("Heavy rainfall hits Cuttack causing waterlogging") is True
    assert is_weather_relevant("Flood warning issued in Assam after river breaches danger mark") is True
    assert is_weather_relevant("Severe cyclone alert for coastal Odisha and Andhra Pradesh") is True
    assert is_weather_relevant("Intense heatwave sweeps across Delhi and Rajasthan") is True

    # Metaphorical non-weather terms
    assert is_weather_relevant("Political storm in Delhi over liquor policy") is False
    assert is_weather_relevant("Opposition creates storm in parliament") is False
    assert is_weather_relevant("Stock market crash triggers storm among investors") is False
    assert is_weather_relevant("Bollywood movie creates storm at box office") is False

    # Meteorological override in metaphorical context
    assert is_weather_relevant("Storm hits parliament as cyclone approaches coastal belt causing 100mm rainfall") is True


def test_india_location_resolution():
    loc = lookup_location("Bhubaneswar")
    assert loc is not None
    assert loc["city"] == "Bhubaneswar"
    assert loc["district"] == "Khordha"
    assert loc["state"] == "Odisha"
    assert abs(loc["lat"] - 20.2961) < 0.01

    loc_puri = lookup_location("Puri")
    assert loc_puri is not None
    assert loc_puri["district"] == "Puri"
    assert loc_puri["state"] == "Odisha"

    loc_mumbai = lookup_location("Mumbai")
    assert loc_mumbai is not None
    assert loc_mumbai["city"] == "Mumbai"
    assert loc_mumbai["state"] == "Maharashtra"

    # Ambiguous location check without explicit coords
    res_ambig = validate_location(None)
    assert res_ambig["location_status"] == "AMBIGUOUS"
    assert res_ambig["coordinates"] is None


def test_multilingual_keyword_detection():
    # Odia
    title_or = "ପୁରୀରେ ପ୍ରବଳ ବର୍ଷା ଓ ଘୂର୍ଣ୍ଣିବାତ ସତର୍କତା"
    assert is_weather_relevant(title_or) is True
    assert normalize_category(None, text=title_or) == "CYCLONE"

    # Hindi
    title_hi = "दिल्ली में भारी बारिश से जनजीवन अस्त-व्यस्त"
    assert is_weather_relevant(title_hi) is True
    assert normalize_category(None, text=title_hi) == "RAINFALL"

    # Bengali
    title_bn = "কলকাতায় প্রবল বৃষ্টিপাত এবং বজ্রবিদ্যুৎ সহ ঝড়"
    assert is_weather_relevant(title_bn) is True
    assert normalize_category(None, text=title_bn) in ("THUNDERSTORM", "RAINFALL")

    # Tamil
    title_ta = "சென்னையில் தீவிர புயல் எச்சரிக்கை விடுக்கப்பட்டுள்ளது"
    assert is_weather_relevant(title_ta) is True
    assert normalize_category(None, text=title_ta) == "CYCLONE"


def test_query_engine_priority_and_alerts():
    engine = QueryEngine(
        locations=["Bhubaneswar", "Puri", "Mumbai"],
        active_alert_states=["Odisha"],
        active_alert_districts=["Puri"],
        active_alert_events=["CYCLONE", "HEAVY_RAIN"],
    )
    
    queries = engine.generate()
    assert len(queries) > 0
    
    # Priority 1 queries should be at the front
    first_item = queries[0]
    assert first_item.priority == 1
    assert first_item.state == "Odisha" or first_item.location in ("Bhubaneswar", "Puri")


def test_rss_feed_registry_structure():
    assert len(RSS_FEEDS) >= 30
    for feed in RSS_FEEDS:
        assert feed.url.startswith("http")
        assert feed.source_type in ("OFFICIAL", "GOVERNMENT", "NEWS_PUBLISHER", "SOCIAL_SIGNAL")
        assert 0.0 <= feed.trust_score <= 1.0
