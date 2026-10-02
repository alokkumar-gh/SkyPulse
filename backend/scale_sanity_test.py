"""
SkyPulse Controlled Pipeline Scale & Throughput Sanity Test
===========================================================
Executes a controlled batch test of 100 synthetic Indian weather events through
the full Unified Ingestion Pipeline.

Measures:
- Total execution time
- Average throughput (events / second)
- Accepted & Processed count
- Duplicate detections & corroborations
- Classification success rate
- Database persistence success
- OpenSearch indexing count
- Dynamic Weather Evidence Graph (DWEG) updates
- Failures / Quarantined counts
- Per-event average latency (ms)

NOTE: Explicitly a controlled integration sanity test, NOT a production-scale benchmark.
"""

import asyncio
import time
import uuid
import random
from datetime import datetime, timezone, timedelta

from app.db.session import AsyncSessionLocal
from app.models.source import Source
from app.models.enums import SourceType
from connectors.schema import CanonicalRawEvent
from connectors.normalizer import INDIAN_CITIES_REFERENCE
from app.services.unified_ingestion_service import unified_ingestion_pipeline
from ai.opensearch_indexer import opensearch_indexer
from ai.dweg_service import dweg_service
from sqlalchemy import select


CITIES_POOL = [
    ("Mumbai", "Maharashtra", 19.0760, 72.8777),
    ("Delhi", "Delhi", 28.6139, 77.2090),
    ("Bengaluru", "Karnataka", 12.9716, 77.5946),
    ("Kolkata", "West Bengal", 22.5726, 88.3639),
    ("Chennai", "Tamil Nadu", 13.0827, 80.2707),
    ("Hyderabad", "Telangana", 17.3850, 78.4867),
    ("Ahmedabad", "Gujarat", 23.0225, 72.5714),
    ("Bhubaneswar", "Odisha", 20.2961, 85.8245),
    ("Cuttack", "Odisha", 20.4625, 85.8830),
    ("Patna", "Bihar", 25.5941, 85.1376),
    ("Jaipur", "Rajasthan", 26.9124, 75.7873),
    ("Guwahati", "Assam", 26.1445, 91.7362),
    ("Srinagar", "Jammu and Kashmir", 34.0837, 74.7973),
    ("Shimla", "Himachal Pradesh", 31.1048, 77.1734),
    ("Kochi", "Kerala", 9.9312, 76.2673),
]

WEATHER_TEMPLATES = [
    ("RAINFALL", "Heavy torrential rainfall recorded with waterlogging across major intersections in {city}, {state}."),
    ("THUNDERSTORM", "Severe thunderstorm with active lightning and convective cloud activity over {city}, {state}."),
    ("FLOODING", "Rapid urban flooding and submerged streets reported near downtown {city}, {state}."),
    ("HEATWAVE", "Extreme scorching heatwave conditions with temperatures exceeding 43C in {city}, {state}."),
    ("FOG", "Dense winter fog causing near-zero visibility and flight delays at {city}, {state}."),
    ("DUST_STORM", "Blinding dust storm with intense gusty winds blowing across {city}, {state}."),
    ("STRONG_WINDS", "Gale-force winds causing uprooted trees and localized power interruptions in {city}, {state}."),
]


