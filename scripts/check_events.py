import sqlite3

conn = sqlite3.connect('backend/skypulse.db')
cur = conn.cursor()
cur.execute("PRAGMA table_info(weather_events)")
print("Columns in weather_events:", [c[1] for c in cur.fetchall()])

cur.execute("SELECT * FROM weather_events WHERE category LIKE '%CYCLONE%' OR primary_state LIKE '%Telangana%'")
events = cur.fetchall()
cur.execute("PRAGMA table_info(weather_events)")
cols = [c[1] for c in cur.fetchall()]
for ev in events:
    print(dict(zip(cols, ev)))
