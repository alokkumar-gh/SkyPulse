"""
Unit and integration tests for the SkyPulse Search Discovery Ingestion Layer (Phase 1).
Tests query generation, provider abstraction, social & news URL classification,
provenance preservation, zero fake GPS enforcement, duplicate handling, and pipeline trace.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from connectors.schema import (
    CanonicalRawEvent,
    ConnectorStatusEnum,
    NormalizedEvent,
)
from connectors.normalizer import normalize_raw_event
from connectors.idempotency import idempotency_service
from connectors.search_discovery_connector import (
    SearchDiscoveryConnector,
    SearchResult,
    SearchQueryRegistry,
    DuckDuckGoSearchProvider,
    SearXNGSearchProvider,
    GoogleCSESearchProvider,
    CustomSearchProvider,
    classify_source_url,
    extract_weather_measurements,
    extract_hashtags_from_text,
    is_weather_relevant_search_content,
    DEFAULT_SEARCH_HASHTAGS,
    DEFAULT_SEARCH_LOCATIONS,
    DEFAULT_SEARCH_CATEGORIES,
)


# ==============================================================================
# 1. Query Generation & Configuration Tests
# ==============================================================================

def test_1_query_generation_defaults():
    registry = SearchQueryRegistry()
    queries = registry.get_all_queries()
    
    assert len(queries) > 0
    # Must contain default hashtags
    assert "#IMD" in queries
    assert "#Weather" in queries
    assert "#Monsoon" in queries
    # Must contain location-aware hashtag queries
    assert "#Rainfall Odisha" in queries or any("Odisha" in q for q in queries)
    assert "#Flood Assam" in queries or any("Assam" in q for q in queries)
    # Must contain quoted category + location queries
    assert any('"heavy rainfall" Mumbai' in q for q in queries)
    assert any('"IMD warning" India' in q for q in queries)


def test_2_query_generation_custom_and_dynamic():
    registry = SearchQueryRegistry(
        hashtags=["#CycloneAlert", "#Rainfall"],
        locations=["Kolkata", "Chennai"],
        categories=["waterlogging", "cloudburst"],
        custom_queries=['"IMD red alert" Tamil Nadu', "live monsoon radar"],
    )
    queries = registry.get_all_queries()
    
    assert '"IMD red alert" Tamil Nadu' in queries
    assert "live monsoon radar" in queries
    assert "#CycloneAlert" in queries
    assert "#Rainfall Kolkata" in queries
    assert '"waterlogging" Chennai' in queries


# ==============================================================================
# 2. Source & URL Classification Tests
# ==============================================================================

def test_3_social_url_detection():
    test_cases = [
        ("https://twitter.com/IMDWeather/status/18374928374", "SOCIAL", "X/Twitter"),
        ("https://x.com/MausamDelhi/status/987654321", "SOCIAL", "X/Twitter"),
        ("https://mastodon.social/@indianweather/10982347293", "SOCIAL", "Mastodon"),
        ("https://reddit.com/r/mumbai/comments/heavy_rain_waterlogging", "SOCIAL", "Reddit"),
        ("https://youtube.com/watch?v=cyclone_odisha_live", "SOCIAL", "YouTube"),
        ("https://threads.net/@bangalorerain/post/394829384", "SOCIAL", "Threads"),
        ("https://bsky.app/profile/weatherindia.bsky.social", "SOCIAL", "Bluesky"),
    ]
    for url, exp_type, exp_platform in test_cases:
        st, platform, domain = classify_source_url(url)
        assert st == exp_type, f"Failed for {url}: got {st}"
        assert platform == exp_platform, f"Failed for {url}: got {platform}"


def test_4_news_and_web_url_detection():
    test_cases = [
        ("https://ndtv.com/india-news/mumbai-rain-live-updates-imd-issues-orange-alert-5982734", "NEWS"),
        ("https://indiatoday.in/cities/delhi/story/delhi-heavy-rainfall-traffic-jam-waterlogging-284920", "NEWS"),
        ("https://thehindu.com/news/national/kerala/heavy-downpour-causes-flooding-in-wayanad/article6849203.ece", "NEWS"),
        ("https://timesofindia.indiatimes.com/city/bhubaneswar/odisha-heavy-rain-alert/articleshow/982734.cms", "NEWS"),
        ("https://mausam.imd.gov.in/forecast/bulletin.pdf", "NEWS"),
        ("https://example-blog.org/my-trip-to-manali-snowfall", "WEB"),
    ]
    for url, exp_type in test_cases:
        st, platform, domain = classify_source_url(url)
        assert st == exp_type, f"Failed for {url}: got {st}"


# ==============================================================================
# 3. Weather Measurements & Hashtags Extraction Tests
# ==============================================================================

def test_5_weather_measurements_extraction():
    text1 = "Santacruz recorded 142.5 mm rainfall in 24 hours with wind gusts up to 65 km/h and temp 28.4 °C."
    m1 = extract_weather_measurements(text1)
    assert "rainfall" in m1
    assert m1["rainfall"]["value"] == 142.5
    assert m1["rainfall"]["unit"] == "mm"
    assert "wind_speed" in m1
    assert m1["wind_speed"]["value"] == 65.0
    assert "temperature" in m1
    assert m1["temperature"]["value"] == 28.4

    text2 = "Severe heatwave in Churu: maximum temperature touches 47.8 deg C, atmospheric pressure 1001 hPa."
    m2 = extract_weather_measurements(text2)
    assert m2["temperature"]["value"] == 47.8
    assert m2["pressure"]["value"] == 1001.0
    assert m2["pressure"]["unit"] == "hpa"


def test_6_hashtag_extraction():
    text = "Heavy downpour in #Mumbai! #MumbaiRain alert issued by #IMD. Stay safe #WeatherAlert #MumbaiRain"
    tags = extract_hashtags_from_text(text)
    assert "#Mumbai" in tags
    assert "#MumbaiRain" in tags
    assert "#IMD" in tags
    assert "#WeatherAlert" in tags
    assert len(tags) == 4  # Deduplicated case-insensitively


# ==============================================================================
# 4. Relevance & Provenance Tests
# ==============================================================================

def test_7_weather_relevance_filter():
    relevant, terms = is_weather_relevant_search_content(
        text="Heavy thunderstorm and lightning reported across Hyderabad.",
        title="Hyderabad Weather Update",
        query='"thunderstorm" Hyderabad',
    )
    assert relevant is True
    assert len(terms) > 0

    irrelevant, terms_irr = is_weather_relevant_search_content(
        text="Stock market hits record high as tech companies surge.",
        title="Business Daily News",
        query="Sensex closing report",
    )
    assert irrelevant is False
    assert len(terms_irr) == 0


def test_8_provenance_retention():
    connector = SearchDiscoveryConnector()
    result = SearchResult(
        title="Bengaluru Heavy Rain: Waterlogging in Silk Board",
        url="https://thehindu.com/news/cities/bangalore/silk-board-flooded/article9823.ece",
        snippet="Over 85 mm rain in 3 hours flooded major junctions in Bengaluru #BengaluruRain",
        published_at=datetime.now(timezone.utc),
        raw_metadata={"rank": 1, "engine": "test"},
    )
    query = '"heavy rainfall" Bengaluru'

    raw_event = connector.parse((result, query))
    assert raw_event is not None
    assert raw_event.source_type == "NEWS"
    assert raw_event.external_id == result.url
    
    payload = raw_event.raw_payload
    assert payload["search_query"] == query
    assert payload["original_url"] == result.url
    assert payload["source_domain"] == "thehindu.com"
    assert payload["source_type"] == "NEWS"
    assert "weather_measurements" in payload
    assert payload["weather_measurements"]["rainfall"]["value"] == 85.0
    assert "#BengaluruRain" in payload["extracted_hashtags"]


# ==============================================================================
# 5. India Validation & Zero Fake GPS Tests
# ==============================================================================

def test_9_india_location_text_zero_fake_gps():
    connector = SearchDiscoveryConnector()
    result = SearchResult(
        title="Mumbai Heavy Rain Alert",
        url="https://ndtv.com/mumbai-rain-alert-123",
        snippet="IMD issues red alert for Mumbai and Thane due to severe waterlogging.",
    )
    raw_event = connector.parse((result, '"heavy rainfall" Mumbai'))
    assert raw_event is not None
    assert raw_event.is_india_valid is True
    assert raw_event.is_quarantined is False
    assert raw_event.city == "Mumbai"
    assert raw_event.state == "Maharashtra"
    assert raw_event.location_source == "TEXT"
    # Zero Fake GPS rule: must NOT invent fake lat/lon coordinates from text mention!
    assert raw_event.latitude is None
    assert raw_event.longitude is None


def test_10_unknown_location_quarantine():
    connector = SearchDiscoveryConnector()
    result = SearchResult(
        title="Unusual Weather Phenomenon",
        url="https://example.org/weather-blog-post",
        snippet="Heavy rain and hail storm recorded in our local area yesterday.",
    )
    raw_event = connector.parse((result, "#Weather"))
    assert raw_event is not None
    assert raw_event.is_india_valid is False
    assert raw_event.is_quarantined is True
    assert raw_event.quarantine_reason == "UNKNOWN_LOCATION"


# ==============================================================================
# 6. Providers & NOT_CONFIGURED Behavior Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_11_google_cse_not_configured():
    provider = GoogleCSESearchProvider(api_key="", cx="")
    status = await provider.health_check()
    assert status == ConnectorStatusEnum.NOT_CONFIGURED
    
    results = await provider.search("heavy rain Mumbai")
    assert results == []


@pytest.mark.asyncio
async def test_12_searxng_not_configured():
    provider = SearXNGSearchProvider(base_url="")
    status = await provider.health_check()
    assert status == ConnectorStatusEnum.NOT_CONFIGURED


@pytest.mark.asyncio
async def test_13_duckduckgo_parsing():
    provider = DuckDuckGoSearchProvider()
    mock_html = """
    <html>
      <div class="result results_links">
        <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Findiatoday.in%2Fweather-odisha-cyclone">
          Odisha Cyclone Alert: IMD issues heavy rainfall warning
        </a>
        <div class="result__snippet">
          Severe cyclonic storm approaches Odisha coast. Coastal districts expect over 150 mm rainfall.
        </div>
      </div>
      <div class="result results_links">
        <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fx.com%2Fweather_india%2Fstatus%2F123456">
          IMD Weather Update on X: #Cyclone Alert
        </a>
        <div class="result__snippet">
          #Cyclone alert for coastal #Odisha. Strong winds up to 90 km/h predicted.
        </div>
      </div>
    </html>
    """
    results = provider._parse_html(mock_html, max_results=10)
    assert len(results) == 2
    assert results[0].url == "https://indiatoday.in/weather-odisha-cyclone"
    assert "Odisha Cyclone Alert" in results[0].title
    assert "150 mm" in results[0].snippet

    assert results[1].url == "https://x.com/weather_india/status/123456"
    assert "#Cyclone" in results[1].snippet


@pytest.mark.asyncio
async def test_14_duckduckgo_rate_limit_backoff():
    provider = DuckDuckGoSearchProvider()
    provider._last_rate_limited = datetime.now(timezone.utc).timestamp()
    provider._backoff_duration = 100.0

    status = await provider.health_check()
    assert status == ConnectorStatusEnum.DEGRADED

    results = await provider.search("#Weather")
    assert results == []


# ==============================================================================
# 7. Polling Lifecycle & Telemetry Consistency Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_15_polling_and_telemetry_consistency():
    async def mock_handler(query: str, max_results: int):
        if "mumbai" in query.lower():
            return [
                SearchResult(
                    title="Mumbai Monsoon Live: Heavy downpour in Dadar",
                    url="https://timesofindia.indiatimes.com/mumbai-rain-dadar",
                    snippet="Waterlogging reported in Dadar and Hindmata following 90 mm rain. #MumbaiRain",
                ),
                SearchResult(
                    title="Stock market report today",
                    url="https://moneycontrol.com/stocks-today",
                    snippet="Sensex gains 500 points in early trading.",
                ),
            ]
        elif "delhi" in query.lower():
            return [
                SearchResult(
                    title="Delhi Heatwave Warning",
                    url="https://ndtv.com/delhi-heatwave-alert",
                    snippet="IMD issues yellow alert as mercury touches 44 °C in Delhi.",
                ),
                SearchResult(
                    title="Unknown remote region rain",
                    url="https://example.com/unnamed-weather",
                    snippet="Thunderstorm and rain observed in our remote area.",
                ),
            ]
        return []

    provider = CustomSearchProvider(handler=mock_handler)
    registry = SearchQueryRegistry(custom_queries=['"heavy rainfall" Mumbai', '"heatwave" Delhi'])
    connector = SearchDiscoveryConnector(provider=provider, query_registry=registry)
    connector.is_running = True

    events = await connector.poll()
    m = connector.metrics

    # Telemetry mathematical invariants:
    # fetched = weather_relevant + rejected_non_weather
    assert m.records_fetched == m.weather_relevant + m.rejected_non_weather
    # weather_relevant = accepted_india + quarantined_foreign + quarantined_unknown_location
    assert m.weather_relevant == m.accepted_india + m.quarantined_foreign + m.quarantined_unknown_location
    assert m.records_accepted == m.accepted_india
    assert len(events) == m.accepted_india
    assert m.errors == 0


# ==============================================================================
# 8. Deduplication & Idempotency Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_16_cross_query_deduplication():
    # Same article returned for multiple queries
    shared_result = SearchResult(
        title="Assam Flood Situation Critical: Brahmaputra Overflows",
        url="https://thehindu.com/news/national/assam/assam-flood-critical-state/article982734.ece",
        snippet="Over 20 districts affected by severe flood in Assam. Kaziranga submerged. #Flood",
    )

    async def mock_handler(query: str, max_results: int):
        return [shared_result]

    provider = CustomSearchProvider(handler=mock_handler)
    registry = SearchQueryRegistry(custom_queries=['#Flood Assam', '"flooding" Assam'])
    connector = SearchDiscoveryConnector(provider=provider, query_registry=registry)
    connector.is_running = True

    events1 = await connector.poll()
    assert len(events1) >= 1

    # Second poll should detect existing URL as duplicate
    events2 = await connector.poll()
    assert connector.metrics.duplicates >= 1


# ==============================================================================
# 9. End-to-End Pipeline Integration Trace Test
# ==============================================================================

@pytest.mark.asyncio
async def test_17_end_to_end_search_discovery_pipeline_trace():
    connector = SearchDiscoveryConnector()
    result = SearchResult(
        title="Chennai Rain: Heavy downpour causes waterlogging in Velachery",
        url="https://timesofindia.indiatimes.com/city/chennai/velachery-rain-waterlogging/123",
        snippet="Over 110 mm rainfall recorded in Chennai. IMD issues thunderstorm warning. #ChennaiRain",
        published_at=datetime(2026, 10, 2, 10, 0, 0, tzinfo=timezone.utc),
    )
    query = '"heavy rainfall" Chennai'

    raw_event = connector.parse((result, query))
    assert isinstance(raw_event, CanonicalRawEvent)
    assert raw_event.source_type == "NEWS"
    assert raw_event.is_india_valid is True

    # Pass into canonical normalizer
    norm_event = await normalize_raw_event(raw_event)
    assert isinstance(norm_event, NormalizedEvent)
    assert norm_event.city == "Chennai"
    assert norm_event.state == "Tamil Nadu"
    assert norm_event.latitude is None  # Zero fake GPS
    assert norm_event.primary_category in ("RAINFALL", "FLOODING")
    assert norm_event.tracking_id.startswith("SP-")
    assert norm_event.idempotency_key is not None
    assert norm_event.is_quarantined is False
