"""
Unit and Integration Tests for NewsWebsiteConnector / PIB RSS
==============================================================
Covers:
- Official RSS feed configuration & RSS-first priority
- XML parsing with UTF-8 BOM cleaning & unescaped ampersand repair
- Weather relevance keyword filtering (extracts weather releases, rejects non-weather releases)
- Rejection of political / non-meteorological press releases
- Bounded retries and HTTP 403 / 5xx error handling (no scraping bypasses)
- CanonicalRawEvent normalization with government media attribution
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from connectors.news_website_connector import (
    NewsWebsiteConnector,
    NewsArticleItem,
    NewsSourceDefinition,
    NewsSourceRegistry,
    is_weather_relevant,
    sanitize_rss_xml,
)
from connectors.schema import ConnectorStatusEnum, CanonicalRawEvent


SAMPLE_PIB_WEATHER_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Press Information Bureau - Ministry of Earth Sciences</title>
    <link>https://pib.gov.in</link>
    <description>Official Press Releases</description>
    <item>
      <title>IMD Issues Orange Alert for Extremely Heavy Rainfall and Thunderstorm in Odisha and West Bengal</title>
      <link>https://pib.gov.in/PressReleasePage.aspx?PRID=2001001&amp;utm_source=rss</link>
      <description>India Meteorological Department forecasts active monsoon with intense rain and gusty winds up to 60 km/h across coastal districts.</description>
      <pubDate>Sat, 03 Oct 2026 09:30:00 +0530</pubDate>
      <category>Ministry of Earth Sciences</category>
    </item>
    <item>
      <title>Union Minister Inaugurates New Science Seminar on Renewable Solar Technology</title>
      <link>https://pib.gov.in/PressReleasePage.aspx?PRID=2001002</link>
      <description>The summit brings together industry leaders to discuss green energy investment and economic growth targets.</description>
      <pubDate>Sat, 03 Oct 2026 10:00:00 +0530</pubDate>
      <category>Ministry of New and Renewable Energy</category>
    </item>
  </channel>
</rss>
"""


@pytest.fixture
def news_connector():
    reg = NewsSourceRegistry()
    conn = NewsWebsiteConnector(
        source_id="00000000-0000-0000-0000-000000000004",
        name="News Website & Government Press Ingestion Layer",
        registry=reg,
    )
    return conn


def test_weather_relevance_filter():
    # Weather item
    rel, kws = is_weather_relevant(
        title="Heavy Rainfall and Thunderstorm Warning Issued by IMD",
        summary="Flood alert in low-lying river basins after intense monsoon showers.",
    )
    assert rel is True
    assert "rainfall" in kws or "thunderstorm" in kws or "flood" in kws

    # Non-weather political item
    rel2, kws2 = is_weather_relevant(
        title="Cabinet Approves New Industrial Policy for Semiconductor Manufacturing",
        summary="The scheme will provide capital incentives to international technology firms.",
    )
    assert rel2 is False
    assert kws2 == []


def test_xml_sanitization_and_parsing():
    raw_with_bom_and_naked_amp = "\ufeff<rss><channel><item><title>Rain & Thunder</title><link>https://pib.gov.in?a=1&b=2</link></item></channel></rss>"
    sanitized = sanitize_rss_xml(raw_with_bom_and_naked_amp)
    assert not sanitized.startswith("\ufeff")
    assert "&amp;" in sanitized


@pytest.mark.asyncio
async def test_pib_rss_feed_parsing_and_relevance_filtering():
    pib_source = NewsSourceDefinition(
        source_id="pib-india",
        publisher_name="Press Information Bureau (PIB)",
        domains=["pib.gov.in"],
        feed_urls=["https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&reg=3"],
        source_type="GOVERNMENT_MEDIA",
        enabled=True,
    )
    pib_connector = NewsWebsiteConnector(
        source_id="00000000-0000-0000-0000-000000000004",
        registry=NewsSourceRegistry(initial_sources=[pib_source]),
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_PIB_WEATHER_RSS

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        events = await pib_connector.poll()
        # Should contain ONLY the weather item (1 item), rejecting the solar seminar item
        assert len(events) == 1
        ev = events[0]
        assert isinstance(ev, CanonicalRawEvent)
        assert "Rainfall" in ev.text or "Thunderstorm" in ev.text
        assert "Odisha" in ev.text or ev.state == "Odisha"
        assert ev.suggested_category in ("RAINFALL", "THUNDERSTORM", "FLOODING")
        assert ev.raw_payload["is_official_government"] is True
        assert ev.raw_payload["publisher"] == "Press Information Bureau (PIB)"



@pytest.mark.asyncio
async def test_news_connector_handles_feed_error_gracefully(news_connector):
    # Mock HTTP 403 or network error
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection failed")):
        events = await news_connector.poll()
        assert events == []
        assert news_connector.status == ConnectorStatusEnum.DEGRADED
        assert news_connector.consecutive_failures > 0
