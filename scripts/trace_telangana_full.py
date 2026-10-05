import sqlite3
import json

conn = sqlite3.connect('backend/skypulse.db')
cur = conn.cursor()

def print_table_info(table_name):
    cur.execute(f"PRAGMA table_info({table_name})")
    cols = [f"{c[1]} ({c[2]})" for c in cur.fetchall()]
    print(f"Table {table_name}:", ", ".join(cols))

for t in ['weather_events', 'weather_reports', 'event_evidence', 'verification_results', 'sources', 'weather_observations']:
    print_table_info(t)

event_id = '58012d609088487bb972f391408cbca2'

print("\n--- Sources connected to this event via weather_reports ---")
cur.execute("""
    SELECT s.* FROM sources s
    JOIN weather_reports r ON r.source_id = s.id
    WHERE r.canonical_event_id = ?
""", (event_id,))
src_cols = [c[0] for c in cur.description]
for row in cur.fetchall():
    print(dict(zip(src_cols, row)))

print("\n--- Event Evidence ---")
cur.execute("SELECT * FROM event_evidence WHERE canonical_event_id = ?", (event_id,))
ee_cols = [c[0] for c in cur.description]
for row in cur.fetchall():
    print(dict(zip(ee_cols, row)))

print("\n--- Verification Results ---")
cur.execute("SELECT * FROM verification_results WHERE canonical_event_id = ?", (event_id,))
vr_cols = [c[0] for c in cur.description]
for row in cur.fetchall():
    print(dict(zip(vr_cols, row)))

print("\n--- Weather Observations for Telangana ---")
cur.execute("SELECT * FROM weather_observations WHERE state LIKE '%Telangana%' OR location_name LIKE '%Telangana%' LIMIT 5")
wo_cols = [c[0] for c in cur.description]
for row in cur.fetchall():
    print(dict(zip(wo_cols, row)))
