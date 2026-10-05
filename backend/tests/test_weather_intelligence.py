"""
Unit and Integration Tests for SkyPulse Recent Weather Intelligence Aggregation & Auto-Fetch
"""

import pytest
from datetime import datetime, timedelta, timezone
from app.services.weather_intelligence_service import (
    compute_freshness_bucket,
    generate_event_fingerprint,
    parse_time_range_to_delta,
)
from connectors.weather_discovery.base_alert_connector import GenericCAPAlertConnector
from app.services.auto_fetch_manager import auto_fetch_manager


def test_freshness_bucketing():
    now = datetime.now(timezone.utc)

    # 1 hour ago -> LIVE (0-6h)
    t_breaking = now - timedelta(hours=2)
    assert compute_freshness_bucket(t_breaking) in ("LIVE", "BREAKING")

    # 10 hours ago -> RECENT (6-24h)
    t_recent = now - timedelta(hours=10)
    assert compute_freshness_bucket(t_recent) == "RECENT"

    # 30 hours ago -> STALE / TODAY (24-48h)
    t_today = now - timedelta(hours=30)
    assert compute_freshness_bucket(t_today) in ("STALE", "TODAY")

    # 72 hours ago -> ARCHIVED / HISTORICAL (>48h)
    t_hist = now - timedelta(hours=72)
    assert compute_freshness_bucket(t_hist) in ("ARCHIVED", "HISTORICAL")


def test_event_fingerprint_generation():
    # Fix timestamp safely within a 6h epoch slot (14:00 UTC) to prevent boundary flakes
    ref_time = datetime(2026, 10, 4, 14, 0, 0, tzinfo=timezone.utc)
    fp1 = generate_event_fingerprint("RAINFALL", "Odisha", "Khordha", "Bhubaneswar", ref_time)
    fp2 = generate_event_fingerprint("RAINFALL", "Odisha", "Khordha", "Bhubaneswar", ref_time + timedelta(minutes=10))
    # Within same 6h slot, identical parameters produce exact match
    assert fp1 == fp2

    # Different category or location produces different fingerprint
    fp_flood = generate_event_fingerprint("FLOODING", "Odisha", "Khordha", "Bhubaneswar", ref_time)
    fp_mumbai = generate_event_fingerprint("RAINFALL", "Maharashtra", "Mumbai City", "Mumbai", ref_time)
    assert fp1 != fp_flood
    assert fp1 != fp_mumbai


def test_time_range_parser():
    assert parse_time_range_to_delta("1h") == timedelta(hours=1)
    assert parse_time_range_to_delta("6h") == timedelta(hours=6)
    assert parse_time_range_to_delta("24h") == timedelta(hours=24)
    assert parse_time_range_to_delta("48h") == timedelta(hours=48)
    assert parse_time_range_to_delta("7d") == timedelta(days=7)
    assert parse_time_range_to_delta("all") is None


def test_cap_alert_adapter_parsing_and_normalization():
    sample_cap_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>NDMA-SACHET-2026-0042</identifier>
      <sender>sachet@ndma.gov.in</sender>
      <sent>2026-10-03T10:00:00+05:30</sent>
      <status>Actual</status>
      <msgType>Alert</msgType>
      <scope>Public</scope>
      <info>
        <category>Met</category>
        <event>Cyclone Warning</event>
        <urgency>Immediate</urgency>
        <severity>Severe</severity>
        <certainty>Observed</certainty>
        <headline>Severe Cyclone Warning for Coastal Odisha and Puri</headline>
        <description>Extremely heavy rainfall and cyclonic storm expected along Puri and Khordha coast.</description>
        <area>
          <areaDesc>Puri, Odisha</areaDesc>
        </area>
      </info>
    </alert>"""

    connector = GenericCAPAlertConnector(
        source_id="test-cap-source",
        name="NDMA SACHET Test CAP",
        feed_url="https://sachet.ndma.gov.in/test_cap.xml",
    )

    parsed = connector.parse(sample_cap_xml, content_type="xml")
    assert len(parsed) == 1
    assert parsed[0]["identifier"] == "NDMA-SACHET-2026-0042"
    assert "Cyclone" in parsed[0]["title"]

    events = connector.normalize(parsed)
    assert len(events) == 1
    ev = events[0]
    assert ev.is_india_valid is True
    assert ev.district == "Puri" or ev.state == "Odisha"
    assert ev.source_type == "OFFICIAL"


def test_auto_fetch_status_format():
    status = auto_fetch_manager.get_status()
    assert "status" in status
    assert "events_last_24h" in status
    assert "sources_total" in status
    assert "sources_healthy" in status
    assert "articles_fetched" in status
    assert "events_created" in status
