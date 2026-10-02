import sqlite3
import uuid

conn = sqlite3.connect("backend/skypulse.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]

for t in tables:
    cur.execute(f"PRAGMA table_info({t})")
    cols = cur.fetchall()
    uuid_cols = [c[1] for c in cols if "UUID" in c[2].upper()]
    for uc in uuid_cols:
        cur.execute(f"SELECT typeof({uc}), count(*) FROM {t} GROUP BY typeof({uc})")
        types = cur.fetchall()
        for tp, cnt in types:
            if tp in ("integer", "real"):
                print(f"Table {t}, column {uc} has {cnt} rows of type {tp}!")
                cur.execute(f"SELECT rowid, {uc} FROM {t} WHERE typeof({uc}) = '{tp}'")
                rows = cur.fetchall()
                print("Values:", rows)
                for rid, val in rows:
                    new_u = str(uuid.uuid4()).replace("-", "")
                    cur.execute(f"UPDATE {t} SET {uc} = '{new_u}' WHERE rowid = {rid}")
                    print(f"Updated row {rid} to {new_u}")

conn.commit()
conn.close()
print("Scan and repair completed.")
