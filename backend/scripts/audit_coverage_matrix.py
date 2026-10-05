import sqlite3

import os
db_path = 'skypulse.db' if os.path.exists('skypulse.db') else 'backend/skypulse.db'
con = sqlite3.connect(db_path)
cur = con.cursor()
tables = [row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('Tables:', tables)

for t in tables:
    cols = [col[1] for col in cur.execute(f"PRAGMA table_info({t})").fetchall()]
    count = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    st_col = None
    for candidate in ['state', 'location_state', 'primary_state']:
        if candidate in cols:
            st_col = candidate
            break
    if st_col:
        st_list = [r[0] for r in cur.execute(f"SELECT DISTINCT {st_col} FROM {t} WHERE {st_col} IS NOT NULL").fetchall()]
        print(f"Table {t} ({count} rows): state column '{st_col}', distinct states count={len(st_list)}")
        print(f"   States: {sorted(st_list)}")
    else:
        print(f"Table {t} ({count} rows): no state column, cols={cols}")
