import sqlite3
import glob
import json
import uuid

dbs = glob.glob('**/*.db', recursive=True)
print("DBs found:", dbs)

for db_path in dbs:
    print(f"\n=================== Inspecting {db_path} ===================")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print("Tables:", tables)
        
        if 'weather_events' in tables:
            cur.execute("""
                SELECT id, category, severity, confidence_score, primary_state, primary_district, 
                       centroid_lat, centroid_lon, status, verification_status, created_at, updated_at
                FROM weather_events
                WHERE category LIKE '%CYCLONE%' OR primary_state LIKE '%Telangana%'
            """)
            events = cur.fetchall()
            print(f"Matching weather_events ({len(events)}):")
            for ev in events:
                print("Event:", ev)
                ev_id = ev[0]
                
                # Check linked reports / evidence
                if 'weather_reports' in tables:
                    cur.execute("""
                        SELECT id, title, description, category, severity, confidence_score, source_id, 
                               raw_content, metadata, created_at, observation_time
                        FROM weather_reports
                        WHERE canonical_event_id = ?
                    """, (ev_id,))
                    reps = cur.fetchall()
                    print(f"  Linked weather_reports ({len(reps)}):")
                    for r in reps:
                        print("    Report:", r[:8])
                        if r[8]:
                            print("    Meta:", r[8][:200])
                
                # Check event_evidence table
                if 'event_evidence' in tables:
                    cur.execute("""
                        SELECT * FROM event_evidence WHERE event_id = ?
                    """, (ev_id,))
                    evid = cur.fetchall()
                    print(f"  Event evidence ({len(evid)}):", evid)
                
                # Check sources
                if 'sources' in tables:
                    cur.execute("""
                        SELECT s.id, s.name, s.source_type, s.reliability_score 
                        FROM sources s
                        JOIN weather_reports r ON r.source_id = s.id
                        WHERE r.canonical_event_id = ?
                    """, (ev_id,))
                    srcs = cur.fetchall()
                    print(f"  Sources ({len(srcs)}):", srcs)

    except Exception as e:
        print(f"Error reading {db_path}: {e}")
