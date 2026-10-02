"""
Unit and integration tests for the SkyPulse News Website Ingestion Layer.
Tests RSS/Atom parsing, source registry management, canonical URL normalization,
publication timestamp parsing, weather measurement extraction, zero fake GPS enforcement,
idempotency, deduplication across channels, and pipeline trace.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import httpx

from connectors.schema import (
    CanonicalRawEvent,
    ConnectorStatusEnum,
    NormalizedEvent,
)
from connectors.normalizer import normalize_raw_event
from connectors.idempotency import idempotency_service
from connectors.news_website_connector import (
    NewsWebsiteConnector,
    NewsSourceRegistry,
    NewsSourceDefinition,
    NewsArticleItem,
    normalize_canonical_url,
    parse_publication_timestamp,
    DEFAULT_NEWS_SOURCES,
)


# ==============================================================================
# 1. Canonical URL Normalization & Timestamp Tests
# ==============================================================================

def test_1_canonical_url_tracking_param_stripping():
    test_cases = [
        (
            "https://www.thehindu.com/news/national/mumbai-rain-alert?utm_source=rss&utm_medium=feed&utm_campaign=news#comments",
            "https://www.thehindu.com/news/national/mumbai-rain-alert",
        ),
        (
            "https://ndtv.com/india-news/article-123/?fbclid=IwAR2345&gclid=EAIaIQobChMI&ref=hp",
            "https://ndtv.com/india-news/article-123",
        ),
        (
            "https://timesofindia.indiatimes.com/city/delhi/heatwave.cms?ocid=NNS&utm_content=top",
            "https://timesofindia.indiatimes.com/city/delhi/heatwave.cms",
        ),
    ]
    for raw_url, expected in test_cases:
        cleaned = normalize_canonical_url(raw_url)
        assert cleaned == expected, f"Failed for {raw_url}: got {cleaned}"


def test_2_publication_timestamp_parsing():
    # RFC 822 / 2822 standard in RSS feeds
    rfc822_date = "Fri, 02 Oct 2026 10:30:00 +0530"
    dt1 = parse_publication_timestamp(rfc822_date)
    assert dt1 is not None
    assert dt1.tzinfo == timezone.utc
    assert dt1.year == 2026
    assert dt1.month == 10
    assert dt1.day == 2

    # ISO 8601 standard in Atom feeds
    iso_date = "2026-10-02T05:00:00Z"
    dt2 = parse_publication_timestamp(iso_date)
    assert dt2 is not None
    assert dt2.year == 2026
    assert dt2.hour == 5

    # Invalid string
    assert parse_publication_timestamp("not-a-valid-date") is None
    assert parse_publication_timestamp("") is None


# ==============================================================================
# 2. Source Registry Management Tests
# ==============================================================================

def test_3_news_source_registry_defaults_and_toggle():
    registry = NewsSourceRegistry()
    sources = registry.get_all_sources()
    assert len(sources) >= 5

    # Verify key publishers exist
    source_ids = [s.source_id for s in sources]
    assert "pib-india" in source_ids
    assert "dd-news" in source_ids
    assert "the-hindu" in source_ids
    assert "ndtv-india" in source_ids

    # Test toggling
    assert registry.disable_source("ndtv-india") is True
    ndtv = registry.get_source("ndtv-india")
    assert ndtv is not None
    assert ndtv.enabled is False
    assert ndtv not in registry.get_enabled_sources()

    assert registry.enable_source("ndtv-india") is True
    assert ndtv.enabled is True


# ==============================================================================
# 3. Feed Parsing Tests (RSS 2.0 & Atom 1.0)
# ==============================================================================

def test_4_rss_feed_parsing_with_media_and_author():
    connector = NewsWebsiteConnector()
    source = NewsSourceDefinition(
        source_id="test-news",
        publisher_name="National News Agency",
        domains=["news.example.com"],
        feed_urls=["https://news.example.com/rss"],
    )

    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/">
      <channel>
        <title>National News Agency Weather</title>
        <item>
          <title>Mumbai Heavy Rain: Waterlogging at Hindmata and Dadar</title>
          <link>https://news.example.com/mumbai-rain-alert-2026?utm_source=rss</link>
          <description><![CDATA[Over 120 mm rainfall recorded in 6 hours causing traffic disruptions across Mumbai. #MumbaiRain]]></description>
          <pubDate>Fri, 02 Oct 2026 09:00:00 +0530</pubDate>
          <dc:creator>Weather Bureau</dc:creator>
          <enclosure url="https://news.example.com/images/mumbai_rain.jpg" type="image/jpeg" />
        </item>
        <item>
          <title>Stock Market Midday Update</title>
          <link>https://news.example.com/stocks-rally</link>
          <description>Financial markets trade higher led by banking stocks.</description>
          <pubDate>Fri, 02 Oct 2026 09:15:00 +0530</pubDate>
        </item>
      </channel>
    </rss>
    """

    items = connector._parse_feed_xml(rss_xml, source, "https://news.example.com/rss")
    assert len(items) == 2

    # Check first item fields
    item1 = items[0]
    assert item1.publisher == "National News Agency"
    assert "Mumbai Heavy Rain" in item1.title
    assert item1.canonical_url == "https://news.example.com/mumbai-rain-alert-2026"  # utm stripped
    assert item1.author == "Weather Bureau"
    assert item1.published_at is not None
    assert len(item1.media_urls) == 1
    assert "mumbai_rain.jpg" in item1.media_urls[0]


