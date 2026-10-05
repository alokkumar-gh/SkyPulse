import urllib.request
import json

req = urllib.request.urlopen("http://127.0.0.1:8000/api/v1/emerging-events?lookback_minutes=1440")
data = json.loads(req.read().decode("utf-8"))
print("Total emerging events:", data.get("total"))
print("Active count:", data.get("active_count"))
for item in data.get("items", [])[:8]:
    print("-----------------------------------------")
    print("ID:", item["id"])
    print("Category:", item["dominant_category"])
    print("Location:", item.get("location_summary"), f"({item.get('district')}, {item.get('state_name')})")
    print("Coords:", f"({item['spatial_centroid_lat']:.4f}, {item['spatial_centroid_lon']:.4f})")
    print("Signals:", item["evidence_count"], "| Independent Sources:", item["source_count"])
    print("Radius:", f"{item['spatial_radius_km']:.1f} km")
    print("Emergence Score:", item["emergence_score"], "| Confidence:", item["confidence_score"])
    print("Why Emerging bullets:", item["factors"]["explanation_bullets"])
