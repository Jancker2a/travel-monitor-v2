#!/usr/bin/env python3
"""
High-Speed Bulk Sync: origin/main of travel-price-monitor into Supabase PostgreSQL and local SQLite.
Ingests the latest runs from Nov 7-10 for all 23 active filters, resolving missing hotels like Jaz Grand Marsa.
"""

import asyncio
import csv
import io
import logging
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

import asyncpg

PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from app.models.cohort import compute_cohort_hash
from app.services.canonical_filters import resolve_filter_spec
from app.services.live_scraper import parse_departure_date, parse_duration_nights, slugify
from scripts.import_full_v1_archives import FOLDER_CONFIG

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sync_v1_main")

V1_DIR = "/Users/andreiyankouski/travel-price-monitor"
SQLITE_PATH = PROJECT_DIR / "travel_monitor_v2.db"
PG_URL = (os.environ.get("DATABASE_URL") or "").replace("postgresql+asyncpg://", "postgresql://")


def parse_iso_datetime(dt_str: str) -> Optional[datetime]:
    if not dt_str:
        return None
    s = dt_str.strip().replace(" ", "T")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    elif "+" not in s:
        s += "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


async def run_sync():
    logger.info("==================================================================")
    logger.info("🚀 High-Speed Bulk Sync: origin/main -> Supabase PostgreSQL & SQLite")
    logger.info("==================================================================")

    pg_conn = await asyncpg.connect(PG_URL)
    sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
    sqlite_cur = sqlite_conn.cursor()

    cmd = "git ls-tree -d --name-only origin/main:data/filters"
    filters = subprocess.check_output(cmd, shell=True, text=True, cwd=V1_DIR).splitlines()

    total_snapshots_synced = 0
    total_cohorts_synced = 0

    for fdir in sorted(filters):
        cfg = FOLDER_CONFIG.get(fdir)
        if not cfg:
            clean_id = fdir.replace("filter_", "")
            dest = "turkey" if "turkey" in fdir else ("egypt" if "egypt" in fdir else "greece")
            cfg = (clean_id, dest, 2, 1)

        filter_id, destination_code, def_adults, def_children = cfg
        country_name = "Турция" if destination_code == "turkey" else ("Египет" if destination_code == "egypt" else "Греция")

        cat_cmd = f"git show origin/main:data/filters/{fdir}/travel_prices.csv"
        res = subprocess.run(cat_cmd, shell=True, capture_output=True, text=True, cwd=V1_DIR)
        if res.returncode != 0 or not res.stdout.strip():
            continue

        reader = csv.DictReader(io.StringIO(res.stdout))
        
        hotels_map: Dict[str, Tuple] = {}
        cohorts_map: Dict[str, Tuple] = {}
        snapshots_raw: List[Tuple] = []
        min_recorded_at: Optional[datetime] = None

        for row in reader:
            hotel_raw = (row.get("hotel_name") or "").strip()
            if not hotel_raw or hotel_raw.startswith("<<") or hotel_raw.startswith("==") or hotel_raw.startswith(">>"):
                continue

            try:
                price_val = float(row.get("price") or 0.0)
            except ValueError:
                continue

            if price_val <= 0:
                continue

            recorded_at = parse_iso_datetime(row.get("scraped_at") or "")
            if not recorded_at:
                continue

            if min_recorded_at is None or recorded_at < min_recorded_at:
                min_recorded_at = recorded_at

            hotel_id = slugify(hotel_raw)
            dates_str = row.get("dates") or ""
            checkin_d, checkout_d = parse_departure_date(dates_str)
            if not checkin_d:
                checkin_d = recorded_at.date()

            duration_raw = row.get("duration") or ""
            nights = parse_duration_nights(duration_raw)
            airport = (row.get("departure_airport") or "WAW").replace("Warszawa - ", "").strip()
            if not airport:
                airport = "WAW"

            offer_url = row.get("offer_url") or row.get("url") or ""
            img_url = row.get("image_url") or ""

            ta_r = None
            try:
                if row.get("ta_rating"):
                    ta_r = float(row["ta_rating"])
            except ValueError:
                pass

            stars = 4
            if "categoryRating=50" in offer_url or "5*" in hotel_raw:
                stars = 5

            hotels_map[hotel_id] = (hotel_id, hotel_raw, country_name, stars, ta_r, img_url)

            cohort_hash = compute_cohort_hash(
                hotel_id=hotel_id,
                checkin_date=checkin_d,
                duration_nights=nights,
                airport_code=airport,
                adults=def_adults,
                board_basis="All Inclusive",
                filter_id=filter_id,
            )

            cohorts_map[cohort_hash] = (
                cohort_hash, filter_id, hotel_id, destination_code, checkin_d, checkout_d,
                nights, airport, def_adults, def_children, offer_url, recorded_at
            )

            pp_night = price_val / max(1, def_adults * nights)
            snapshots_raw.append((cohort_hash, filter_id, recorded_at, price_val, pp_night))

        if not snapshots_raw:
            continue

        # 1. Bulk Upsert Hotels (PG & SQLite)
        hotel_records = list(hotels_map.values())
        await pg_conn.executemany("""
            INSERT INTO hotels (hotel_id, display_name, country, stars, ta_rating, main_image_url)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (hotel_id) DO UPDATE
            SET main_image_url = COALESCE(hotels.main_image_url, EXCLUDED.main_image_url),
                ta_rating = COALESCE(hotels.ta_rating, EXCLUDED.ta_rating);
        """, hotel_records)

        sqlite_cur.executemany("""
            INSERT OR IGNORE INTO hotels (hotel_id, display_name, country, stars, ta_rating, main_image_url)
            VALUES (?, ?, ?, ?, ?, ?);
        """, [(h[0], h[1], h[2], h[3], h[4], h[5]) for h in hotel_records])

        # 2. Bulk Upsert Cohorts (PG & SQLite)
        cohort_records = list(cohorts_map.values())
        await pg_conn.executemany("""
            INSERT INTO offer_cohorts (
                cohort_hash, filter_id, hotel_id, destination_code, checkin_date, checkout_date,
                duration_nights, airport_code, board_basis, adults, children, operator, offer_url,
                first_seen_at, last_seen_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'All Inclusive', $9, $10, '', $11, $12, $12)
            ON CONFLICT (cohort_hash) DO UPDATE
            SET last_seen_at = GREATEST(offer_cohorts.last_seen_at, EXCLUDED.last_seen_at);
        """, cohort_records)

        sqlite_cur.executemany("""
            INSERT OR IGNORE INTO offer_cohorts (
                cohort_hash, filter_id, hotel_id, destination_code, checkin_date, checkout_date,
                duration_nights, airport_code, board_basis, adults, children, operator, offer_url,
                first_seen_at, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'All Inclusive', ?, ?, '', ?, ?, ?);
        """, [(c[0], c[1], c[2], c[3], str(c[4]), str(c[5]) if c[5] else None, c[6], c[7], c[8], c[9], c[10], c[11].isoformat(), c[11].isoformat()) for c in cohort_records])

        # 3. Retrieve PG cohort_id for all hashes
        cohort_hashes = list(cohorts_map.keys())
        id_rows = await pg_conn.fetch("""
            SELECT cohort_hash, cohort_id FROM offer_cohorts WHERE cohort_hash = ANY($1);
        """, cohort_hashes)
        cohort_id_map = {r["cohort_hash"]: r["cohort_id"] for r in id_rows}

        # 4. Check existing snapshots in PG to prevent duplicates
        cohort_ids = list(cohort_id_map.values())
        existing_snaps = await pg_conn.fetch("""
            SELECT cohort_id, recorded_at FROM price_snapshots
            WHERE cohort_id = ANY($1) AND recorded_at >= $2;
        """, cohort_ids, min_recorded_at)
        existing_set = {(r["cohort_id"], r["recorded_at"]) for r in existing_snaps}

        new_pg_snaps = []
        new_sqlite_snaps = []
        for ch, fid, rec, price, pp in snapshots_raw:
            cid = cohort_id_map.get(ch)
            if cid and (cid, rec) not in existing_set:
                new_pg_snaps.append((cid, fid, rec, price, pp, "PLN", "fly_pl"))
                existing_set.add((cid, rec))
            new_sqlite_snaps.append((ch, fid, rec.isoformat(), price, pp, "PLN", "fly_pl"))

        if new_pg_snaps:
            await pg_conn.executemany("""
                INSERT INTO price_snapshots (cohort_id, filter_id, recorded_at, total_price_pln, price_per_night_per_pax, currency, source)
                VALUES ($1, $2, $3, $4, $5, $6, $7);
            """, new_pg_snaps)

        sqlite_cur.executemany("""
            INSERT OR IGNORE INTO price_snapshots (cohort_hash, filter_id, recorded_at, total_price_pln, price_per_night_per_pax, currency, source)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, new_sqlite_snaps)

        sqlite_conn.commit()
        total_snapshots_synced += len(new_pg_snaps)
        total_cohorts_synced += len(cohort_hashes)
        logger.info(f"✅ Filter '{fdir}' synced: +{len(new_pg_snaps)} new PG snapshots ({len(snapshots_raw)} raw).")

    # Sequence sync
    for table in ["price_snapshots", "offer_cohorts"]:
        col = "cohort_id" if table == "offer_cohorts" else "id"
        await pg_conn.execute(f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', '{col}'),
                COALESCE((SELECT MAX({col}) FROM {table}), 0) + 1,
                false
            );
        """)

    await pg_conn.close()
    sqlite_conn.close()

    logger.info("==================================================================")
    logger.info(f"🏁 Sync Complete! Total new PG snapshots inserted: {total_snapshots_synced}")
    logger.info("==================================================================")


if __name__ == "__main__":
    asyncio.run(run_sync())
