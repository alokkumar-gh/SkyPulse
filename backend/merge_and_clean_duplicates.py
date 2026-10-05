"""
SkyPulse Duplicate Merger and False Positive Cleanup
====================================================
Merges duplicate WeatherEvents created during ingestion cycles,
re-associates reports and evidence, and marks duplicates inactive.
Also removes impossible meteorological false positives (e.g. snowfall in tropical plains).
"""

import sqlite3
from datetime import datetime, timezone

def merge_duplicates():
    conn = sqlite3.connect("skypulse.db")
    c = conn.cursor()

    print("=== 1. REMOVING IMPOSSIBLE METEOROLOGICAL FALSE POSITIVES ===")
    # Tropical/subtropical states where SNOWFALL is physically impossible
    no_snow_states = ["Tamil Nadu", "Kerala", "Karnataka", "Andhra Pradesh", "Telangana", "Odisha", "Maharashtra", "Goa", "Gujarat", "Delhi", "Punjab", "Haryana", "Rajasthan", "Uttar Pradesh", "Bihar", "West Bengal", "Assam"]
    for st in no_snow_states:
        c.execute("""
            UPDATE weather_events 
            SET is_active = 0, is_deleted = 1 
            WHERE category = 'SNOWFALL' AND primary_state = ?
        """, (st,))
        if c.rowcount > 0:
            print(f"  Deactivated {c.rowcount} false SNOWFALL events in {st}")

    print("\n=== 2. MERGING DUPLICATE ACTIVE EVENTS ===")
    c.execute("""
        SELECT category, primary_state, COALESCE(primary_district, '') as dist, count(*) as cnt
        FROM weather_events 
        WHERE is_active = 1 AND is_deleted = 0
        GROUP BY category, primary_state, dist
        HAVING cnt > 1
    """)
    clusters = c.fetchall()
    print(f"Found {len(clusters)} duplicate active clusters to merge:")

    total_merged = 0
    for cat, state, dist, cnt in clusters:
        dist_filter = "primary_district IS NULL" if not dist else "primary_district = ?"
        params = (cat, state) if not dist else (cat, state, dist)

        c.execute(f"""
            SELECT id, last_updated_at, evidence_count 
            FROM weather_events 
            WHERE is_active = 1 AND is_deleted = 0 
              AND category = ? AND primary_state = ? AND {dist_filter}
            ORDER BY last_updated_at DESC
        """, params)
        rows = c.fetchall()
        if len(rows) <= 1:
            continue

        master_id = rows[0][0]
        duplicate_ids = [r[0] for r in rows[1:]]

        print(f"  Cluster {cat} in {state} / {dist or 'State-Wide'}: Master {master_id[:8]}, Deactivating {len(duplicate_ids)} duplicates")

        # Repoint reports
        for dup_id in duplicate_ids:
            c.execute("UPDATE weather_reports SET canonical_event_id = ? WHERE canonical_event_id = ?", (master_id, dup_id))
            c.execute("UPDATE event_evidence SET canonical_event_id = ? WHERE canonical_event_id = ?", (master_id, dup_id))
            c.execute("UPDATE weather_events SET is_active = 0, is_deleted = 1 WHERE id = ?", (dup_id,))
            total_merged += 1

        # Update evidence count on master
        c.execute("SELECT count(*) FROM weather_reports WHERE canonical_event_id = ?", (master_id,))
        total_reps = c.fetchone()[0]
        c.execute("UPDATE weather_events SET evidence_count = ? WHERE id = ?", (total_reps, master_id))

    conn.commit()

    c.execute("SELECT count(*) FROM weather_events WHERE is_active = 1 AND is_deleted = 0")
    active_clean = c.fetchone()[0]
    print(f"\nCompleted! Merged {total_merged} duplicate events.")
    print(f"Remaining clean active canonical events: {active_clean}")
    conn.close()

if __name__ == "__main__":
    merge_duplicates()
