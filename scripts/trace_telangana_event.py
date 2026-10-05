import sqlite3
import json

conn = sqlite3.connect('backend/skypulse.db')
cur = conn.cursor()

event_id = '58012d609088487bb972f391408cbca2'

print("=== WEATHER EVENT ===")
cur.execute("SELECT * FROM weather_events WHERE id = ?", (event_id,))
cols = [c[0] for c in cur.description]
event_row = cur.fetchone()
print(json.dumps(dict(zip(cols, event_row)), indent=2, default=str))

print("\n=== LINKED WEATHER REPORTS ===")
cur.execute("SELECT * FROM weather_reports WHERE canonical_event_id = ?", (event_id,))
rep_cols = [c[0] for c in cur.description]
reports = cur.fetchall()
for r in reports:
    print(json.dumps(dict(zip(rep_cols, r)), indent=2, default=str))

print("\n=== LINKED EVENT EVIDENCE ===")
cur.execute("SELECT * FROM event_evidence WHERE event_id = ?", (event_id,))
ev_cols = [c[0] for c in cur.description]
evidences = cur.fetchall()
for e in evidences:
    print(json.dumps(dict(zip(ev_cols, e)), indent=2, default=str))

print("\n=== LINKED VERIFICATION RESULTS ===")
cur.execute("SELECT * FROM verification_results WHERE canonical_event_id = ?", (event_id,))
vr_cols = [c[0] for c in cur.description]
verifs = cur.fetchall()
for v in verifs:
    print(json.dumps(dict(zip(vr_cols, v)), indent=2, default=str))

print("\n=== SOURCES ===")
for r in reports:
    r_dict = dict(zip(rep_cols, r))
    s_id = r_dict.get('source_id')
    cur.execute("SELECT * FROM sources WHERE id = ?", (s_id,))
    s_cols = [c[0] for c in cur.description]
    src = cur.fetchone()
    if src:
        print(json.dumps(dict(zip(s_cols, src)), indent=2, default=str))

print("\n=== WEATHER OBSERVATIONS FOR TELANGANA ===")
cur.execute("SELECT * FROM weather_observations WHERE state LIKE '%Telangana%' OR location_name LIKE '%Telangana%' OR district LIKE '%Telangana%' LIMIT 10")
obs_cols = [c[0] for c in cur.description]
obss = cur.fetchall()
for o in obss:
    print(json.dumps(dict(zip(obs_cols, o)), indent=2, default=str))
