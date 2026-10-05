import sqlite3
import json

conn = sqlite3.connect('skypulse.db')
cursor = conn.cursor()

print("=== SOURCES COLUMNS ===")
cursor.execute("PRAGMA table_info(sources)")
columns = [col[1] for col in cursor.fetchall()]
print("Columns:", columns)

cursor.execute("SELECT * FROM sources WHERE id = 'b082e3c2763a4245bc4130d69910a2ec'")
row = cursor.fetchone()
print(f"Source for b082e3c2763a4245bc4130d69910a2ec: {dict(zip(columns, row)) if row else None}")

cursor.execute("SELECT * FROM sources")
all_sources = cursor.fetchall()
print(f"\nAll sources in DB ({len(all_sources)}):")
for s in all_sources:
    s_dict = dict(zip(columns, s))
    print(f"  {s_dict['id']} -> {s_dict.get('name', '')} ({s_dict.get('source_type', '')})")

print("\n=== EVENT EVIDENCE TABLE ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='event_evidence'")
has_ee = cursor.fetchone()
print("Has event_evidence table:", bool(has_ee))
if has_ee:
    cursor.execute("PRAGMA table_info(event_evidence)")
    ee_cols = [col[1] for col in cursor.fetchall()]
    print("event_evidence columns:", ee_cols)
    cursor.execute("SELECT * FROM event_evidence WHERE canonical_event_id IN ('572f0279e60a4c83a971aa65452aec5f', '2519bdc7dfa04c4bb0eb30cf9500315a', '5e6fe8b775e74c4daaf6df7c1a73664f')")
    rows = cursor.fetchall()
    print(f"Evidence rows for Mumbai events: {len(rows)}")
    for r in rows:
        print(dict(zip(ee_cols, r)))
