#!/usr/bin/env python3
"""
High-Speed Streaming Synchronization of Full 6-Month Historical Data
from SQLite (travel_monitor_v2.db) to Neon PostgreSQL.

Streams:
1. Missing Hotels (2,835)
2. Offer Cohorts (105,268)
3. Historical Price Snapshots (2,336,060 snapshots from May 28 to Nov 18)
"""

import asyncio
import logging
import sqlite3
import sys
import time
from datetime import datetime, date, timezone
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import asyncpg
import json

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("stream_history_to_neon")

PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings

SQLITE_PATH = PROJECT_DIR / "travel_monitor_v2.db"
PG_URL = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


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


def parse_d(val) -> Optional[date]:
    if not val:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


async def sync_hotels(sq_cur, pg_conn):
    logger.info("🏨 --- Step 1: Syncing Hotels ---")
    sq_cur.execute("""
        SELECT hotel_id, display_name, country, region, stars, ta_rating, ta_reviews, specs, reputation, main_image_url
        FROM hotels;
    """)
    rows = sq_cur.fetchall()
    
    records = []
    for r in rows:
        specs_json = json.dumps(r[7]) if isinstance(r[7], (dict, list)) else (r[7] if isinstance(r[7], str) and r[7].startswith("{") else None)
        rep_json = json.dumps(r[8]) if isinstance(r[8], (dict, list)) else (r[8] if isinstance(r[8], str) and r[8].startswith("{") else None)
        records.append((
            r[0], r[1], r[2], r[3],
            int(r[4]) if r[4] is not None else 4,
            float(r[5]) if r[5] is not None else None,
            int(r[6]) if r[6] is not None else 0,
            specs_json, rep_json, r[9]
        ))
    
    # Batch upsert hotels
    batch_size = 500
    for i in range(0, len(records), batch_size):
        chunk = records[i:i+batch_size]
        await pg_conn.executemany("""
            INSERT INTO hotels (hotel_id, display_name, country, region, stars, ta_rating, ta_reviews, specs, reputation, main_image_url)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (hotel_id) DO NOTHING;
        """, chunk)
    
    h_count = await pg_conn.fetchval("SELECT count(*) FROM hotels;")
    logger.info(f"✅ Hotels synced. Total in Neon PG: {h_count:,}")


async def sync_cohorts(sq_cur, pg_conn):
    logger.info("📦 --- Step 2: Syncing Offer Cohorts ---")
    sq_cur.execute("""
        SELECT cohort_hash, filter_id, hotel_id, destination_code, checkin_date, checkout_date,
               duration_nights, airport_code, board_basis, room_type, adults, children,
               operator, offer_url, is_active, first_seen_at, last_seen_at
        FROM offer_cohorts;
    """)
    rows = sq_cur.fetchall()
    logger.info(f"Loaded {len(rows):,} cohorts from SQLite.")
    
    # Query existing cohort_hashes in PG
    existing_hashes = set(r[0] for r in await pg_conn.fetch("SELECT cohort_hash FROM offer_cohorts;"))
    logger.info(f"Already existing cohorts in PG: {len(existing_hashes):,}")
    
    to_insert = []
    for r in rows:
        ch = r[0]
        if ch in existing_hashes:
            continue
        to_insert.append((
            ch, r[1] or "default", r[2], r[3],
            parse_d(r[4]), parse_d(r[5]),
            int(r[6]) if r[6] else 8,
            r[7] or "WAW", r[8] or "All Inclusive", r[9] or "Standard",
            int(r[10]) if r[10] else 2, int(r[11]) if r[11] else 1,
            r[12] or "", r[13] or "", bool(r[14]),
            parse_dt(r[15]), parse_dt(r[16])
        ))
    
    if to_insert:
        logger.info(f"Inserting {len(to_insert):,} new cohorts via copy_records_to_table...")
        await pg_conn.copy_records_to_table(
            "offer_cohorts",
            records=to_insert,
            columns=[
                "cohort_hash", "filter_id", "hotel_id", "destination_code",
                "checkin_date", "checkout_date", "duration_nights", "airport_code",
                "board_basis", "room_type", "adults", "children", "operator",
                "offer_url", "is_active", "first_seen_at", "last_seen_at"
            ]
        )
    
    c_count = await pg_conn.fetchval("SELECT count(*) FROM offer_cohorts;")
    logger.info(f"✅ Offer cohorts synced. Total in Neon PG: {c_count:,}")