def test_5_atom_feed_parsing():
    connector = NewsWebsiteConnector()
    source = NewsSourceDefinition(
        source_id="test-atom",
        publisher_name="Meteorology Feed",
        domains=["met.example.org"],
    )

    atom_xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Meteorological Alerts</title>
      <entry>
        <title>Severe Heatwave Warning for Rajasthan Districts</title>
        <link href="https://met.example.org/heatwave-rajasthan-alert?ref=atom"/>
        <summary>Max temperature expected to reach 46.5 °C in Churu and Bikaner districts.</summary>
        <published>2026-10-02T06:30:00Z</published>
      </entry>
    </feed>
    """

    items = connector._parse_feed_xml(atom_xml, source, "https://met.example.org/atom")
    assert len(items) == 1
    assert "Severe Heatwave Warning" in items[0].title
    assert items[0].canonical_url == "https://met.example.org/heatwave-rajasthan-alert"
    assert items[0].published_at is not None


# ==============================================================================
# 4. Parsing, Relevance & Zero Fake GPS Tests
# ==============================================================================

def test_6_news_item_parsing_and_zero_fake_gps():
    connector = NewsWebsiteConnector()
    article = NewsArticleItem(
        publisher="The Hindu",
        title="Odisha Cyclone Alert: Heavy downpour likely in coastal districts",
        canonical_url="https://thehindu.com/news/national/odisha/cyclone-alert-odisha/123",
        summary="IMD issues yellow alert for coastal Odisha. Wind speeds up to 75 km/h and 150 mm rain predicted. #CycloneAlert",
        published_at=datetime(2026, 10, 2, 8, 0, 0, tzinfo=timezone.utc),
        media_urls=["https://thehindu.com/images/cyclone.jpg"],
        source_feed_url="https://thehindu.com/rss",
    )

    raw_event = connector.parse(article)
    assert raw_event is not None
    assert raw_event.source_type == "NEWS"
    assert raw_event.is_india_valid is True
    assert raw_event.is_quarantined is False
    assert raw_event.state == "Odisha"
    assert raw_event.location_source == "TEXT"
    # Zero Fake GPS: must NEVER invent fake lat/lon coordinates from text mention!
    assert raw_event.latitude is None
    assert raw_event.longitude is None

    # Check DWEG Evidence Metadata Provenance
    payload = raw_event.raw_payload
    assert payload["publisher"] == "The Hindu"
    assert payload["canonical_url"] == article.canonical_url
    assert payload["source_feed_url"] == article.source_feed_url
    assert payload["dbt_evidence_type"] == "NEWS_ARTICLE"
    assert "weather_measurements" in payload
    assert payload["weather_measurements"]["rainfall"]["value"] == 150.0
    assert payload["weather_measurements"]["wind_speed"]["value"] == 75.0


def test_7_non_weather_rejection_and_unknown_location():
    connector = NewsWebsiteConnector()

    # Non-weather article must be rejected
    non_weather = NewsArticleItem(
        publisher="NDTV",
        title="Cricket World Cup Final: Team India Prepares",
        canonical_url="https://ndtv.com/cricket-news/123",
        summary="The national cricket team begins practice sessions ahead of the championship.",
    )
    assert connector.parse(non_weather) is None

    # Weather article with unknown location must be quarantined
    unknown_loc_article = NewsArticleItem(
        publisher="Global Weather",
        title="Unusual Dense Fog Observed",
        canonical_url="https://example.org/fog-article",
        summary="Dense fog and cold temperature enveloped the valley this morning.",
    )
    raw_event = connector.parse(unknown_loc_article)
    assert raw_event is not None
    assert raw_event.is_india_valid is False
    assert raw_event.is_quarantined is True
    assert raw_event.quarantine_reason == "UNKNOWN_LOCATION"


# ==============================================================================
# 5. Polling Lifecycle, Rate Limits & Telemetry Invariants
# ==============================================================================

@pytest.mark.asyncio
async def test_8_polling_and_mathematical_telemetry_consistency():
    mock_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Delhi Rainfall Alert: Traffic Diverted Due to Waterlogging</title>
          <link>https://example-news.in/delhi-rain-waterlogging?utm_source=rss</link>
          <description>80 mm rain lashed Delhi causing waterlogging at Minto Bridge. #DelhiWeather</description>
          <pubDate>Fri, 02 Oct 2026 08:00:00 +0530</pubDate>
        </item>
        <item>
          <title>Tech Startup Funding News</title>
          <link>https://example-news.in/startup-funding</link>
          <description>Fintech firm raises $20M in Series A round.</description>
        </item>
      </channel>
    </rss>
    """

    mock_source = NewsSourceDefinition(
        source_id="mock-news-source",
        publisher_name="Mock News Network",
        domains=["example-news.in"],
        feed_urls=["https://example-news.in/rss"],
    )

    registry = NewsSourceRegistry([mock_source])
    connector = NewsWebsiteConnector(registry=registry)
    connector.is_running = True

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = httpx.Response(
            status_code=200,
            text=mock_rss,
            request=httpx.Request("GET", "https://example-news.in/rss"),
        )
        mock_get.return_value = mock_response

        events = await connector.poll()

    m = connector.metrics
    # Mathematical Invariants:
    # records_fetched = weather_relevant + rejected_non_weather
    assert m.records_fetched == m.weather_relevant + m.rejected_non_weather
    assert m.weather_relevant == m.accepted_india + m.quarantined_foreign + m.quarantined_unknown_location
    assert m.records_accepted == m.accepted_india
    assert len(events) == m.accepted_india
    assert connector.sources_healthy_count == 1
    assert connector.sources_failed_count == 0


