import sqlite3
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('backend/skypulse.db')
cur = conn.cursor()
cur.execute("SELECT id, source_name, observation_type, state, district, city, station_name, observed_at, temperature_c, wind_speed_kmh, precipitation_mm, weather_condition FROM weather_observations WHERE state LIKE '%Telangana%' LIMIT 10")
cols = [c[0] for c in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))
