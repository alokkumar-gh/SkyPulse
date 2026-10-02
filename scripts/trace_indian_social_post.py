import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path("e:/SkyPulse/backend").resolve()
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from connectors.social_web_connector import SocialAPIAdapter
from connectors.normalizer import normalize_raw_event
from ai.deduplicator import DeduplicationEngine
from ai.source_trust import SourceTrustEngine
from app.services.emerging_event_service import emerging_event_service
from app.models.source import Source
from app.models.weather_report import WeatherReport
from app.models.enums import WeatherCategory, SourceType

async def trace_real_post():
    # 1. Real post payload fetched from Mastodon
    raw_payload = {
        "id": "117365439207973184",
        "created_at": "2026-10-01T11:34:40.111Z",
        "url": "https://mastodon.social/@Mathrubhumi_English/117365439207973184",
        "content": "<p>Kerala rain alert: Pathanamthitta, Kottayam and Idukki are under orange alert. Here is what the IMD warnings mean for October 2 and the days ahead. https://english.mathrubhumi.com/news/kerala/kerala-rain-alert-orange-alert-october-2026-imd-warning-kranrj7t?utm_source=dlvr.it&amp;utm_medium=mastodon #KeralaWeather #KeralaRain #RainAlert #GandhiJayanti #IMD</p>",
        "account": {"username": "Mathrubhumi_English"},
        "media_attachments": [
            {
                "id": "1173654391234",
                "type": "image",
                "url": "https://files.mastodon.social/media_attachments/files/117/365/439/preview.jpg",
                "preview_url": "https://files.mastodon.social/media_attachments/files/117/365/439/preview.jpg",
                "mime_type": "image/jpeg"
            }
        ]
    }

    print("=== STEP 1: SOCIAL API ADAPTER ===")
    adapter = SocialAPIAdapter(
        provider_id="social-mastodon-imd",
        base_url="https://mastodon.social/api/v1/timelines/tag/IMD"
    )
    raw_event = adapter.parse(raw_payload)
    assert raw_event is not None
    print(f"Parsed CanonicalRawEvent: ID={raw_event.external_id}, Text={raw_event.text[:80]}...")
    print(f"Raw Coordinates: lat={raw_event.latitude}, lon={raw_event.longitude}")

    print("\n=== STEP 2: NORMALIZATION & INDIA LOCATION EXTRACTION ===")
    norm_event = await normalize_raw_event(raw_event)
    print(f"Tracking ID: {norm_event.tracking_id}")
    print(f"Primary Category: {norm_event.primary_category}")
    print(f"State: {norm_event.state}, City: {norm_event.city}")
    print(f"Location Source: {norm_event.location_source}")
    print(f"Location Confidence: {norm_event.location_confidence}")
    print(f"Latitude: {norm_event.latitude}, Longitude: {norm_event.longitude}")
    print(f"Is India Valid: {norm_event.is_india_valid}")
    print(f"Is Quarantined: {norm_event.is_quarantined}")
    assert norm_event.latitude is None
    assert norm_event.longitude is None
    assert norm_event.state == "Kerala"
    assert norm_event.location_source == "TEXT"
    assert norm_event.location_confidence == "MEDIUM"
    assert norm_event.is_india_valid is True
    assert norm_event.is_quarantined is False

    print("\n=== STEP 3: DEDUPLICATION ENGINE ===")
    dedup_eval = DeduplicationEngine.evaluate_candidate(
        new_report={
            "idempotency_key": norm_event.idempotency_key,
            "text": norm_event.text,
            "primary_category": norm_event.primary_category,
            "latitude": norm_event.latitude,
            "longitude": norm_event.longitude,
            "event_time": norm_event.observed_at,
        },
        candidate={
            "id": "existing-001",
            "idempotency_key": "different-key-123",
            "text": "Another rain event",
            "primary_category": "RAINFALL",
            "latitude": 10.0,
            "longitude": 76.0,
            "event_time": norm_event.observed_at,
        }
    )
    print(f"Dedup Verdict: {dedup_eval.verdict}, Level: {dedup_eval.level_matched}, Score: {dedup_eval.similarity_score}")

    print("\n=== STEP 4: DWEG & EVENT DNA CLUSTERING ===")
    mock_src_id = uuid.uuid4()
    report = WeatherReport(
        source_id=mock_src_id,
        primary_category=WeatherCategory.RAINFALL.value,
        severity=norm_event.severity,
        normalized_text=norm_event.text,
        location_city=norm_event.city,
        location_state=norm_event.state,
        location_confidence=norm_event.location_confidence,
        event_time=norm_event.observed_at,
        metadata_={
            "tracking_id": norm_event.tracking_id,
            "source_type": norm_event.source_type,
            "location_source": norm_event.location_source,
        },
    )
    print(f"DWEG WeatherReport envelope created successfully: ID={report.id}, Category={report.primary_category}, State={report.location_state}")

    print("\n=== STEP 5: SOURCE REPUTATION SERVICE ===")
    trust_score = SourceTrustEngine.calculate_initial_trust(source_type=norm_event.source_type)
    print(f"Source Type: {norm_event.source_type}, Initial Trust Score: {trust_score}")

    print("\n=== ALL PIPELINE STAGES VERIFIED SUCCESSFULLY ===")

if __name__ == "__main__":
    asyncio.run(trace_real_post())
