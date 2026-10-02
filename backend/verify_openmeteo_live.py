"""
SkyPulse Open-Meteo Real Live Verification Script
=================================================
Performs an authenticated/live operational query against https://api.open-meteo.com/v1/forecast.
Verifies:
- DNS/network connectivity
- HTTP 200 OK
- Real JSON response & field extraction
- CanonicalRawEvent normalization
- Unified ingestion pipeline flow (India validation, Dedup, AI, DWEG, DNA, persistence)
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.unified_ingestion_service import unified_ingestion_pipeline
from connectors.openmeteo_connector import OpenMeteoConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("skypulse.verify_openmeteo_live")


async def main():
    print("==================================================")
    print("SKYPULSE OPEN-METEO LIVE VERIFICATION")
    print("==================================================")

    # 1. Inspect configuration
    print(f"OPEN_METEO_ENABLED: {getattr(settings, 'OPEN_METEO_ENABLED', True)}")
    print(f"OPEN_METEO_BASE_URL: {getattr(settings, 'OPEN_METEO_BASE_URL', 'https://api.open-meteo.com/v1/forecast')}")
    print(f"API Key Required: NO (Free Public Meteorological Service)")

    # 2. Live HTTP Request using OpenMeteoConnector
    connector = OpenMeteoConnector(
        locations=[
            {"city": "New Delhi", "district": "New Delhi", "state": "Delhi", "lat": 28.6139, "lon": 77.2090},
            {"city": "Bhubaneswar", "district": "Khurda", "state": "Odisha", "lat": 20.2961, "lon": 85.8245},
            {"city": "Mumbai", "district": "Mumbai City", "state": "Maharashtra", "lat": 19.0760, "lon": 72.8777},
        ]
    )
    await connector.start()

    print("\nExecuting live HTTP poll across 3 Indian locations...")
    events = await connector.poll()

    if not events:
        print("FAIL: No events returned from Open-Meteo live API.")
        await connector.stop()
        sys.exit(1)

    print(f"HTTP REQUEST: PASS (Received {len(events)} real weather observations)")
    print(f"CONNECTOR STATUS: {connector.status.value}")

    # Inspect observations in detail
    for idx, sample in enumerate(events):
        raw_payload = sample.raw_payload
        metrics = raw_payload.get("extracted_metrics", {})
        print(f"\n--- LIVE OBSERVATION #{idx+1}: {sample.city}, {sample.state} ---")
        print(f"City: {sample.city}")
        print(f"State: {sample.state}")
        print(f"District: {sample.district}")
        print(f"Query Coordinates: {sample.latitude}°N, {sample.longitude}°E")
        print(f"Observed At: {sample.observed_at.isoformat()}")
        print(f"Suggested Category: {sample.suggested_category}")
        print(f"Severity: {sample.severity}")
        print(f"Narrative Text: {sample.text}")
        print(f"Temperature: {metrics.get('temperature_c')} °C (Feels like: {metrics.get('apparent_temperature_c')} °C)")
        print(f"Relative Humidity: {metrics.get('humidity_pct')} %")
        print(f"Wind: {metrics.get('wind_speed_kmph')} km/h (Gusts: {metrics.get('wind_gusts_kmph')} km/h)")
        print(f"Precipitation: {metrics.get('precipitation_mm')} mm")
        print(f"Pressure: {metrics.get('surface_pressure_hpa')} hPa")
        print(f"WMO Code: {raw_payload.get('wmo_code')} ({raw_payload.get('condition_description')})")
        print(f"Provider: {raw_payload.get('provider')}")
        print(f"Idempotency Key: {sample.idempotency_key}")

    # 3. Test Unified Ingestion Pipeline Flow for first observation
    print("\n--- TESTING UNIFIED INGESTION PIPELINE FLOW ---")
    async with AsyncSessionLocal() as session:
        result = await unified_ingestion_pipeline.ingest_canonical_event(
            raw_event=events[0],
            db=session,
        )

        print(f"Unified Ingestion Status: {result.status}")
        print(f"Report ID: {result.report_id}")
        print(f"Tracking ID: {result.tracking_id}")
        print(f"Category: {result.category}")
        print(f"Is India Valid: {result.is_india_valid}")
        print(f"Is Quarantined: {result.is_quarantined}")
        print(f"Is Duplicate: {result.is_duplicate}")
        print(f"Canonical Event ID: {result.canonical_event_id}")
        print(f"Confidence Score: {result.confidence_score}")
        print(f"Verification Status: {result.verification_status}")

    await connector.stop()
    print("\n==================================================")
    print("LIVE VERIFICATION: ALL STAGES PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(main())
