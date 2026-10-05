"""
Populate authoritative locations table from INDIA_STATES and INDIA_DISTRICTS.
"""

import sqlite3
import uuid
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connectors.weather_discovery.india_locations import INDIA_STATES, INDIA_DISTRICTS

def populate():
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "skypulse.db"))
    con = sqlite3.connect(db_path, timeout=30.0)
    con.execute("PRAGMA busy_timeout = 30000;")
    cur = con.cursor()

    cur.execute("SELECT count(*) FROM locations")
    cnt = cur.fetchone()[0]
    print(f"Current locations count: {cnt}")

    rows_to_insert = []
    seen = set()

    # 1. Insert 36 States & UTs
    for code, s in INDIA_STATES.items():
        st_name = s["name"]
        key = ("STATE", st_name, None)
        if key not in seen:
            seen.add(key)
            rows_to_insert.append((
                str(uuid.uuid4()),
                st_name,
                "STATE",
                st_name,
                None,
                "IN",
                s["lat"],
                s["lon"],
                "[]",
                "2026-10-01 00:00:00"
            ))

    # 2. Insert Districts
    for d in INDIA_DISTRICTS:
        dist_name = d["district"]
        st_name = d["state"]
        key = ("DISTRICT", st_name, dist_name)
        if key not in seen:
            seen.add(key)
            rows_to_insert.append((
                str(uuid.uuid4()),
                dist_name,
                "DISTRICT",
                st_name,
                dist_name,
                "IN",
                d["lat"],
                d["lon"],
                "[]",
                "2026-10-01 00:00:00"
            ))

    print(f"Prepared {len(rows_to_insert)} authoritative locations (States + Districts).")
    cur.executemany("""
        INSERT INTO locations (id, name, level, state, district, country, lat, lon, adjacent_location_ids, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows_to_insert)
    con.commit()
    print("Locations table populated successfully!")

if __name__ == "__main__":
    populate()
