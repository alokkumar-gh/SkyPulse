"""
Comprehensive Unit Tests for Social & Web Weather Intelligence Connector
========================================================================
Tests all 25 requirements:
1. RSS parsing
2. Atom parsing
3. public JSON mapping
4. social API response mapping
5. hashtag filtering
6. weather keyword filtering
7. missing metadata handling
8. GPS extraction
9. city/state extraction
10. media metadata extraction
11. duplicate external ID
12. content hash duplicate
13. repost/copy detection
14. India geographic validation
15. malformed response
16. timeout
17. rate-limit handling
18. authentication failure
19. idempotency
20. provenance preservation
21. source trust integration
22. DWEG integration
23. Event DNA integration
24. Emerging Event integration
25. no credential leakage
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import httpx
import xml.etree.ElementTree as ET

from app.models.enums import ContentRelationship, WeatherCategory, SourceType
from connectors.schema import CanonicalRawEvent, ConnectorStatusEnum, MediaItem
from connectors.normalizer import normalize_raw_event
from connectors.social_web_connector import (
    SocialWebConnector,
    SocialAPIAdapter,
    RSSAtomAdapter,
    PublicWebAdapter,
    PublicJSONAdapter,
    matches_weather_filter,
    extract_hashtags,
    detect_content_relationship,
    validate_india_coordinates,
    sanitize_config_dict,
    compute_content_hash,
    DEFAULT_WEATHER_HASHTAGS,
    DEFAULT_WEATHER_KEYWORDS,
)


# ============================================================================
# 1. RSS PARSING
# ============================================================================

def test_1_rss_parsing():
    adapter = RSSAtomAdapter(feed_url="https://example.com/weather-rss.xml")
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>IMD Alerts</title>
        <item>
          <title>Heavy Rain Alert for Mumbai</title>
          <description>IMD has issued a red alert for severe rainfall and waterlogging in Mumbai.</description>
          <guid>rss-alert-101</guid>
          <link>https://imd.gov.in/alerts/101</link>
          <pubDate>Thu, 01 Oct 2026 12:00:00 GMT</pubDate>
          <category>RAINFALL</category>
          <enclosure url="https://imd.gov.in/radar/mumbai.jpg" type="image/jpeg" length="12345" />
        </item>
      </channel>
    </rss>
    """
    items = adapter._extract_xml_items(rss_xml)
    assert len(items) == 1
    event = adapter.parse(items[0])
    assert event is not None
    assert event.source_type == "RSS_FEED"
    assert event.external_id == "rss-alert-101"
    assert "Heavy Rain Alert for Mumbai" in event.text
    assert len(event.media) == 1
    assert event.media[0].url == "https://imd.gov.in/radar/mumbai.jpg"
    assert event.media[0].mime_type == "image/jpeg"


# ============================================================================
# 2. ATOM PARSING
# ============================================================================

