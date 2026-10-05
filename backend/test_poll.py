import asyncio
import httpx
from connectors.weather_discovery.regional_rss import poll_rss_feed, RSS_FEEDS, DEFAULT_USER_AGENT

async def test_odisha_feeds():
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    async with httpx.AsyncClient(headers=headers) as client:
        for f in RSS_FEEDS:
            if "Odisha" in str(f.state_coverage):
                print(f"\n--- Polling {f.name} ({f.url}) ---")
                try:
                    events, status = await poll_rss_feed(f, source_id="00000000-0000-0000-0000-000000000008", client=client, max_items=15)
                    print(f"Status: {status} | Collected: {len(events)} weather events")
                    for ev in events[:5]:
                        meta = ev.raw_payload or {}
                        title = meta.get("title", "")
                        print(f"  Title: {title[:75]}")
                        print(f"  Published: {ev.observed_at}")
                        print(f"  Loc: State={ev.state}, Dist={ev.district}, City={ev.city}")
                        print(f"  Coords: ({ev.latitude}, {ev.longitude})")
                        print(f"  Affected: count={meta.get('affected_district_count')}, dists={meta.get('affected_districts')}")
                        print(f"  Category: {ev.suggested_category}")
                except Exception as e:
                    print(f"Error polling {f.name}: {e}")

if __name__ == "__main__":
    asyncio.run(test_odisha_feeds())
