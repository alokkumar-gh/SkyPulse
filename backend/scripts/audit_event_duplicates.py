import asyncio
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from app.db.session import async_session_factory
from app.models.weather_event import WeatherEvent
from app.models.weather_report import WeatherReport
from app.models.event_evidence import EventEvidence

async def main():
    async with async_session_factory() as db:
        stmt = select(WeatherEvent).where(WeatherEvent.is_active == True)
        events = (await db.execute(stmt)).scalars().all()
        
        print(f"Total active events in DB: {len(events)}")
        
        groups = defaultdict(list)
        for ev in events:
            key = (
                (ev.category or "").upper(),
                (ev.primary_state or "").upper(),
                (ev.primary_district or "").upper(),
                (ev.primary_city or "").upper()
            )
            groups[key].append(ev)
            
        dup_count = 0
        for k, ev_list in groups.items():
            if len(ev_list) > 1:
                dup_count += len(ev_list) - 1
                print(f"\nGroup {k} has {len(ev_list)} events:")
                for e in ev_list:
                    print(f"  - ID: {e.id}, Created: {e.created_at}, Evidence Count: {e.evidence_count}, Centroid: ({e.centroid_lat}, {e.centroid_lon})")

        print(f"\nTotal duplicate canonical event instances: {dup_count}")

if __name__ == "__main__":
    asyncio.run(main())