async def sync_snapshots(sq_cur, pg_conn):
    logger.info("📈 --- Step 3: Streaming Historical Price Snapshots ---")
    
    # Load mapping of cohort_hash -> cohort_id from PG
    logger.info("Loading cohort_hash -> cohort_id index from PG...")
    t0 = time.time()
    id_rows = await pg_conn.fetch("SELECT cohort_hash, cohort_id FROM offer_cohorts;")
    hash_to_id = {r["cohort_hash"]: r["cohort_id"] for r in id_rows}
    logger.info(f"Mapped {len(hash_to_id):,} cohort IDs in {time.time() - t0:.2f}s.")
    
    # We want snapshots recorded before 2026-11-18 (the ones from June to mid-November)
    sq_cur.execute("""
        SELECT COUNT(*) FROM price_snapshots WHERE recorded_at < '2026-11-18';
    """)
    total_to_stream = sq_cur.fetchone()[0]
    logger.info(f"Total historical snapshots to stream: {total_to_stream:,}")
    
    sq_cur.execute("""
        SELECT cohort_hash, filter_id, recorded_at, total_price_pln, price_per_night_per_pax, currency, source
        FROM price_snapshots
        WHERE recorded_at < '2026-11-18'
        ORDER BY id ASC;
    """)
    
    batch_size = 50000
    streamed = 0
    t_start = time.time()
    
    while True:
        rows = sq_cur.fetchmany(batch_size)
        if not rows:
            break
        
        records = []
        for r in rows:
            ch = r[0]
            cid = hash_to_id.get(ch)
            if not cid:
                continue
            records.append((
                cid,
                r[1] or "default",
                parse_dt(r[2]),
                float(r[3]),
                float(r[4]) if r[4] is not None else 0.0,
                r[5] or "PLN",
                r[6] or "fly_pl"
            ))
        
        if records:
            await pg_conn.copy_records_to_table(
                "price_snapshots",
                records=records,
                columns=[
                    "cohort_id", "filter_id", "recorded_at", "total_price_pln",
                    "price_per_night_per_pax", "currency", "source"
                ]
            )
            streamed += len(records)
            elapsed = time.time() - t_start
            rate = streamed / elapsed if elapsed > 0 else 0
            pct = (streamed / total_to_stream) * 100
            logger.info(f"  Streamed {streamed:,} / {total_to_stream:,} snapshots ({pct:.1f}%) | {rate:,.0f} rows/s")
    
    # Resync sequences
    for table, col in [("price_snapshots", "id"), ("offer_cohorts", "cohort_id")]:
        await pg_conn.execute(f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', '{col}'),
                COALESCE((SELECT MAX({col}) FROM {table}), 0) + 1,
                false
            );
        """)
    
    p_count = await pg_conn.fetchval("SELECT count(*) FROM price_snapshots;")
    logger.info(f"✅ Price snapshots sync finished! Total in Neon PG: {p_count:,}")


async def main():
    start_time = time.time()
    logger.info("==================================================================")
    logger.info("🚀 Starting Full 6-Month Historical Data Stream to Neon")
    logger.info("==================================================================")
    
    sq_conn = sqlite3.connect(str(SQLITE_PATH))
    sq_cur = sq_conn.cursor()
    
    pg_conn = await asyncpg.connect(PG_URL)
    
    try:
        await sync_hotels(sq_cur, pg_conn)
        await sync_cohorts(sq_cur, pg_conn)
        await sync_snapshots(sq_cur, pg_conn)
    finally:
        await pg_conn.close()
        sq_conn.close()
    
    total_elapsed = time.time() - start_time
    logger.info("==================================================================")
    logger.info(f"🎉 Complete Migration Finished in {total_elapsed / 60:.1f} minutes!")
    logger.info("==================================================================")


if __name__ == "__main__":
    asyncio.run(main())
