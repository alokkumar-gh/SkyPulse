"""SkyPulse Database Partition Management Script

Creates range partitions for:
- weather_reports (monthly)
- audit_logs (quarterly)
"""

import asyncio
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
import asyncpg
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.core.config import settings


async def create_weather_report_partitions(conn, months_ahead: int = 12):
    """Create monthly partitions for weather_reports table."""
    now = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    print(f"Creating monthly partitions for weather_reports starting from {now.strftime('%Y-%m')}...")

    for i in range(-1, months_ahead + 1):
        start_date = now + relativedelta(months=i)
        end_date = start_date + relativedelta(months=1)
        part_name = f"weather_reports_{start_date.strftime('%Y_%m')}"
        start_str = start_date.strftime("%Y-%m-%d 00:00:00+00")
        end_str = end_date.strftime("%Y-%m-%d 00:00:00+00")

        sql = f"""
        CREATE TABLE IF NOT EXISTS {part_name} PARTITION OF weather_reports
            FOR VALUES FROM ('{start_str}') TO ('{end_str}');
        """
        try:
            await conn.execute(sql)
            print(f"  [+] Partition created/verified: {part_name} ({start_str} to {end_str})")
        except Exception as e:
            print(f"  [!] Notice creating {part_name}: {e}")


async def create_audit_log_partitions(conn, quarters_ahead: int = 4):
    """Create quarterly partitions for audit_logs table."""
    now = datetime.now(timezone.utc)
    current_quarter = (now.month - 1) // 3 + 1
    quarter_start_month = (current_quarter - 1) * 3 + 1
    q_now = now.replace(month=quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    print(f"Creating quarterly partitions for audit_logs starting from Q{current_quarter} {q_now.year}...")

    for i in range(-1, quarters_ahead + 1):
        start_date = q_now + relativedelta(months=i * 3)
        end_date = start_date + relativedelta(months=3)
        q_num = (start_date.month - 1) // 3 + 1
        part_name = f"audit_logs_{start_date.year}_q{q_num}"
        start_str = start_date.strftime("%Y-%m-%d 00:00:00+00")
        end_str = end_date.strftime("%Y-%m-%d 00:00:00+00")

        sql = f"""
        CREATE TABLE IF NOT EXISTS {part_name} PARTITION OF audit_logs
            FOR VALUES FROM ('{start_str}') TO ('{end_str}');
        """
        try:
            await conn.execute(sql)
            print(f"  [+] Partition created/verified: {part_name} ({start_str} to {end_str})")
        except Exception as e:
            print(f"  [!] Notice creating {part_name}: {e}")


async def main():
    # Convert SQLAlchemy database URL to asyncpg DSN
    dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    print(f"Connecting to database to maintain partitions...")
    try:
        conn = await asyncpg.connect(dsn)
        try:
            await create_weather_report_partitions(conn)
            await create_audit_log_partitions(conn)
            print("Partition maintenance completed successfully.")
        finally:
            await conn.close()
    except Exception as e:
        print(f"Database connection error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
