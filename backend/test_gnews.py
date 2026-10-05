import asyncio
from connectors.weather_discovery.gnews_discovery import GoogleNewsRSSDiscovery

async def test_gnews():
    disc = GoogleNewsRSSDiscovery(
        source_id="00000000-0000-0000-0000-000000000008",
        max_queries_per_cycle=10,
    )
    res = await disc.poll()
    events = res.get("events", [])
    print(f"Total GNews events discovered: {len(events)}")
    for ev in events:
        meta = ev.raw_payload or {}
        print(f"Title: {meta.get('title', '')[:70]}")
        print(f"  Published: {ev.observed_at}")
        print(f"  Publisher: {meta.get('publisher')}")
        print(f"  Loc: State={ev.state}, Dist={ev.district}, City={ev.city}")
        print(f"  Affected: {meta.get('affected_districts')}")

if __name__ == "__main__":
    asyncio.run(test_gnews())