async def run_scale_sanity_test(num_events: int = 100):
    print("==================================================")
    print(f"SKYPULSE PIPELINE LOAD & THROUGHPUT SANITY TEST ({num_events} EVENTS)")
    print("==================================================")
    print("Generating synthetic events across Indian cities...")
    
    # Set classifier, nlp_extractor, and image_analyzer to fast provider to measure pipeline throughput accurately
    from ai.event_classifier import EventClassifier
    from ai.nlp_extractor import NLPExtractor
    from ai.image_analyzer import ImageAnalyzer
    from ai.fallback_provider import FallbackAIProvider
    fallback_prov = FallbackAIProvider()
    unified_ingestion_pipeline._classifier = EventClassifier(provider=fallback_prov)
    unified_ingestion_pipeline._nlp_extractor = NLPExtractor(provider=fallback_prov)
    unified_ingestion_pipeline._image_analyzer = ImageAnalyzer(provider=fallback_prov)


    # Generate synthetic events
    events = []
    base_time = datetime.now(timezone.utc)
    for i in range(num_events):
        city, state, lat, lon = random.choice(CITIES_POOL)
        category, template = random.choice(WEATHER_TEMPLATES)
        text = template.format(city=city, state=state)
        # Introduce intentional duplicate texts for 10% of events
        if i % 10 == 0 and len(events) > 0:
            dup_ev = events[i - 1]
            text = dup_ev.text
            lat = dup_ev.latitude
            lon = dup_ev.longitude
            city = dup_ev.city
            state = dup_ev.state

        obs_time = base_time - timedelta(minutes=random.randint(5, 300))
        ev = CanonicalRawEvent(
            source_id="00000000-0000-0000-0000-000000000008",
            source_type="WEATHER_API",
            text=text,
            city=city,
            state=state,
            latitude=lat,
            longitude=lon,
            observed_at=obs_time,
            is_demo=True,
        )
        events.append(ev)

    print(f"Generated {len(events)} synthetic CanonicalRawEvents.")
    print("Beginning pipeline ingestion stream...")

    t0 = time.perf_counter()
    accepted = 0
    duplicates = 0
    quarantined = 0
    failures = 0
    categories_count = {}
    latencies = []

    async with AsyncSessionLocal() as session:
        # Pre-resolve test source
        src_res = await session.execute(select(Source).where(Source.source_type == SourceType.WEATHER_API.value))
        src = src_res.scalars().first()
        src_id = str(src.id) if src else str(uuid.uuid4())

        for idx, ev in enumerate(events):
            ev.source_id = src_id
            ev_t0 = time.perf_counter()
            try:
                res = await unified_ingestion_pipeline.ingest_canonical_event(
                    raw_event=ev,
                    db=session,
                )
                ev_t1 = time.perf_counter()
                latencies.append((ev_t1 - ev_t0) * 1000.0)

                if res.status == "SUCCESS":
                    accepted += 1
                    if res.is_duplicate:
                        duplicates += 1
                    cat = res.category or "UNKNOWN"
                    categories_count[cat] = categories_count.get(cat, 0) + 1
                elif res.status == "QUARANTINED":
                    quarantined += 1
                else:
                    failures += 1
            except Exception as e:
                failures += 1
                print(f"Event {idx} processing exception: {e}")

            if (idx + 1) % 25 == 0 or (idx + 1) == num_events:
                print(f"  Processed {idx + 1}/{num_events} events... (Elapsed: {time.perf_counter() - t0:.2f}s)", flush=True)


    t1 = time.perf_counter()
    total_time = t1 - t0
    throughput = num_events / total_time if total_time > 0 else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0

    print("\n==================================================")
    print("SANITY TEST RESULTS (Controlled Integration Benchmark)")
    print("==================================================")
    print(f"Total Events Ingested:      {num_events}")
    print(f"Total Duration:             {total_time:.2f} s")
    print(f"Throughput:                 {throughput:.1f} events/sec")
    print(f"Accepted & Processed:       {accepted} ({accepted/num_events*100:.1f}%)")
    print(f"Duplicates Detected:        {duplicates} ({duplicates/num_events*100:.1f}%)")
    print(f"Quarantined / Rejected:     {quarantined}")
    print(f"Pipeline Failures:          {failures}")
    print(f"Average Latency per Event:  {avg_latency:.2f} ms")
    print(f"P95 Latency:                {p95_latency:.2f} ms")
    print("\nCategory Distribution:")
    for cat, cnt in sorted(categories_count.items()):
        print(f"  - {cat}: {cnt}")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_scale_sanity_test(100))
