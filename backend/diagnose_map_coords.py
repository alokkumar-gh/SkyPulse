import sqlite3
import json

conn = sqlite3.connect('skypulse.db')
cursor = conn.cursor()

cursor.execute("SELECT id, category, primary_state, primary_district, primary_city, centroid_lat, centroid_lon, is_active FROM weather_events WHERE is_active = 1")
active_events = cursor.fetchall()

total_active = len(active_events)
with_lat = 0
with_lon = 0
with_both = 0
valid_coords = 0
regional_only = 0
invalid_coords = 0

print("="*60)
print("DATABASE ACTIVE EVENTS COORDINATE AUDIT")
print("="*60)

for ev in active_events:
    eid, cat, state, dist, city, lat, lon, is_act = ev
    if lat is not None:
        with_lat += 1
    if lon is not None:
        with_lon += 1
    if lat is not None and lon is not None:
        with_both += 1
        if 6.0 <= lat <= 38.0 and 68.0 <= lon <= 98.0:
            valid_coords += 1
        else:
            invalid_coords += 1
    else:
        regional_only += 1

print(f"TOTAL ACTIVE:       {total_active}")
print(f"WITH_LATITUDE:      {with_lat}")
print(f"WITH_LONGITUDE:     {with_lon}")
print(f"WITH_BOTH:          {with_both}")
print(f"VALID_COORDINATES:  {valid_coords}")
print(f"REGIONAL_ONLY:      {regional_only}")
print(f"INVALID_COORDINATES:{invalid_coords}")

# Check polygon events
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cap_alert_zones'")
has_cap = cursor.fetchone()
print(f"Has cap_alert_zones table: {bool(has_cap)}")

# Check sources
print("\n" + "="*60)
print("SOURCES AUDIT")
print("="*60)
cursor.execute("SELECT id, name, source_type, connector_class, trust_score, is_active FROM sources")
for s in cursor.fetchall():
    print(f"Source: ID={s[0]} | NAME={s[1]} | TYPE={s[2]} | CLASS={s[3]} | ACTIVE={s[5]}")

print("\n" + "="*60)
print("WEATHER_REPORTS AUDIT")
print("="*60)
cursor.execute("SELECT source_id, COUNT(*), SUM(CASE WHEN location_lat IS NOT NULL AND location_lon IS NOT NULL THEN 1 ELSE 0 END) FROM weather_reports GROUP BY source_id")
for r in cursor.fetchall():
    print(f"Source ID {r[0]}: Total Reports={r[1]}, With GPS Coordinates={r[2]}")

conn.close()
