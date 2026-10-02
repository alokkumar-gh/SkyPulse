import io
import pytest

from connectors.demo_connector import DemoConnector
from connectors.weather_api_connector import WeatherAPIConnector
from connectors.government_connector import GovernmentFeedConnector
from connectors.rss_connector import RSSFeedConnector
from connectors.historical_batch import HistoricalBatchIngestion
from connectors.schema import ConnectorStatusEnum, CanonicalRawEvent


@pytest.mark.asyncio
async def test_demo_connector_all_seven_categories():
    """Verify DemoConnector produces all 7 core problem statement categories with is_demo=True."""
    connector = DemoConnector(scenario="mixed_national")
    await connector.start()

    observed_categories = set()
    for _ in range(30):
        events = await connector.poll()
        for ev in events:
            assert ev.is_demo is True
            assert ev.source_type == "DEMO"
            assert ev.latitude is not None and ev.longitude is not None
            assert ev.city is not None and ev.state is not None
            observed_categories.add(ev.suggested_category)

    await connector.stop()

    required_categories = {
        "RAINFALL",
        "THUNDERSTORM",
        "FLOODING",
        "HEATWAVE",
        "FOG",
        "DUST_STORM",
        "STRONG_WINDS",
    }
    assert required_categories.issubset(observed_categories), (
        f"Missing categories in demo stream: {required_categories - observed_categories}"
    )


@pytest.mark.asyncio
async def test_demo_connector_scenarios():
    """Verify different demo scenarios: burst, storm_cluster, flood_cluster."""
    # Burst scenario: produces at least 10 events
    burst_conn = DemoConnector(scenario="burst")
    burst_events = await burst_conn.poll()
    assert len(burst_events) == 10
    assert all(e.is_demo for e in burst_events)

    # Storm cluster scenario
    storm_conn = DemoConnector(scenario="storm_cluster")
    storm_events = await storm_conn.poll()
    assert len(storm_events) == 5
    assert all(e.suggested_category in ["THUNDERSTORM", "RAINFALL", "STRONG_WINDS"] for e in storm_events)

    # Flood cluster scenario
    flood_conn = DemoConnector(scenario="flood_cluster")
    flood_events = await flood_conn.poll()
    assert len(flood_events) == 5
    assert all(e.suggested_category == "FLOODING" for e in flood_events)


@pytest.mark.asyncio
async def test_weather_api_connector_unconfigured_status():
    """Verify WeatherAPIConnector reports NOT_CONFIGURED when API key is missing."""
    conn = WeatherAPIConnector(source_id="test-wapi", api_key="")
    assert conn.status == ConnectorStatusEnum.NOT_CONFIGURED

    # Poll returns empty list without error
    events = await conn.poll()
    assert events == []


def test_weather_api_connector_parsing():
    """Verify raw WeatherAPI JSON payload parsing into CanonicalRawEvent."""
    conn = WeatherAPIConnector(source_id="test-wapi", api_key="dummy_key")
    raw_payload = {
        "location": {"name": "Mumbai", "region": "Maharashtra", "lat": 18.97, "lon": 72.82},
        "current": {
            "last_updated_epoch": 1727721600,
            "temp_c": 31.0,
            "humidity": 85,
            "wind_kph": 28.0,
            "condition": {"text": "Heavy rain at times"},
        },
    }
    event = conn.parse(raw_payload)
    assert isinstance(event, CanonicalRawEvent)
    assert event.source_type == "WEATHER_API"
    assert event.city == "Mumbai"
    assert event.suggested_category == "RAINFALL"
    assert event.is_demo is False


@pytest.mark.asyncio
async def test_rss_feed_connector_parsing():
    """Verify RSSFeedConnector parsing valid RSS XML and handling malformed XML."""
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Weather Warning Feed</title>
        <item>
          <title>Severe Thunderstorm Warning</title>
          <description>Lightning squall expected over coastal Odisha districts.</description>
          <guid>adv-2026-09-odisha</guid>
        </item>
      </channel>
    </rss>"""
    conn = RSSFeedConnector(source_id="test-rss", feed_url="http://mock.feed/rss")
    events = conn._parse_feed_xml(rss_xml)
    assert len(events) == 1
    assert "Severe Thunderstorm Warning" in events[0].text
    assert events[0].external_id == "adv-2026-09-odisha"

    # Malformed XML handles gracefully
    malformed_events = conn._parse_feed_xml("<invalid xml><not closed>")
    assert malformed_events == []


@pytest.mark.asyncio
async def test_government_connector_status():
    """Verify GovernmentFeedConnector handles missing feed_url gracefully."""
    conn = GovernmentFeedConnector(source_id="test-gov", feed_url=None)
    assert conn.status == ConnectorStatusEnum.NOT_CONFIGURED
    events = await conn.poll()
    assert events == []


@pytest.mark.asyncio
async def test_historical_batch_csv_ingestion():
    """Verify HistoricalBatchIngestion streams valid rows and filters invalid coordinates."""
    csv_data = """description,latitude,longitude,category,city,severity
Cloudburst over Dehradun valley,30.3165,78.0322,RAINFALL,Dehradun,3
Heavy flooding in London,51.5074,0.1278,FLOODING,London,3
Heatwave in Nagpur,21.1458,79.0882,HEATWAVE,Nagpur,2
,19.0760,72.8777,FOG,Mumbai,1
"""
    engine = HistoricalBatchIngestion(source_id="hist-test-01")
    stream = io.StringIO(csv_data)

    total_valid = 0
    total_invalid = 0

    async for valid_batch, error_batch in engine.ingest_csv_stream(stream, batch_size=2):
        total_valid += len(valid_batch)
        total_invalid += len(error_batch)

    # Dehradun (valid) and Nagpur (valid) -> 2 valid
    # London (out of India lat) -> 1 invalid
    # Missing text row -> 1 invalid
    assert total_valid == 2
    assert total_invalid == 2
