"""
Fast batch enrichment of weather_reports in SQLite with real Indian geographic coordinates
from the canonical INDIA_DISTRICTS and INDIA_STATES registry in india_locations.py.
"""
import sqlite3
import re
from connectors.weather_discovery.india_locations import INDIA_STATES, INDIA_DISTRICTS

conn = sqlite3.connect('skypulse.db', timeout=60)
cur = conn.cursor()
cur.execute("PRAGMA journal_mode=WAL")
cur.execute("PRAGMA busy_timeout=60000")

# Build lookup tables
dist_lookup = {}
for d in INDIA_DISTRICTS:
    key = d['district'].lower().strip()
    dist_lookup[key] = (d['lat'], d['lon'], d['state'], d['district'])

state_lookup = {}
for s in INDIA_STATES.values():
    key = s['name'].lower().strip()
    state_lookup[key] = (s['lat'], s['lon'], s['name'])
    if 'capital' in s:
        dist_lookup[s['capital'].lower().strip()] = (s['lat'], s['lon'], s['name'], s['capital'])

# 1. Update where location_district is populated
cur.execute("SELECT id, location_district, location_state FROM weather_reports WHERE location_lat IS NULL AND location_district IS NOT NULL")
rows = cur.fetchall()
batch_dist = []
for row_id, dist, state in rows:
    if not dist:
        continue
    k = dist.lower().strip()
    if k in dist_lookup:
        lat, lon, st, canon_dist = dist_lookup[k]
        batch_dist.append((lat, lon, st, canon_dist, row_id))

if batch_dist:
    cur.executemany("UPDATE weather_reports SET location_lat = ?, location_lon = ?, location_state = ?, location_district = ? WHERE id = ?", batch_dist)
    print(f"Updated by district: {len(batch_dist)}")

# 2. Update where location_state is populated
cur.execute("SELECT id, location_state FROM weather_reports WHERE location_lat IS NULL AND location_state IS NOT NULL")
rows_st = cur.fetchall()
batch_st = []
for row_id, state in rows_st:
    if not state:
        continue
    k = state.lower().strip()
    if k in state_lookup:
        lat, lon, canon_st = state_lookup[k]
        batch_st.append((lat, lon, canon_st, row_id))

if batch_st:
    cur.executemany("UPDATE weather_reports SET location_lat = ?, location_lon = ?, location_state = ? WHERE id = ?", batch_st)
    print(f"Updated by state: {len(batch_st)}")

conn.commit()

# Final count
cur.execute("SELECT count(1) FROM weather_reports WHERE location_lat IS NOT NULL")
total_with_coords = cur.fetchone()[0]
print(f"Total reports with coordinates: {total_with_coords}")

conn.close()
print("ENRICHMENT COMPLETE")
