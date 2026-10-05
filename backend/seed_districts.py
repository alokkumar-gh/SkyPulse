import sqlite3
import uuid
import sys
sys.stdout.reconfigure(encoding='utf-8')
from connectors.weather_discovery.india_locations import INDIA_DISTRICTS, INDIA_STATES

conn = sqlite3.connect('skypulse.db')
c = conn.cursor()

c.execute("SELECT name, state FROM locations WHERE level = 'DISTRICT'")
existing_districts = set((r[0].lower(), r[1].lower()) for r in c.fetchall())
print(f"Initial districts in locations table: {len(existing_districts)}")

added = 0
for d in INDIA_DISTRICTS:
    d_name = d['district']
    state = d['state']
    key = (d_name.lower(), state.lower())
    if key not in existing_districts:
        c.execute("""
            INSERT INTO locations (id, name, level, state, district, country, lat, lon, adjacent_location_ids, created_at)
            VALUES (?, ?, 'DISTRICT', ?, ?, 'IN', ?, ?, '[]', datetime('now'))
        """, (str(uuid.uuid4()), d_name, state, d_name, d['lat'], d['lon']))
        existing_districts.add(key)
        added += 1

conn.commit()

# Verify Odisha districts
c.execute("SELECT name FROM locations WHERE level = 'DISTRICT' AND state = 'Odisha' ORDER BY name")
od_districts = [r[0] for r in c.fetchall()]
print(f"Added {added} districts. Total Odisha districts now in locations: {len(od_districts)}")
print("Odisha districts in DB:", od_districts)
