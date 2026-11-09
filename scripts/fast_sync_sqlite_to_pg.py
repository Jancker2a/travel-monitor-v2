#!/usr/bin/env python3
"""
Fast Streaming Sync Part 2: Resume remaining ~269k snapshots from SQLite to Supabase PostgreSQL.
"""

import asyncio
import logging
import sqlite3
import time
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Optional
import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fast_sync")

SQLITE_PATH = Path("/Users/andreiyankouski/travel-monitor-v2/travel_monitor_v2.db")
SUPABASE_URL = "postgresql://postgres.diwrmsoiyhxbfzwrtumi:5J4VB6%2BiU%25UkCZb@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"


def parse_dt(val) -> datetime:
    if not val:
        return datetime.now(timezone.utc)
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day, tzinfo=timezone.utc)
    s = str(val).strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    elif "+" not in s:
        s += "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now(timezone.utc)


async def main():
    start_all = time.time()
    logger.info("==================================================================")
    logger.info("🚀 Resuming SQLite -> Supabase PostgreSQL Historical Sync (from offset 2,050,000)")
    logger.info("==================================================================")

    # 1. Connect to SQLite
    sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    # 2. Connect to Supabase PostgreSQL via asyncpg
    pg_conn = await asyncpg.connect(SUPABASE_URL)
    current_pg_count = await pg_conn.fetchval("SELECT count(*) FROM price_snapshots;")
    logger.info(f"✅ Connected to Supabase PostgreSQL. Current snapshots in PG: {current_pg_count:,}")

    # Resume from offset 2,050,000
    sqlite_cur.execute("""
        SELECT cohort_hash, filter_id, recorded_at, total_price_pln, price_per_night_per_pax, currency, source
        FROM price_snapshots
        WHERE recorded_at < '2026-11-09'
        ORDER BY id ASC
        LIMIT -1 OFFSET 2050000;
    """)

    snap_columns = [
        'cohort_hash', 'filter_id', 'recorded_at', 'total_price_pln',
        'price_per_night_per_pax', 'currency', 'source'
    ]

    batch_size = 50000
    total_streamed = 0
    t0 = time.time()

    while True:
        rows = sqlite_cur.fetchmany(batch_size)
        if not rows:
            break

        records = [
            (
                r[0],                                       # cohort_hash
                r[1],                                       # filter_id
                parse_dt(r[2]),                             # recorded_at
                float(r[3]),                                # total_price_pln
                float(r[4]),                                # price_per_night_per_pax
                r[5] or "PLN",                              # currency
                r[6] or "fly_pl",                           # source
            )
            for r in rows
        ]

        await pg_conn.copy_records_to_table(
            'price_snapshots',
            records=records,
            columns=snap_columns,
        )
        total_streamed += len(records)
        elapsed = time.time() - t0
        rate = total_streamed / elapsed if elapsed > 0 else 0
        logger.info(f"  Streamed {total_streamed:,} snapshots ({rate:,.0f} rows/s)...")

    # Sequence Sync & Optimization
    logger.info("📦 Updating database sequence & running ANALYZE...")
    await pg_conn.execute("""
        SELECT setval(
            pg_get_serial_sequence('price_snapshots', 'id'),
            COALESCE((SELECT MAX(id) FROM price_snapshots), 0) + 1,
            false
        );
    """)
    await pg_conn.execute("ANALYZE price_snapshots;")
    await pg_conn.execute("ANALYZE offer_cohorts;")
    await pg_conn.execute("ANALYZE hotels;")

    total_pg_snaps = await pg_conn.fetchval("SELECT count(*) FROM price_snapshots;")
    min_snap_dt = await pg_conn.fetchval("SELECT min(recorded_at) FROM price_snapshots;")
    max_snap_dt = await pg_conn.fetchval("SELECT max(recorded_at) FROM price_snapshots;")

    total_time = time.time() - start_all
    logger.info("==================================================================")
    logger.info(f"🎉 Complete Sync Finished in {total_time:.1f}s!")
    logger.info(f"Total PostgreSQL Snapshots: {total_pg_snaps:,}")
    logger.info(f"Historical Coverage: {min_snap_dt} -> {max_snap_dt}")
    logger.info("==================================================================")

    await pg_conn.close()
    sqlite_conn.close()


if __name__ == "__main__":
    asyncio.run(main())
