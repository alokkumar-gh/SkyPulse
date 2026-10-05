import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skypulse.db")
if os.path.exists(db_path):
    con = sqlite3.connect(db_path, timeout=30.0)
    cur = con.cursor()
    existing_cols = [c[1] for c in cur.execute("PRAGMA table_info(weather_events)").fetchall()]
    
    new_cols = [
        ("observed_at", "DATETIME"),
        ("ingested_at", "DATETIME"),
        ("last_seen_at", "DATETIME"),
        ("expires_at", "DATETIME"),
        ("lifecycle_status", "VARCHAR(20) DEFAULT 'ACTIVE'"),
    ]
    
    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            print(f"Adding column {col_name}...")
            cur.execute(f"ALTER TABLE weather_events ADD COLUMN {col_name} {col_type}")
            
    con.commit()
    final_cols = [c[1] for c in cur.execute("PRAGMA table_info(weather_events)").fetchall()]
    print("Migration successful! Current columns:", final_cols)
    con.close()
else:
    print("No skypulse.db found, skipping SQLite migration.")