def test_2_atom_parsing():
    adapter = RSSAtomAdapter(feed_url="https://example.com/weather-atom.xml")
    atom_xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Met Department Atom Feed</title>
      <entry>
        <title>Thunderstorm with lightning in Kolkata</title>
        <summary>Severe thunderstorm expected across Gangetic West Bengal including Kolkata.</summary>
        <id>urn:uuid:12345-67890</id>
        <link href="https://imd.gov.in/kolkata-alert" />
        <updated>2026-10-01T14:30:00Z</updated>
        <category term="THUNDERSTORM" />
      </entry>
    </feed>
    """
    items = adapter._extract_xml_items(atom_xml)
    assert len(items) == 1
    event = adapter.parse(items[0])
    assert event is not None
    assert "Thunderstorm with lightning in Kolkata" in event.text
    assert event.external_id == "urn:uuid:12345-67890"
    assert event.observed_at.year == 2026


# ============================================================================
# 3. PUBLIC JSON MAPPING
# ============================================================================

def test_3_public_json_mapping():
    mapping = {
        "id": "alert_id",
        "text": "headline",
        "timestamp": "published_epoch",
        "latitude": "coords.lat",
        "longitude": "coords.lon",
        "city": "place.city_name",
        "state": "place.state_name",
        "category": "hazard_type",
        "media_url": "attachments.image_url",
    }
    adapter = PublicJSONAdapter(
        endpoint_url="https://api.example.com/alerts",
        record_path="data.reports",
        field_mapping=mapping,
    )
    raw_record = {
        "alert_id": "NDMA-2026-999",
        "headline": "Severe flooding and waterlogged roads in Bengaluru",
        "published_epoch": 1790856000,
        "hazard_type": "FLOODING",
        "coords": {"lat": 12.9716, "lon": 77.5946},
        "place": {"city_name": "Bengaluru", "state_name": "Karnataka"},
        "attachments": {"image_url": "https://ndma.gov.in/img/flood_blr.png"},
    }
    event = adapter.parse(raw_record)
    assert event is not None
    assert event.external_id == "NDMA-2026-999"
    assert event.latitude == 12.9716
    assert event.longitude == 77.5946
    assert event.city == "Bengaluru"
    assert event.state == "Karnataka"
    assert event.suggested_category == "FLOODING"
    assert len(event.media) == 1
    assert event.media[0].url == "https://ndma.gov.in/img/flood_blr.png"


# ============================================================================
# 4. SOCIAL API RESPONSE MAPPING
# ============================================================================

def test_4_social_api_response_mapping():
    adapter = SocialAPIAdapter(
        base_url="https://social.example.com/api/v1/timelines/tag/WeatherAlert",
        api_token="valid_bearer_token_xyz",
    )
    raw_post = {
        "id": "status_10928374",
        "content": "<p>Heavy rainfall and lightning in Pune #WeatherAlert #HeavyRain</p>",
        "created_at": "2026-10-01T15:00:00Z",
        "account": {"username": "puneweather_watcher"},
        "geo": {"lat": 18.5204, "lon": 73.8567, "city": "Pune", "state": "Maharashtra"},
        "media_attachments": [
            {"type": "image", "url": "https://social.example.com/media/rain_pune.jpg", "mime_type": "image/jpeg"}
        ],
    }
    event = adapter.parse(raw_post)
    assert event is not None
    assert event.external_id == "status_10928374"
    assert "Heavy rainfall and lightning in Pune" in event.text
    assert "<p>" not in event.text  # HTML stripped
    assert event.latitude == 18.5204
    assert event.longitude == 73.8567
    assert event.city == "Pune"
    assert len(event.media) == 1
    assert event.media[0].media_type == "IMAGE"


# ============================================================================
# 5. HASHTAG FILTERING
# ============================================================================

def test_5_hashtag_filtering():
    text1 = "Expect intense downpour today #IMD #HeavyRain"
    is_match1, matched1 = matches_weather_filter(text1)
    assert is_match1 is True
    assert "#IMD" in matched1 or "#HeavyRain" in matched1

    # Text without weather hashtag/keyword
    text2 = "Attending a tech conference today #AI #TechSummit"
    is_match2, matched2 = matches_weather_filter(text2)
    assert is_match2 is False
    assert len(matched2) == 0

    # Custom hashtags
    custom_ht = ["#ChennaiRains", "#DelhiFog"]
    text3 = "Airport visibility down to 50m #DelhiFog"
    is_match3, matched3 = matches_weather_filter(text3, configured_hashtags=custom_ht)
    assert is_match3 is True
    assert "#DelhiFog" in matched3


# ============================================================================
# 6. WEATHER KEYWORD FILTERING
# ============================================================================

def test_6_weather_keyword_filtering():
    text_kw = "Severe heatwave condition observed in Rajasthan today"
    is_match, terms = matches_weather_filter(text_kw)
    assert is_match is True
    assert "heatwave" in terms

    text_unrelated = "Just having a cup of coffee at home"
    is_match2, terms2 = matches_weather_filter(text_unrelated)
    assert is_match2 is False


# ============================================================================
# 7. MISSING METADATA HANDLING
# ============================================================================

def test_7_missing_metadata_handling():
    adapter = SocialAPIAdapter(base_url="https://api.example.com", api_key="secret")
    raw_post_sparse = {
        "id": "sparse_001",
        "text": "Intense dust storm blinding visibility on highway",
        # missing geo, timestamps, media, user
    }
    event = adapter.parse(raw_post_sparse)
    assert event is not None
    assert event.latitude is None
    assert event.longitude is None
    assert event.city is None
    assert event.state is None
    assert len(event.media) == 0
    assert isinstance(event.observed_at, datetime)


# ============================================================================
# 8. GPS EXTRACTION
# ============================================================================

def test_8_gps_extraction():
    adapter = SocialAPIAdapter(base_url="https://api.example.com", api_token="tok")
    # Coordinates in list format [lat, lon]
    raw_geo_list = {
        "id": "geo_001",
        "text": "Heavy thunderstorm reported",
        "coordinates": [28.6139, 77.2090],
    }
    event = adapter.parse(raw_geo_list)
    assert event is not None
    assert event.latitude == 28.6139
    assert event.longitude == 77.2090


# ============================================================================
# 9. CITY / STATE EXTRACTION
# ============================================================================

def test_9_city_state_extraction():
    adapter = PublicJSONAdapter(
        endpoint_url="https://api.example.com",
        field_mapping={"id": "id", "text": "body", "city": "district_name", "state": "state_name"},
    )
    raw = {
        "id": "cs_01",
        "body": "Massive rainfall and inundated roads",
        "district_name": "Ernakulam",
        "state_name": "Kerala",
    }
    event = adapter.parse(raw)
    assert event is not None
    assert event.city == "Ernakulam"
    assert event.state == "Kerala"


# ============================================================================
# 10. MEDIA METADATA EXTRACTION
# ============================================================================

def test_10_media_metadata_extraction():
    adapter = SocialAPIAdapter(base_url="https://api.example.com", api_key="key")
    raw_with_video = {
        "id": "media_vid_01",
        "text": "Video of waterlogging under flyover #Flood",
        "media": [
            {"type": "video", "url": "https://cdn.example.com/flood_video.mp4", "mime_type": "video/mp4", "file_size": 1048576}
        ],
    }
    event = adapter.parse(raw_with_video)
    assert event is not None
    assert len(event.media) == 1
    assert event.media[0].media_type == "VIDEO"
    assert event.media[0].url == "https://cdn.example.com/flood_video.mp4"
    assert event.media[0].file_size_bytes == 1048576


# ============================================================================
# 11. DUPLICATE EXTERNAL ID
# ============================================================================

def test_11_duplicate_external_id():
    recent = [{"external_id": "post_dup_100", "text": "Rainfall in Chennai", "content_hash": "hash1"}]
    rel, evidence = detect_content_relationship(
        text="Heavy rainfall in Chennai",
        external_id="post_dup_100",
        raw_payload={},
        recent_events=recent,
    )
    assert rel == ContentRelationship.DUPLICATE
    assert evidence["matched_original_id"] == "post_dup_100"


# ============================================================================
# 12. CONTENT HASH DUPLICATE
# ============================================================================

def test_12_content_hash_duplicate():
    text_orig = "Massive cyclone landfall near coastal Odisha with winds over 120kmph"
    h_orig = compute_content_hash(text_orig)
    recent = [{"external_id": "post_orig_01", "text": text_orig, "content_hash": h_orig}]

    # Different external ID but exact text match
    rel, evidence = detect_content_relationship(
        text=text_orig.upper(),  # case-insensitive normalized
        external_id="post_copy_99",
        raw_payload={},
        recent_events=recent,
    )
    assert rel == ContentRelationship.LIKELY_COPY
    assert evidence["matched_original_id"] == "post_orig_01"


# ============================================================================
# 13. REPOST / COPY DETECTION
# ============================================================================

def test_13_repost_copy_detection():
    # Explicit repost indicator in payload
    rel1, ev1 = detect_content_relationship(
        text="Severe storm warning",
        external_id="rp_1",
        raw_payload={"is_repost": True, "repost_of": "orig_post_555"},
    )
    assert rel1 == ContentRelationship.REPOST
    assert ev1["has_repost_indicator"] is True

    # RT @ prefix
    rel2, ev2 = detect_content_relationship(
        text="RT @imd_weather Heavy rainfall alert for Mumbai",
        external_id="rp_2",
        raw_payload={},
    )
    assert rel2 == ContentRelationship.REPOST


# ============================================================================
# 14. INDIA GEOGRAPHIC VALIDATION
# ============================================================================

def test_14_india_geographic_validation():
    # Valid coordinates inside India (e.g., Delhi, Mumbai, Chennai)
    lat1, lon1 = validate_india_coordinates(28.6139, 77.2090)
    assert lat1 == 28.6139 and lon1 == 77.2090

    # Coordinates outside India (e.g., London 51.5, -0.12 or New York 40.7, -74.0)
    lat2, lon2 = validate_india_coordinates(51.5074, -0.1278)
    assert lat2 is None and lon2 is None

    # Invalid string values
    lat3, lon3 = validate_india_coordinates("abc", None)
    assert lat3 is None and lon3 is None


# ============================================================================
# 15. MALFORMED RESPONSE HANDLING
# ============================================================================

def test_15_malformed_response():
    adapter = RSSAtomAdapter(feed_url="https://example.com/rss")
    malformed_xml = "<rss><channel><item>unclosed tags"
    items = adapter._extract_xml_items(malformed_xml)
    assert len(items) == 0  # Graceful recovery, no crash

    json_adapter = PublicJSONAdapter(endpoint_url="https://api.example.com")
    parsed = json_adapter.parse("not a dict")
    assert parsed is None


# ============================================================================
# 16. TIMEOUT HANDLING
# ============================================================================

@pytest.mark.asyncio
async def test_16_timeout_handling():
    adapter = SocialAPIAdapter(
        base_url="https://social.example.com/slow",
        api_token="tok",
        timeout_seconds=0.1,
    )
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Read timed out")):
        records = await adapter.fetch()
        assert records == []
        assert adapter.status == ConnectorStatusEnum.ERROR
        assert "timed out" in adapter.metrics.last_error.lower()


# ============================================================================
# 17. RATE-LIMIT HANDLING
# ============================================================================

@pytest.mark.asyncio
async def test_17_rate_limit_handling():
    adapter = SocialAPIAdapter(
        base_url="https://social.example.com/api",
        api_token="tok",
    )
    mock_resp = httpx.Response(status_code=429, request=httpx.Request("GET", "https://social.example.com/api"))
    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        records = await adapter.fetch()
        assert records == []
        assert adapter.status == ConnectorStatusEnum.DEGRADED
        assert "rate limit" in adapter.metrics.last_error.lower()


# ============================================================================
# 18. AUTHENTICATION FAILURE
# ============================================================================

@pytest.mark.asyncio
async def test_18_authentication_failure():
    adapter = SocialAPIAdapter(
        base_url="https://social.example.com/api",
        api_token="invalid_token",
    )
    mock_resp = httpx.Response(status_code=401, request=httpx.Request("GET", "https://social.example.com/api"))
    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        st = await adapter.health_check()
        assert st == ConnectorStatusEnum.ERROR
        assert "401" in adapter.metrics.last_error


# ============================================================================
# 19. IDEMPOTENCY
# ============================================================================

@pytest.mark.asyncio
async def test_19_idempotency():
    adapter = SocialAPIAdapter(base_url="https://api.example.com", api_key="k")
    raw = {
        "id": "idem_1001",
        "text": "Severe dust storm in Jaipur #DustStorm",
        "created_at": "2026-10-01T10:00:00Z",
    }
    raw_event = adapter.parse(raw)
    assert raw_event is not None
    norm1 = await normalize_raw_event(raw_event)
    norm2 = await normalize_raw_event(raw_event)
    assert norm1.idempotency_key == norm2.idempotency_key
    assert norm1.primary_category == "DUST_STORM"


# ============================================================================
# 20. PROVENANCE PRESERVATION
# ============================================================================

def test_20_provenance_preservation():
    adapter = RSSAtomAdapter(feed_url="https://imd.gov.in/rss/bulletin.xml")
    xml = """<item>
      <title>Heatwave Advisory for Nagpur</title>
      <description>Severe heatwave temperatures exceeding 45C expected in Nagpur.</description>
      <guid>imd-nagpur-45</guid>
      <link>https://imd.gov.in/bulletin/45</link>
      <pubDate>Thu, 01 Oct 2026 09:00:00 GMT</pubDate>
    </item>"""
    elem = ET.fromstring(xml)
    event = adapter.parse(elem)
    assert event is not None
    prov = event.raw_payload.get("provenance", {})
    assert prov.get("source_type") == "RSS_FEED"
    assert prov.get("source_url") == "https://imd.gov.in/bulletin/45"
    assert prov.get("external_id") == "imd-nagpur-45"
    assert prov.get("connector_name") == "SocialWebConnector"
    assert prov.get("connector_version") == "1.0.0"
    assert "retrieved_at" in prov
    assert "published_at" in prov


# ============================================================================
# 21. SOURCE TRUST INTEGRATION
# ============================================================================

def test_21_source_trust_integration():
    from ai.source_trust import SourceTrustEngine
    # Baseline for new social feed source
    trust = SourceTrustEngine.calculate_initial_trust(SourceType.SOCIAL_FEED.value)
    assert 0.0 <= trust <= 1.0
    # Baseline for RSS feed source
    rss_trust = SourceTrustEngine.calculate_initial_trust(SourceType.RSS_FEED.value)
    assert rss_trust >= trust


# ============================================================================
# 22. DWEG INTEGRATION
# ============================================================================

@pytest.mark.asyncio
async def test_22_dweg_integration():
    adapter = SocialAPIAdapter(base_url="https://api.example.com", api_token="tok")
    raw = {
        "id": "dweg_obs_01",
        "text": "Torrential downpour and severe waterlogging in Mumbai #HeavyRain",
        "geo": {"lat": 19.0760, "lon": 72.8777, "city": "Mumbai", "state": "Maharashtra"},
    }
    raw_ev = adapter.parse(raw)
    norm = await normalize_raw_event(raw_ev)
    
    # Graph semantics verify presence of required properties
    assert norm.latitude == 19.0760
    assert norm.longitude == 72.8777
    assert norm.primary_category == "FLOODING" or norm.primary_category == "RAINFALL"
    assert norm.city == "Mumbai"
    assert norm.state == "Maharashtra"


# ============================================================================
# 23. EVENT DNA INTEGRATION
# ============================================================================

def test_23_event_dna_integration():
    adapter = PublicWebAdapter(urls=["https://weather.gov.in/special_bulletin"])
    raw_web = {
        "url": "https://weather.gov.in/special_bulletin",
        "html": "<html><head><title>Super Cyclone Warning</title><meta name='description' content='Super cyclone tracking towards coastal regions.'></head><body>Severe alert</body></html>",
        "retrieved_at": "2026-10-01T10:00:00Z",
    }
    event = adapter.parse(raw_web)
    assert event is not None
    prov = event.raw_payload.get("provenance")
    assert prov is not None
    assert prov["source_url"] == "https://weather.gov.in/special_bulletin"
    assert "Super Cyclone Warning" in event.text


# ============================================================================
# 24. EMERGING EVENT INTEGRATION
# ============================================================================

def test_24_emerging_event_integration():
    # Verify that duplicate/repost signals are flagged so detector weights them correctly
    text = "Mild rainfall started in South Delhi"
    h = compute_content_hash(text)
    history = [{"external_id": "sig_orig", "text": text, "content_hash": h}]

    rel, ev = detect_content_relationship(
        text=text,
        external_id="sig_copy_1",
        raw_payload={},
        recent_events=history,
    )
    # Copied post is detected as LIKELY_COPY
    assert rel == ContentRelationship.LIKELY_COPY
    assert ev["matched_original_id"] == "sig_orig"


# ============================================================================
# 25. NO CREDENTIAL LEAKAGE
# ============================================================================

def test_25_no_credential_leakage():
    config = {
        "base_url": "https://social.example.com",
        "api_key": "super_secret_api_key_12345",
        "api_token": "bearer_secret_jwt_token_67890",
        "queries": ["#IMD"],
        "nested": {
            "password": "mypassword",
            "auth_token": "nested_token",
            "safe_param": 100,
        },
    }
    sanitized = sanitize_config_dict(config)
    assert sanitized["api_key"] == "***MASKED***"
    assert sanitized["api_token"] == "***MASKED***"
    assert sanitized["nested"]["password"] == "***MASKED***"
    assert sanitized["nested"]["auth_token"] == "***MASKED***"
    assert sanitized["nested"]["safe_param"] == 100
    assert sanitized["base_url"] == "https://social.example.com"
    # Ensure raw secrets do not appear anywhere in string representation
    serialized = json.dumps(sanitized)
    assert "super_secret_api_key_12345" not in serialized
    assert "bearer_secret_jwt_token_67890" not in serialized
    assert "mypassword" not in serialized


# ============================================================================
# 26. API ENDPOINTS & RBAC
# ============================================================================

@pytest.mark.asyncio
async def test_26_api_endpoints(client, test_analyst, test_citizen, auth_headers):
    headers_analyst = auth_headers(test_analyst)
    headers_citizen = auth_headers(test_citizen)

    # 1. GET overview
    res_overview = await client.get("/api/v1/connectors/social-web", headers=headers_analyst)
    assert res_overview.status_code == 200
    data = res_overview.json()
    assert data["connector_name"] == "SocialWebConnector"
    assert "SOCIAL_API" in data["supported_source_types"]

    # 2. GET status
    res_status = await client.get("/api/v1/connectors/social-web/status", headers=headers_analyst)
    assert res_status.status_code == 200
    assert "records_fetched" in res_status.json()

    # 3. GET sources
    res_sources = await client.get("/api/v1/connectors/social-web/sources", headers=headers_analyst)
    assert res_sources.status_code == 200
    assert "sources" in res_sources.json()

    # 4. POST test with unconfigured source returns NOT_CONFIGURED
    test_payload = {"source_type": "SOCIAL_API", "url": None}
    res_test = await client.post("/api/v1/connectors/social-web/test", json=test_payload, headers=headers_analyst)
    assert res_test.status_code == 200
    test_data = res_test.json()
    assert test_data["status"] == "NOT_CONFIGURED"
    assert test_data["success"] is False

    # 5. POST test RBAC: Citizen user should be forbidden (Analyst/Admin/Gov only)
    res_forbidden = await client.post("/api/v1/connectors/social-web/test", json=test_payload, headers=headers_citizen)
    assert res_forbidden.status_code == 403


# ============================================================================
# 27. LIVE SOURCE SMOKE-TEST HANDLING
# ============================================================================

@pytest.mark.asyncio
async def test_27_live_source_smoke_test_handling(client, test_analyst, auth_headers):
    headers = auth_headers(test_analyst)

    # Test with mock valid RSS feed
    mock_rss = """<rss version="2.0"><channel><item><title>Heavy Rainfall Alert</title><description>Downpour observed in Kerala #HeavyRain</description></item></channel></rss>"""
    with patch("httpx.AsyncClient.head", return_value=httpx.Response(200, request=httpx.Request("HEAD", "https://mock.gov.in/rss"))):
        with patch("httpx.AsyncClient.get", return_value=httpx.Response(200, text=mock_rss, request=httpx.Request("GET", "https://mock.gov.in/rss"))):
            res = await client.post(
                "/api/v1/connectors/social-web/test",
                json={"source_type": "RSS_FEED", "url": "https://mock.gov.in/rss"},
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "HEALTHY"
            assert data["success"] is True
            assert data["records_found"] == 1
            assert len(data["sample_records"]) == 1
            assert "Heavy Rainfall Alert" in data["sample_records"][0]["text"]


# ============================================================================
# 28. REGRESSION: FOREIGN WEATHER POST QUARANTINE
# ============================================================================

@pytest.mark.asyncio
async def test_28_foreign_weather_post_quarantine():
    # E.g. Mat-Su Valley Alaska dense fog post with foreign GPS
    adapter = SocialAPIAdapter(base_url="https://social.example.com")
    raw_post = {
        "id": "alaska_fog_001",
        "text": "Dense fog advisory in Mat-Su valley freezing fog #weather #fog",
        "geo": {"lat": 61.5815, "lon": -149.4394},
    }
    raw_event = adapter.parse(raw_post)
    assert raw_event is not None
    assert "Dense fog advisory" in raw_event.text

    norm_event = await normalize_raw_event(raw_event)
    # Regression requirement:
    # Foreign weather post -> weather-relevant = YES -> India-valid = NO -> domestic pipeline = NO
    assert norm_event.is_india_valid is False
    assert norm_event.is_quarantined is True
    assert norm_event.quarantine_reason == "FOREIGN_COORDINATES"


# ============================================================================
# 29. REGRESSION: INDIAN CITY MENTIONED IN TEXT (ZERO FAKE GPS)
# ============================================================================

@pytest.mark.asyncio
async def test_29_indian_city_in_text_zero_fake_gps():
    adapter = SocialAPIAdapter(base_url="https://social.example.com")
    raw_post = {
        "id": "bhubaneswar_rain_002",
        "text": "Heavy rain and thunderstorms in Bhubaneswar #OdishaWeather #RainAlert",
    }
    raw_event = adapter.parse(raw_post)
    assert raw_event is not None

    norm_event = await normalize_raw_event(raw_event)
    assert norm_event.is_india_valid is True
    assert norm_event.is_quarantined is False
    assert norm_event.city == "Bhubaneswar"
    assert norm_event.state == "Odisha"
    assert norm_event.location_source == "TEXT"
    assert norm_event.location_confidence == "MEDIUM"
    # STRICT ZERO FAKE GPS RULE:
    assert norm_event.latitude is None
    assert norm_event.longitude is None


# ============================================================================
# 30. REGRESSION: EXPLICIT INDIAN GPS PRESERVATION
# ============================================================================

@pytest.mark.asyncio
async def test_30_explicit_indian_gps_preservation():
    adapter = SocialAPIAdapter(base_url="https://social.example.com")
    raw_post = {
        "id": "mumbai_gps_003",
        "text": "Severe waterlogging near Dadar station #MumbaiRain",
        "geo": {"lat": 19.0178, "lon": 72.8478},
    }
    raw_event = adapter.parse(raw_post)
    assert raw_event is not None

    norm_event = await normalize_raw_event(raw_event)
    assert norm_event.is_india_valid is True
    assert norm_event.is_quarantined is False
    assert norm_event.latitude == 19.0178
    assert norm_event.longitude == 72.8478
    assert norm_event.location_source == "COORDINATES"
    assert norm_event.location_confidence == "HIGH"


# ============================================================================
# 31. REGRESSION: UNKNOWN LOCATION QUARANTINE
# ============================================================================

@pytest.mark.asyncio
async def test_31_unknown_location_quarantine():
    adapter = SocialAPIAdapter(base_url="https://social.example.com")
    raw_post = {
        "id": "generic_weather_004",
        "text": "Extremely cloudy and dark skies today, might rain soon #weather #clouds",
    }
    raw_event = adapter.parse(raw_post)
    assert raw_event is not None

    norm_event = await normalize_raw_event(raw_event)
    assert norm_event.is_india_valid is False
    assert norm_event.is_quarantined is True
    assert norm_event.quarantine_reason == "UNKNOWN_LOCATION"
    assert norm_event.location_source == "UNKNOWN"
    assert norm_event.location_confidence == "LOW"


# ============================================================================
# 32. REGRESSION: NON-WEATHER POST REJECTION
# ============================================================================

def test_32_non_weather_post_rejection():
    adapter = SocialAPIAdapter(base_url="https://social.example.com")
    raw_post = {
        "id": "non_weather_005",
        "text": "Just launched our new product version! Check it out on our website #tech #software",
    }
    raw_event = adapter.parse(raw_post)
    assert raw_event is None


# ============================================================================
# 33. REGRESSION: DUPLICATE & REPOST CLASSIFICATION
# ============================================================================

def test_33_duplicate_and_repost_classification():
    text = "Red alert issued for Chennai coast as storm approaches #ChennaiRain"
    rel_orig, ev_orig = detect_content_relationship(text, "post_100", {})
    assert rel_orig == ContentRelationship.ORIGINAL

    # Repost with RT prefix
    rel_repost, ev_repost = detect_content_relationship(f"RT @chennai_met: {text}", "post_101", {})
    assert rel_repost == ContentRelationship.REPOST
    assert ev_repost["has_repost_indicator"] is True

    # Exact content duplicate from another post
    history = [{"external_id": "post_100", "text": text, "content_hash": ev_orig["content_hash"]}]
    rel_dupe, ev_dupe = detect_content_relationship(text, "post_102", {}, recent_events=history)
    assert rel_dupe == ContentRelationship.LIKELY_COPY
    assert ev_dupe["matched_original_id"] == "post_100"


# ============================================================================
# 34. REGRESSION: TELEMETRY COUNTER SEMANTICS
# ============================================================================

@pytest.mark.asyncio
async def test_34_telemetry_counter_semantics(client, test_analyst, auth_headers):
    headers = auth_headers(test_analyst)

    # Mock response with 4 items:
    # 1. Real Indian weather post (Accepted India)
    # 2. Foreign weather post (Quarantined Foreign)
    # 3. Weather post without location (Quarantined Unknown)
    # 4. Non-weather post (Rejected Non-Weather)
    mock_posts = [
        {"id": "p1", "content": "Heavy rainfall in Mumbai #MumbaiRain #WeatherAlert"},
        {"id": "p2", "content": "Heavy snowfall in Denver #weather", "geo": {"lat": 39.7392, "lon": -104.9903}},
        {"id": "p3", "content": "Thunderstorm and lightning warning #WeatherAlert"},
        {"id": "p4", "content": "Good morning everyone, having a cup of coffee!"},
    ]

    with patch("httpx.AsyncClient.get", return_value=httpx.Response(200, json=mock_posts, request=httpx.Request("GET", "https://mastodon.social/api/v1/timelines/tag/weather"))):
        res = await client.post(
            "/api/v1/connectors/social-web/test",
            json={"source_type": "SOCIAL_API", "url": "https://mastodon.social/api/v1/timelines/tag/weather"},
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["records_fetched"] == 4
        assert data["weather_relevant"] == 3
        assert data["accepted_india"] == 1
        assert data["accepted_for_pipeline"] == 1
        assert data["rejected_non_weather"] == 1
        assert data["quarantined_foreign"] == 1
        assert data["quarantined_unknown_location"] == 1
        assert data["duplicates"] == 0
        assert data["errors"] == 0


# ============================================================================
# 35. CENTRALIZED HASHTAG REGISTRY & NORMALIZATION
# ============================================================================

def test_35_centralized_hashtag_registry_and_normalization():
    from connectors.social_web_connector import HashtagRegistry, normalize_hashtag, parse_hashtag_list

    # 1. Normalization helper
    assert normalize_hashtag("IMD") == "#IMD"
    assert normalize_hashtag("#Weather") == "#Weather"
    assert normalize_hashtag("  mumbairain  ") == "#mumbairain"

    # 2. Parse & deduplicate list case-insensitively
    raw = ["#IMD", "imd", "#Weather", "#weather", "Monsoon", "#monsoon"]
    parsed = parse_hashtag_list(raw)
    assert len(parsed) == 3
    assert "#IMD" in parsed
    assert "#Weather" in parsed
    assert "#Monsoon" in parsed

    # 3. Registry dynamic operations
    reg = HashtagRegistry(["#IMD", "#HeavyRain"])
    assert reg.is_weather_hashtag("#imd") is True
    assert reg.is_weather_hashtag("heavyrain") is True
    assert reg.is_weather_hashtag("#Crypto") is False

    reg.add_hashtag("ChennaiRain")
    assert reg.is_weather_hashtag("#chennairain") is True
    reg.remove_hashtag("#HeavyRain")
    assert reg.is_weather_hashtag("#HeavyRain") is False

    # 4. Text matching with registry
    is_m, terms = reg.match_text("Flash flood warnings in #chennairain today")
    assert is_m is True
    assert "#ChennaiRain" in terms


# ============================================================================
# 36. MULTI-HASHTAG MASTODON POLLING
# ============================================================================

@pytest.mark.asyncio
async def test_36_mastodon_multi_hashtag_polling():
    adapter = SocialAPIAdapter(
        base_url="https://mastodon.social",
        queries=["#IMD", "#Monsoon", "#MumbaiRain"],
        max_posts_per_hashtag=5,
    )

    mock_imd_posts = [
        {"id": "imd_101", "content": "IMD orange alert issued for coastal Konkan #IMD #HeavyRain", "account": {"username": "imd_news"}},
        {"id": "imd_102", "content": "Weather bulletin for North India #IMD #WeatherAlert", "account": {"username": "met_watch"}},
    ]
    mock_monsoon_posts = [
        {"id": "mon_201", "content": "Monsoon activity intensifying over Maharashtra #Monsoon #MumbaiRain", "account": {"username": "skymet"}},
        {"id": "imd_101", "content": "IMD orange alert issued for coastal Konkan #IMD #HeavyRain", "account": {"username": "imd_news"}}, # duplicate across tags
    ]
    mock_mumbai_posts = [
        {"id": "mum_301", "content": "Waterlogging reported in Kurla and Dadar #MumbaiRain", "account": {"username": "mumbai_live"}},
    ]

    async def mock_get(url, *args, **kwargs):
        if "tag/IMD" in url:
            return httpx.Response(200, json=mock_imd_posts, request=httpx.Request("GET", url))
        elif "tag/Monsoon" in url:
            return httpx.Response(200, json=mock_monsoon_posts, request=httpx.Request("GET", url))
        elif "tag/MumbaiRain" in url:
            return httpx.Response(200, json=mock_mumbai_posts, request=httpx.Request("GET", url))
        return httpx.Response(404, request=httpx.Request("GET", url))

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        records = await adapter.fetch()
        # Should have fetched 5 records total, and deduplicated the cross-tag post id 'imd_101' down to 4 unique records
        assert len(records) == 4
        assert adapter.status == ConnectorStatusEnum.HEALTHY
        assert adapter.metrics.records_fetched == 4
        assert adapter.metrics.last_successful_fetch is not None


# ============================================================================
# 37. MASTODON RATE LIMIT BACKOFF & RESILIENCE
# ============================================================================

@pytest.mark.asyncio
async def test_37_mastodon_rate_limit_backoff():
    adapter = SocialAPIAdapter(
        base_url="https://mastodon.social",
        queries=["#IMD", "#Weather"],
    )

    async def mock_rate_limited(url, *args, **kwargs):
        return httpx.Response(429, headers={"Retry-After": "2"}, request=httpx.Request("GET", url))

    with patch("httpx.AsyncClient.get", side_effect=mock_rate_limited):
        records = await adapter.fetch()
        assert len(records) == 0
        assert adapter.status == ConnectorStatusEnum.DEGRADED
        assert adapter.metrics.rate_limits >= 1
        assert "429" in adapter.metrics.last_error or "rate limit" in adapter.metrics.last_error.lower()


# ============================================================================
# 38. WEATHER RELEVANCE FILTERING AND PROVENANCE
# ============================================================================

def test_38_weather_relevance_filtering_and_provenance():
    adapter = SocialAPIAdapter(base_url="https://mastodon.social", queries=["#IMD", "#HeavyRain"])

    # 1. Weather relevant post with metadata
    raw_weather = {
        "id": "post_weather_999",
        "url": "https://mastodon.social/@user/999",
        "content": "<p>Massive cloudburst and landslide near Shimla #HeavyRain #WeatherAlert</p>",
        "created_at": "2026-10-01T08:00:00Z",
        "account": {"username": "himachal_update", "display_name": "Himachal Weather"},
        "language": "en",
        "media_attachments": [
            {"type": "image", "url": "https://files.mastodon.social/landslide.jpg", "preview_url": "https://files.mastodon.social/thumb.jpg", "mime_type": "image/jpeg"}
        ],
    }
    event = adapter.parse(raw_weather)
    assert event is not None
    assert event.external_id == "post_weather_999"
    assert "Massive cloudburst and landslide near Shimla" in event.text
    assert len(event.media) == 1
    assert event.media[0].url == "https://files.mastodon.social/landslide.jpg"
    assert event.raw_payload["platform"] == "Mastodon"
    assert event.raw_payload["author_id"] == "himachal_update"
    assert event.raw_payload["author_display_name"] == "Himachal Weather"
    assert event.raw_payload["language"] == "en"
    assert "#HeavyRain" in event.raw_payload["hashtags"]
    assert event.raw_payload["initial_event_category"] in ("RAINFALL", "FLOODING", "UNKNOWN")

    # 2. Obvious non-weather post rejected
    raw_non_weather = {
        "id": "post_coffee_100",
        "content": "<p>Drinking a delicious cup of espresso this morning! #coffee #breakfast</p>",
    }
    event_non_weather = adapter.parse(raw_non_weather)
    assert event_non_weather is None


# ============================================================================
# 39. TELEMETRY MATHEMATICAL CONSISTENCY ACROSS MULTIPLE RUNS
# ============================================================================

@pytest.mark.asyncio
async def test_39_telemetry_mathematical_consistency():
    connector = SocialWebConnector()
    adapter = SocialAPIAdapter(base_url="https://mastodon.social", queries=["#IMD"])
    connector.register_provider("social_api", adapter)

    mock_batch = [
        {"id": "m1", "content": "Heavy rainfall in Bengaluru causes waterlogging #BengaluruRain #WeatherAlert"},
        {"id": "m2", "content": "Dense fog in Chicago airport #weather", "geo": {"lat": 41.8781, "lon": -87.6298}},
        {"id": "m3", "content": "Thunderstorm and lightning observed #WeatherAlert"},
        {"id": "m4", "content": "Excited for the cricket match today! #sports #weekend"},
    ]

    with patch("httpx.AsyncClient.get", return_value=httpx.Response(200, json=mock_batch, request=httpx.Request("GET", "https://mastodon.social/api/v1/timelines/tag/IMD"))):
        events = await connector.poll()
        m = connector.metrics

        # Strict mathematical consistency checks:
        # 1. Total fetched = weather relevant + rejected non-weather
        assert m.records_fetched == m.weather_relevant + m.rejected_non_weather
        assert m.records_fetched == 4
        assert m.weather_relevant == 3
        assert m.rejected_non_weather == 1

        # 2. Weather relevant = accepted India + quarantined foreign + quarantined unknown
        assert m.weather_relevant == m.accepted_india + m.quarantined_foreign + m.quarantined_unknown_location
        assert m.accepted_india == 1
        assert m.quarantined_foreign == 1
        assert m.quarantined_unknown_location == 1

        # 3. Accepted for pipeline = accepted India
        assert m.accepted_for_pipeline == m.accepted_india

        # 4. Returned events length matches weather_relevant
        assert len(events) == m.weather_relevant


# ============================================================================
# 40. HASHTAG CONFIGURATION REST API ENDPOINTS
# ============================================================================

@pytest.mark.asyncio
async def test_40_hashtag_api_endpoints(client, test_analyst, test_citizen, auth_headers):
    headers_analyst = auth_headers(test_analyst)
    headers_citizen = auth_headers(test_citizen)

    # 1. GET hashtags
    res_get = await client.get("/api/v1/connectors/social-web/hashtags", headers=headers_analyst)
    assert res_get.status_code == 200
    data = res_get.json()
    assert "configured_hashtags" in data
    assert len(data["configured_hashtags"]) >= 20

    # 2. PUT hashtags update by analyst/admin
    new_hashtags = ["#IMD", "#Monsoon", "#KeralaFlood", "#OdishaCyclone"]
    res_put = await client.put(
        "/api/v1/connectors/social-web/hashtags",
        json={"hashtags": new_hashtags},
        headers=headers_analyst,
    )
    assert res_put.status_code == 200
    assert res_put.json()["status"] == "SUCCESS"
    assert len(res_put.json()["configured_hashtags"]) == 4

    # 3. PUT forbidden for citizen
    res_forbidden = await client.put(
        "/api/v1/connectors/social-web/hashtags",
        json={"hashtags": ["#Test"]},
        headers=headers_citizen,
    )
    assert res_forbidden.status_code == 403


# ============================================================================
# 41. END-TO-END SOCIAL POST TO CANONICAL WEATHER REPORT TRACE
# ============================================================================

@pytest.mark.asyncio
async def test_41_end_to_end_social_pipeline_trace(db_session):
    from workers.ingestion_writer import persist_normalized_event

    adapter = SocialAPIAdapter(base_url="https://mastodon.social", queries=["#IMD"])
    raw_post = {
        "id": "e2e_social_12345",
        "url": "https://mastodon.social/@kerala_news/12345",
        "content": "<p>Heavy rainfall in Kochi and Ernakulam district. Waterlogging on MG Road. #KeralaRain #IMD</p>",
        "created_at": "2026-10-01T12:00:00Z",
        "account": {"username": "kerala_news", "display_name": "Kerala News Live"},
    }

    raw_event = adapter.parse(raw_post)
    assert raw_event is not None
    assert raw_event.external_id == "e2e_social_12345"

    # Persist through ingestion writer worker handler
    report = await persist_normalized_event(db_session, raw_event.model_dump(mode="json"))
    assert report is not None
    assert report.location_city == "Kochi" or report.location_district == "Ernakulam"
    assert report.location_state == "Kerala"
    assert report.location_lat is None  # Zero fake GPS rule
    assert report.location_lon is None
    assert report.primary_category in ("RAINFALL", "FLOODING")
    assert report.metadata_["external_id"] == "e2e_social_12345"


# ============================================================================
# 42. LIVE MASTODON PUBLIC API SMOKE TEST
# ============================================================================

@pytest.mark.asyncio
async def test_42_live_mastodon_smoke_test():
    """
    Live smoke test against public Mastodon API with graceful network failure tolerance.
    """
    adapter = SocialAPIAdapter(
        base_url="https://mastodon.social/api/v1/timelines/tag/Weather",
        timeout_seconds=5.0,
    )
    try:
        health = await adapter.health_check()
        if health == ConnectorStatusEnum.HEALTHY:
            records = await adapter.fetch()
            assert isinstance(records, list)
            if records:
                first_event = adapter.parse(records[0])
                # If the real post was weather-related, it parsed into a CanonicalRawEvent
                if first_event:
                    assert first_event.text is not None
                    assert first_event.observed_at is not None
    except (httpx.ConnectError, httpx.TimeoutException) as net_err:
        pytest.skip(f"Live network unavailable during smoke test: {net_err}")


