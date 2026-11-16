#!/usr/bin/env python3
"""
Fast Streaming Migration from Supabase to Neon PostgreSQL.
Transfers hotels, filter_monitors, normalized_price_snapshots, offer_cohorts, and price_snapshots.
"""

import asyncio
import logging
import time
import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("supabase_to_neon")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
NEON_URL = os.environ.get("NEON_URL", "")


async def sync_table(c_sub, c_neon, table_name: str, cols: list, batch_size: int = 50000):
    col_str = ", ".join(cols)
    count = await c_sub.fetchval(f"SELECT COUNT(*) FROM {table_name}")
    logger.info(f"--- Syncing '{table_name}' ({count:,} records) ---")
    if count == 0:
        return

    # Clear destination table first
    await c_neon.execute(f"TRUNCATE TABLE {table_name} CASCADE")

    start = time.time()
    offset = 0
    while offset < count:
        rows = await c_sub.fetch(
            f"SELECT {col_str} FROM {table_name} ORDER BY 1 LIMIT {batch_size} OFFSET {offset}"
        )
        if not rows:
            break
        records = [tuple(r.values()) for r in rows]
        await c_neon.copy_records_to_table(table_name, records=records, columns=cols)
        offset += len(rows)
        pct = (offset / count) * 100
        rate = offset / max(0.1, time.time() - start)
        logger.info(f"[{table_name}] {offset:,} / {count:,} ({pct:.1f}%) | {rate:,.0f} rows/s")

    elapsed = time.time() - start
    logger.info(f"✅ '{table_name}' completed in {elapsed:.1f}s ({offset:,} rows transferred).")


async def main():
    start_all = time.time()
    logger.info("==================================================================")
    logger.info("🚀 Starting Direct Streaming Sync: Supabase -> Neon PostgreSQL")
    logger.info("==================================================================")

    c_sub = await asyncpg.connect(SUPABASE_URL)
    c_neon = await asyncpg.connect(NEON_URL)

    # 1. Sync small catalog tables first
    await sync_table(
        c_sub, c_neon, "filter_monitors",
        [
            "id", "group_id", "title", "subtitle", "destination", "target_url",
            "is_active", "is_hourly", "last_scraped_at", "last_offers_count",
            "last_min_price_pln", "last_status", "created_by", "created_at", "updated_at",
        ],
    )

    await sync_table(
        c_sub, c_neon, "hotels",
        [
            "hotel_id", "display_name", "country", "region", "stars",
            "ta_rating", "ta_reviews", "specs", "reputation", "main_image_url",
            "created_at", "updated_at",
        ],
    )

    await sync_table(
        c_sub, c_neon, "normalized_price_snapshots",
        [
            "id", "hotel_id", "destination_code", "recorded_at",
            "normalized_price_1p_8n", "pure_hotel_night_rate", "flight_estimate_seat",
            "source_type", "source_cohort_hash", "is_crawler_standard",
        ],
    )

    # 2. Sync offer_cohorts
    await sync_table(
        c_sub, c_neon, "offer_cohorts",
        [
            "cohort_id", "cohort_hash", "filter_id", "hotel_id", "destination_code",
            "checkin_date", "checkout_date", "duration_nights", "airport_code",
            "board_basis", "room_type", "adults", "children", "operator",
            "offer_url", "is_active", "first_seen_at", "last_seen_at",
        ],
    )

    # 3. Sync price_snapshots
    await sync_table(
        c_sub, c_neon, "price_snapshots",
        [
            "id", "cohort_id", "filter_id", "recorded_at",
            "total_price_pln", "price_per_night_per_pax", "currency", "source",
        ],
    )

    await c_sub.close()
    await c_neon.close()

    total_time = time.time() - start_all
    logger.info("==================================================================")
    logger.info(f"🎉 All tables migrated to Neon successfully in {total_time:.1f}s!")
    logger.info("==================================================================")


if __name__ == "__main__":
    asyncio.run(main())
