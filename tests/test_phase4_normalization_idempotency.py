import pytest
from datetime import datetime, timezone

from connectors.normalizer import (
    normalize_category,
    enrich_location,
    sanitize_text,
    normalize_raw_event,
)
from connectors.schema import CanonicalRawEvent
from connectors.idempotency import IdempotencyService


def test_normalize_category():
    assert normalize_category("RAINFALL") == "RAINFALL"
    assert normalize_category("unknown_code", "Flash flood in riverbed") == "FLOODING"
    assert normalize_category("advisory", "High speed dust storm and andhi") == "DUST_STORM"
    assert normalize_category("alert", "Loo winds and heat wave warning") == "HEATWAVE"
    assert normalize_category("custom_tag", "Mild cloudy skies with birds") == "UNKNOWN"


def test_enrich_location_known_city():
    # Mumbai coordinates
    lat, lon, city, dist, state, loc_src, conf, is_valid, is_quarantined, q_reason = enrich_location(19.0760, 72.8777)
    assert conf == "HIGH"
    assert city == "Mumbai"
    assert state == "Maharashtra"
    assert is_valid is True

    # Geocoding via city text mention
    lat2, lon2, city2, dist2, state2, loc_src2, conf2, is_valid2, is_quarantined2, q_reason2 = enrich_location(None, None, text="Heavy shower over Bengaluru")
    assert conf2 == "MEDIUM"
    assert city2 == "Bengaluru"
    assert state2 == "Karnataka"
    assert is_valid2 is True


def test_sanitize_text():
    raw = "Alert\x00\x08! High   winds  \n\n  observed.   "
    clean = sanitize_text(raw)
    assert "\x00" not in clean
    assert clean == "Alert! High winds observed."


@pytest.mark.asyncio
async def test_idempotency_service_duplicate_detection():
    idemp = IdempotencyService(in_memory_max_size=100)

    key1 = idemp.compute_key(source_id="src-1", external_id="ext-999")
    key2 = idemp.compute_key(source_id="src-1", external_id="ext-999")
    key3 = idemp.compute_key(source_id="src-1", external_id="ext-1000")

    assert key1 == key2
    assert key1 != key3

    # First check: new -> not duplicate
    is_dup1 = await idemp.is_duplicate(key1, ttl_seconds=60)
    assert is_dup1 is False

    # Second check within TTL: duplicate
    is_dup2 = await idemp.is_duplicate(key1, ttl_seconds=60)
    assert is_dup2 is True

    # Different key: not duplicate
    is_dup3 = await idemp.is_duplicate(key3, ttl_seconds=60)
    assert is_dup3 is False


@pytest.mark.asyncio
async def test_normalize_raw_event_end_to_end():
    raw_event = CanonicalRawEvent(
        source_id="src-test",
        source_type="CITIZEN",
        external_id="ext-42",
        text="Continuous thunder and rain reported in Dadar, Mumbai",
        suggested_category="THUNDERSTORM",
        severity=3,
    )
    norm = await normalize_raw_event(raw_event)
    assert norm.primary_category == "THUNDERSTORM"
    assert norm.city == "Mumbai"
    assert norm.state == "Maharashtra"
    assert norm.tracking_id.startswith("SP-")
    assert norm.is_duplicate is False
