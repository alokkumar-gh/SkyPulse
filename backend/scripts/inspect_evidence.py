import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio, uuid
from app.db.session import async_session_factory
from sqlalchemy import text

async def main():
    async with async_session_factory() as db:
        res = await db.execute(text("""
            SELECT ee.canonical_event_id, ee.weather_report_id, 
                   wr.id, wr.source_id, typeof(wr.id), typeof(wr.source_id), typeof(wr.canonical_event_id)
            FROM event_evidence ee
            LEFT JOIN weather_reports wr ON wr.id = ee.weather_report_id
            WHERE ee.canonical_event_id = '874fa5ec939a428d9bd7243614950bc3' OR ee.canonical_event_id = '874fa5ec-939a-428d-9bd7-243614950bc3'
        """))
        print('Event evidence rows for 874fa5ec:', res.all())
        
        # Check all tables where typeof column is not text/null for any UUID column
        tables_res = await db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [r[0] for r in tables_res.all() if not r[0].startswith('sqlite_')]
        for tbl in tables:
            cols_res = await db.execute(text(f"PRAGMA table_info({tbl})"))
            for col in cols_res.all():
                cname, ctype = col[1], col[2]
                if 'UUID' in ctype.upper() or cname.endswith('_id') or (cname == 'id' and tbl != 'audit_logs'):
                    r = await db.execute(text(f"SELECT typeof({cname}), count(*), group_concat(distinct {cname}) FROM {tbl} WHERE typeof({cname}) NOT IN ('text', 'null') GROUP BY typeof({cname})"))
                    rows = r.all()
                    if rows:
                        print(f"NON-TEXT UUID IN {tbl}.{cname}:", rows)

if __name__ == "__main__":
    asyncio.run(main())
