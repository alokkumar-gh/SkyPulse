import httpx
import json
import re
import math
import sys
import os

sys.path.insert(0, r"e:\SkyPulse\backend")

from connectors.normalizer import (
    INDIAN_CITIES_REFERENCE,
    INDIAN_STATES_REFERENCE,
    enrich_location,
    sanitize_text,
    INDIA_LAT_MIN, INDIA_LAT_MAX, INDIA_LON_MIN, INDIA_LON_MAX
)
from connectors.social_web_connector import matches_weather_filter, DEFAULT_WEATHER_KEYWORDS, DEFAULT_WEATHER_HASHTAGS

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

headers = {
    "User-Agent": "SkyPulse-WeatherAnalytics/1.0.0 (+https://skypulse.gov.in)"
}

out_file = r"e:\SkyPulse\scripts\mastodon_search_results.json"
results_summary = []

for tag in HASHTAGS_TO_TEST:
    url = f"https://mastodon.social/api/v1/timelines/tag/{tag}?limit=20"
    print(f"Querying #{tag}...", flush=True)
    try:
        with httpx.Client(timeout=6.0, headers=headers) as client:
            resp = client.get(url)
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
                
                valid_india_posts = []

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
                            valid_india_posts.append({
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

                entry = {
                    "query": f"#{tag}",
                    "status": status_code,
                    "fetched": fetched,
                    "weather_rel": weather_rel,
                    "india_evidence": has_india_evidence,
                    "with_coords": has_coords,
                    "city_state": has_city_state,
                    "foreign": foreign,
                    "unknown": unknown,
                    "valid_posts": valid_india_posts
                }
                results_summary.append(entry)
                print(f"  #{tag}: {fetched} fetched, {weather_rel} weather, {has_india_evidence} India valid", flush=True)
            else:
                entry = {
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
                results_summary.append(entry)
                print(f"  #{tag}: HTTP {status_code}", flush=True)
    except Exception as e:
        entry = {
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
        results_summary.append(entry)
        print(f"  #{tag}: Exception {e}", flush=True)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results_summary, f, indent=2)

print("Done!", flush=True)
