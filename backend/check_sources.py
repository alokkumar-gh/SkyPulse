import sqlite3

conn = sqlite3.connect('skypulse.db')
cur = conn.cursor()
cur.execute("SELECT source_id, count(1) FROM weather_reports WHERE typeof(source_id) = 'integer' GROUP BY source_id")
print('integers in weather_reports:', cur.fetchall())

cur.execute("SELECT id, name, typeof(id) FROM sources")
print('sources table:')
for row in cur.fetchall():
    print(row)
conn.close()
