import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path("e:/SkyPulse/backend").resolve()
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import httpx
from connectors.normalizer import enrich_location, sanitize_text
from connectors.social_web_connector import matches_weather_filter

HASHTAGS_TO_TEST = [
    "IMD",
    "IndiaWeather",
    "IndianWeather",
    "Monsoon",
    "Monsoon2026",
    "MumbaiRain",
    "DelhiWeather",
    "OdishaWeather",
    "BengaluruRain",
    "HyderabadRain",
    "KolkataRain",
    "ChennaiRain",
    "FloodIndia",
    "HeatwaveIndia",
]

async def query_tag(client, tag):
    url = f"https://mastodon.social/api/v1/timelines/tag/{tag}?limit=20"
    try:
        resp = await client.get(url)
        status_code = resp.status_code
        if status_code == 200:
            posts = resp.json()
            fetched = len(posts)
            weather_rel = 0
            has_india_evidence = 0
            has_coords = 0
            has_city_state = 0
            foreign = 0
            unknown = 0
            valid_posts = []

            for p in posts:
                raw_text = p.get("content", "") or p.get("text", "")
                clean_text = sanitize_text(re.sub(r"<[^>]+>", " ", raw_text))

                is_weather, matched = matches_weather_filter(clean_text, None, None)
                tag_is_weather = tag.lower() in ("monsoon", "monsoon2026", "mumbairain", "delhiweather", "odishaweather", "bengalururain", "hyderabadrain", "kolkatarain", "chennairain", "floodindia", "heatwaveindia", "indiaweather", "indianweather")

                if is_weather or tag_is_weather:
                    weather_rel += 1

                    lat, lon = None, None
                    geo = p.get("geo") or p.get("coordinates")
                    if isinstance(geo, dict):
                        lat = geo.get("lat") or geo.get("latitude")
                        lon = geo.get("lon") or geo.get("longitude")

                    lat_e, lon_e, city_e, dist_e, state_e, src, conf, is_in, is_quar, quar_r = enrich_location(
                        lat=lat, lon=lon, text=clean_text
                    )

                    if lat is not None and lon is not None:
                        has_coords += 1
                    if city_e or state_e:
                        has_city_state += 1

                    if is_in and not is_quar:
                        has_india_evidence += 1
                        valid_posts.append({
                            "id": p.get("id"),
                            "url": p.get("url"),
                            "created_at": p.get("created_at"),
                            "text": clean_text,
                            "tag": tag,
                            "city": city_e,
                            "district": dist_e,
                            "state": state_e,
                            "source": src,
                            "confidence": conf,
                            "media": len(p.get("media_attachments", []))
                        })
                    elif is_quar:
                        if quar_r == "FOREIGN_COORDINATES":
                            foreign += 1
                        else:
                            unknown += 1

            return {
                "query": f"#{tag}",
                "status": status_code,
                "fetched": fetched,
                "weather_rel": weather_rel,
                "india_evidence": has_india_evidence,
                "with_coords": has_coords,
                "city_state": has_city_state,
                "foreign": foreign,
                "unknown": unknown,
                "valid_posts": valid_posts
            }
        else:
            return {
                "query": f"#{tag}",
                "status": status_code,
                "fetched": 0,
                "weather_rel": 0,
                "india_evidence": 0,
                "with_coords": 0,
                "city_state": 0,
                "foreign": 0,
                "unknown": 0,
                "valid_posts": []
            }
    except Exception as e:
        return {
            "query": f"#{tag}",
            "status": f"ERR: {e}",
            "fetched": 0,
            "weather_rel": 0,
            "india_evidence": 0,
            "with_coords": 0,
            "city_state": 0,
            "foreign": 0,
            "unknown": 0,
            "valid_posts": []
        }

async def main():
    headers = {"User-Agent": "SkyPulse-WeatherAnalytics/1.0.0 (+https://skypulse.gov.in)"}
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        tasks = [query_tag(client, tag) for tag in HASHTAGS_TO_TEST]
        results = await asyncio.gather(*tasks)

    out_file = Path("e:/SkyPulse/scripts/mastodon_search_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
