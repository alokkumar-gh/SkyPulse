"""
SkyPulse Canonical Weather Event Deduplication & Integrity Consolidation
========================================================================
Consolidates existing duplicate WeatherEvents in PostgreSQL:
1. Identifies duplicate event clusters across:
   - Category (same or related hazard category)
   - Spatial proximity (geospatial <= 35km OR administrative match on State + District/City)
   - Temporal proximity (time window <= 36h)
2. Selects the primary canonical event for each cluster (highest evidence_count / GPS accuracy).
3. Re-links all WeatherReport rows and EventEvidence rows to the primary canonical event.
4. Soft-deletes / marks redundant WeatherEvent records.
5. Updates evidence_count, centroid coordinates, and last_updated_at on the primary event.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Set, Any
from sqlalchemy import select, update, func, delete
from geoalchemy2.elements import WKTElement

from app.db.session import AsyncSessionLocal
from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.models.event_evidence import EventEvidence
from app.models.verification import VerificationResult
from ai.deduplicator import haversine_distance_km

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("skypulse.scripts.dedup")


async def run_deduplication():
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(WeatherEvent)
            .where(WeatherEvent.is_deleted == False)
            .order_by(WeatherEvent.first_reported_at.asc())
        )
        all_events = res.scalars().all()
        logger.info("Loaded %d active WeatherEvents for consolidation", len(all_events))

        visited: Set[Any] = set()
        clusters: List[List[WeatherEvent]] = []

        for i, e1 in enumerate(all_events):
            if e1.id in visited:
                continue

            cluster = [e1]
            for j in range(i + 1, len(all_events)):
                e2 = all_events[j]
                if e2.id in visited:
                    continue

                # 1. Category comparison
                cat1 = (e1.category or "UNKNOWN").upper()
                cat2 = (e2.category or "UNKNOWN").upper()

                cat_match = (
                    (cat1 == cat2 and cat1 != "UNKNOWN")
                    or (cat1 in ("RAINFALL", "FLOODING") and cat2 in ("RAINFALL", "FLOODING"))
                    or (cat1 in ("THUNDERSTORM", "STRONG_WINDS") and cat2 in ("THUNDERSTORM", "STRONG_WINDS"))
                    or (cat1 == "UNKNOWN" or cat2 == "UNKNOWN")
                )
                if not cat_match:
                    continue

                # 2. Spatial comparison
                spatial_match = False
                lat1, lon1 = e1.centroid_lat, e1.centroid_lon
                lat2, lon2 = e2.centroid_lat, e2.centroid_lon

                if lat1 is not None and lon1 is not None and lat2 is not None and lon2 is not None:
                    dist = haversine_distance_km(lat1, lon1, lat2, lon2)
                    if dist <= 40.0:
                        spatial_match = True
                else:
                    s1 = (e1.primary_state or "").lower().strip()
                    s2 = (e2.primary_state or "").lower().strip()
                    d1 = (e1.primary_district or e1.primary_city or "").lower().strip().replace("khordha", "khurda").replace("bengaluru", "bangalore")
                    d2 = (e2.primary_district or e2.primary_city or "").lower().strip().replace("khordha", "khurda").replace("bengaluru", "bangalore")

                    if s1 and s2 and (s1 == s2 or s1 in s2 or s2 in s1):
                        if d1 and d2 and (d1 == d2 or d1 in d2 or d2 in d1):
                            spatial_match = True
                        elif not d1 and not d2:
                            spatial_match = True
                        elif (not d1 or not d2) and (cat1 == cat2 or cat1 == "UNKNOWN" or cat2 == "UNKNOWN"):
                            spatial_match = True

                if not spatial_match:
                    continue

                # 3. Temporal comparison
                t1 = e1.first_reported_at or e1.last_updated_at
                t2 = e2.first_reported_at or e2.last_updated_at
                if t1 and t2:
                    diff_hours = abs((t1 - t2).total_seconds()) / 3600.0
                    if diff_hours <= 48.0:
                        cluster.append(e2)
                        visited.add(e2.id)

            if len(cluster) > 1:
                visited.add(e1.id)
                clusters.append(cluster)

        logger.info("Identified %d duplicate clusters covering %d events", len(clusters), sum(len(c) for c in clusters))

        total_merged = 0

        for cluster in clusters:
            # Pick primary event: prefer one with GPS coordinates, highest evidence_count, non-UNKNOWN category
            def sort_key(ev: WeatherEvent):
                has_gps = 1 if (ev.centroid_lat is not None and ev.centroid_lon is not None) else 0
                is_known = 1 if ev.category != "UNKNOWN" else 0
                ev_cnt = ev.evidence_count or 1
                return (has_gps, is_known, ev_cnt)

            cluster.sort(key=sort_key, reverse=True)
            primary = cluster[0]
            redundants = cluster[1:]

            # If primary was UNKNOWN but redundants have a specific category, adopt it
            if primary.category == "UNKNOWN":
                for red in redundants:
                    if red.category != "UNKNOWN":
                        primary.category = red.category
                        break

            # Upgrade coordinates if primary lacked them but a redundant has them
            if (primary.centroid_lat is None or primary.centroid_lon is None):
                for red in redundants:
                    if red.centroid_lat is not None and red.centroid_lon is not None:
                        primary.centroid_lat = red.centroid_lat
                        primary.centroid_lon = red.centroid_lon
                        primary.centroid_point = WKTElement(f"POINT({red.centroid_lon} {red.centroid_lat})", srid=4326)
                        primary.primary_city = primary.primary_city or red.primary_city
                        primary.primary_district = primary.primary_district or red.primary_district
                        primary.primary_state = primary.primary_state or red.primary_state
                        break

            # Merge all evidence and reports from redundants
            redundant_ids = [r.id for r in redundants]

            # 1. Update WeatherReports pointing to redundants
            await db.execute(
                update(WeatherReport)
                .where(WeatherReport.canonical_event_id.in_(redundant_ids))
                .values(canonical_event_id=primary.id)
            )

            # 2. Update or re-assign EventEvidence links
            for red in redundants:
                ev_res = await db.execute(
                    select(EventEvidence).where(EventEvidence.canonical_event_id == red.id)
                )
                evidence_items = ev_res.scalars().all()
                for ev_item in evidence_items:
                    # Check if link already exists for primary
                    dup_check = await db.execute(
                        select(EventEvidence).where(
                            EventEvidence.canonical_event_id == primary.id,
                            EventEvidence.weather_report_id == ev_item.weather_report_id,
                        )
                    )
                    if dup_check.scalar_one_or_none():
                        await db.delete(ev_item)
                    else:
                        ev_item.canonical_event_id = primary.id

                # Soft delete redundant event
                red.is_deleted = True
                red.is_active = False
                total_merged += 1

            # Recount total evidence for primary
            cnt_res = await db.execute(
                select(func.count(EventEvidence.id)).where(EventEvidence.canonical_event_id == primary.id)
            )
            total_ev_count = cnt_res.scalar() or 1
            primary.evidence_count = total_ev_count
            primary.last_updated_at = datetime.now(timezone.utc)

        await db.commit()
        logger.info("Successfully merged %d redundant duplicate events into primary canonical events!", total_merged)

        # Final audit
        final_res = await db.execute(select(WeatherEvent).where(WeatherEvent.is_deleted == False, WeatherEvent.is_active == True))
        active_remaining = final_res.scalars().all()
        plottable = [e for e in active_remaining if e.centroid_lat is not None and e.centroid_lon is not None]
        regional = [e for e in active_remaining if e.centroid_lat is None or e.centroid_lon is None]

        logger.info("Final State: %d active canonical events (%d plottable with GPS, %d regional/no-GPS)",
                    len(active_remaining), len(plottable), len(regional))


if __name__ == "__main__":
    asyncio.run(run_deduplication())
