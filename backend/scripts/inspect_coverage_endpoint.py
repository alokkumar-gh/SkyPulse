import urllib.request
import json

req = urllib.request.urlopen("http://127.0.0.1:8000/api/v1/weather/coverage")
data = json.loads(req.read().decode("utf-8"))
print("Summary:", {k: v for k, v in data.items() if k != "national_coverage_matrix"})
matrix = data.get("national_coverage_matrix", [])
print(f"Matrix states count: {len(matrix)}")
for m in matrix[:8]:
    print(f"  {m['state']}: status={m['status']}, obs={m['observations_count']}, reports={m['reports_count']}, events={m['events_count']}, dist={m['districts_with_data']}/{m['total_known_districts']}")