@pytest.mark.asyncio
async def test_9_dead_feed_and_rate_limit_handling():
    source_dead = NewsSourceDefinition(
        source_id="dead-source",
        publisher_name="Dead Source",
        domains=["dead.invalid"],
        feed_urls=["https://dead.invalid/feed"],
    )
    source_429 = NewsSourceDefinition(
        source_id="rate-limited-source",
        publisher_name="Rate Limited Source",
        domains=["ratelimit.invalid"],
        feed_urls=["https://ratelimit.invalid/feed"],
    )

    registry = NewsSourceRegistry([source_dead, source_429])
    connector = NewsWebsiteConnector(registry=registry)
    connector.is_running = True

    async def mock_get_side_effect(url, **kwargs):
        if "dead" in str(url):
            raise httpx.ConnectError("Connection refused")
        elif "ratelimit" in str(url):
            return httpx.Response(429, request=httpx.Request("GET", str(url)))
        return httpx.Response(200, text="<rss></rss>", request=httpx.Request("GET", str(url)))

    with patch("httpx.AsyncClient.get", side_effect=mock_get_side_effect):
        events = await connector.poll()

    assert len(events) == 0
    assert connector.parsing_errors_count >= 1
    assert connector.rate_limit_responses_count >= 1
    assert connector.sources_failed_count == 2


