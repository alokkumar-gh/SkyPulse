import asyncio
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update, delete
from app.db.session import async_session_factory
from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.models.event_evidence import EventEvidence

async def consolidate_duplicates():
    async with async_session_factory() as db:
        stmt = select(WeatherEvent).where(WeatherEvent.is_active == True).order_by(WeatherEvent.created_at.asc())
        events = (await db.execute(stmt)).scalars().all()
        
        print(f"Total active events before consolidation: {len(events)}")
        
        # Group by (category, state, district, city)
        groups = defaultdict(list)
        for ev in events:
            key = (
                (ev.category or "UNKNOWN").upper().strip(),
                (ev.primary_state or "").upper().strip(),
                (ev.primary_district or "").upper().strip(),
                (ev.primary_city or "").upper().strip()
            )
            groups[key].append(ev)
            
        merged_count = 0
        deleted_count = 0
        
        for key, ev_list in groups.items():
            if len(ev_list) <= 1:
                continue
                
            # Keep the primary event (first created or the one with point coordinates)
            primary_ev = None
            for e in ev_list:
                if e.centroid_lat is not None and e.centroid_lon is not None:
                    primary_ev = e
                    break
            if not primary_ev:
                primary_ev = ev_list[0]
                
            duplicate_events = [e for e in ev_list if e.id != primary_ev.id]
            
            total_evidence_added = 0
            for dup in duplicate_events:
                # Re-link all EventEvidence from duplicate event to primary event
                await db.execute(
                    update(EventEvidence)
                    .where(EventEvidence.canonical_event_id == dup.id)
                    .values(canonical_event_id=primary_ev.id)
                )
                
                # Re-link WeatherReport rows
                await db.execute(
                    update(WeatherReport)
                    .where(WeatherReport.canonical_event_id == dup.id)
                    .values(canonical_event_id=primary_ev.id)
                )
                
                total_evidence_added += dup.evidence_count
                
                # Delete duplicate canonical event
                await db.delete(dup)
                deleted_count += 1
                
            primary_ev.evidence_count += total_evidence_added
            primary_ev.last_updated_at = datetime.now(timezone.utc)
            merged_count += 1
            print(f"Merged {len(duplicate_events)} duplicate(s) into primary event {primary_ev.id} ({key}) -> new evidence count: {primary_ev.evidence_count}")
            
        await db.commit()
        
        stmt_after = select(WeatherEvent).where(WeatherEvent.is_active == True)
        events_after = (await db.execute(stmt_after)).scalars().all()
        print(f"\nConsolidation complete:")
        print(f"- Total active events after consolidation: {len(events_after)}")
        print(f"- Consolidated groups: {merged_count}")
        print(f"- Duplicate events removed: {deleted_count}")

if __name__ == "__main__":
    asyncio.run(consolidate_duplicates())
