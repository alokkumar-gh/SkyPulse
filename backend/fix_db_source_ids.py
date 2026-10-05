import sqlite3
import time

conn = sqlite3.connect('skypulse.db', timeout=60)
cur = conn.cursor()
cur.execute("PRAGMA journal_mode=WAL")
cur.execute("PRAGMA busy_timeout=60000")

cur.execute("UPDATE weather_reports SET source_id = '00000000-0000-0000-0000-000000000008' WHERE source_id = 8")
print('Updated rows:', cur.rowcount)
conn.commit()

# Verify no remaining integers in any UUID columns
for col in ['id', 'source_id', 'submitted_by', 'canonical_event_id']:
    cur.execute(f"SELECT typeof({col}), count(1) FROM weather_reports GROUP BY typeof({col})")
    print(col, cur.fetchall())

conn.close()
print("REPAIR COMPLETE")
