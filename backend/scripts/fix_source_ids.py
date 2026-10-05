import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from app.db.session import async_session_factory
from sqlalchemy import text

async def main():
    async with async_session_factory() as db:
        res = await db.execute(text("UPDATE weather_reports SET source_id = '00000000-0000-0000-0000-000000000008' WHERE typeof(source_id) = 'integer'"))
        await db.commit()
        print(f"Fixed {res.rowcount} rows with integer source_id in weather_reports.")

if __name__ == "__main__":
    asyncio.run(main())