# ==============================================================================
# 6. Deduplication Across Channels & Pipeline Trace Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_10_cross_channel_deduplication():
    # Same article arriving via RSS and another via category page
    connector = NewsWebsiteConnector()

    art1 = NewsArticleItem(
        publisher="Times of India",
        title="Bengaluru Rain: Heavy Downpour Causes Waterlogging",
        canonical_url="https://timesofindia.indiatimes.com/bengaluru-rain-today?utm_source=rss",
        summary="Over 95 mm rainfall recorded in Bengaluru. #BengaluruRain",
        published_at=datetime(2026, 10, 2, 8, 0, 0, tzinfo=timezone.utc),
    )

    art2 = NewsArticleItem(
        publisher="Times of India",
        title="Bengaluru Rain: Heavy Downpour Causes Waterlogging",
        canonical_url="https://timesofindia.indiatimes.com/bengaluru-rain-today?utm_medium=web",
        summary="Over 95 mm rainfall recorded in Bengaluru. #BengaluruRain",
        published_at=datetime(2026, 10, 2, 8, 0, 0, tzinfo=timezone.utc),
    )

    raw1 = connector.parse(art1)
    raw2 = connector.parse(art2)
    assert raw1 is not None and raw2 is not None

    # Because tracking parameters are stripped, both point to identical normalized URLs and idempotency keys
    assert raw1.external_id == raw2.external_id
    assert raw1.idempotency_key == raw2.idempotency_key


@pytest.mark.asyncio
async def test_11_end_to_end_canonical_pipeline_trace():
    connector = NewsWebsiteConnector()
    article = NewsArticleItem(
        publisher="Press Information Bureau",
        title="IMD Special Weather Bulletin: Severe Thunderstorm over Assam and Meghalaya",
        canonical_url="https://pib.gov.in/PressReleasePage.aspx?PRID=1982734",
        summary="Thunderstorm with squall winds up to 60 km/h and isolated heavy rainfall over Assam.",
        published_at=datetime(2026, 10, 2, 9, 30, 0, tzinfo=timezone.utc),
        source_feed_url="https://pib.gov.in/rss",
    )

    raw_event = connector.parse(article)
    assert isinstance(raw_event, CanonicalRawEvent)
    assert raw_event.source_type == "NEWS"
    assert raw_event.is_india_valid is True

    # Pass into canonical normalizer
    norm_event = await normalize_raw_event(raw_event)
    assert isinstance(norm_event, NormalizedEvent)
    assert norm_event.state == "Assam"
    assert norm_event.latitude is None  # Zero fake GPS
    assert norm_event.primary_category in ("THUNDERSTORM", "RAINFALL")
    assert norm_event.tracking_id.startswith("SP-")
    assert norm_event.idempotency_key is not None
    assert norm_event.is_quarantined is False
    assert norm_event.metadata["raw_payload"]["publisher"] == "Press Information Bureau"


# ==============================================================================
# 7. Live Public News Feed Smoke Test
# ==============================================================================

@pytest.mark.asyncio
async def test_12_live_news_feed_smoke_test():
    """
    Live smoke test against real public Indian news RSS feed.
    Does not crash if internet is unavailable.
    """
    live_feed = "https://ddnews.gov.in/feed/"
    dummy_source = NewsSourceDefinition(
        source_id="live-dd-news",
        publisher_name="DD News",
        domains=["ddnews.gov.in"],
        feed_urls=[live_feed],
    )
    connector = NewsWebsiteConnector()
    headers = {"User-Agent": connector.user_agent}

    try:
        async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
            resp = await client.get(live_feed)
            if resp.status_code == 200 and resp.text:
                items = connector._parse_feed_xml(resp.text, dummy_source, live_feed)
                assert isinstance(items, list)
                if items:
                    assert items[0].publisher == "DD News"
                    assert len(items[0].canonical_url) > 0
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        pytest.skip(f"Live network feed unavailable during smoke test: {exc}")
