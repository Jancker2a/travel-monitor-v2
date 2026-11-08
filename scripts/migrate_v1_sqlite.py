#!/usr/bin/env python3
"""
Migration Script: Imports historical data from Travel Price Monitor v1 (SQLite)
into Travel Monitor 2.0 (PostgreSQL / SQLite v2 schema).
"""

import os
import re
import sys
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.models.cohort import compute_cohort_hash

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration_v1_to_v2")

DEFAULT_V1_DB = "/Users/andreiyankouski/travel-price-monitor/data/travel_monitor.db"
DEFAULT_V2_DB = "/Users/andreiyankouski/travel-monitor-v2/travel_monitor_v2.db"


def slugify(text: str) -> str:
    text = str(text or "").lower().strip()
    text = re.sub(r"[^\w\d]+", "-", text)
    return text.strip("-") or "hotel"


def parse_departure_date(date_str: str) -> Tuple[str, str]:
    """Extracts (checkin_iso, checkout_iso) from date string."""
    if not date_str:
        return "", ""
    # 1. Look for part1.part2.YYYY
    matches = re.findall(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", date_str)
    iso_dates = []
    for p1, p2, y in matches:
        v1, v2 = int(p1), int(p2)
        if v2 > 12 and v1 <= 12:
            # p1 is month, p2 is day (e.g. 12.26.2026)
            iso_dates.append(f"{y}-{v1:02d}-{v2:02d}")
        else:
            # default DD.MM.YYYY (Polish standard, e.g. 21.11.2026)
            iso_dates.append(f"{y}-{v2:02d}-{v1:02d}")

    if not iso_dates:
        # 2. Look for YYYY-MM-DD
        m_iso = re.findall(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
        for y, m_val, d_val in m_iso:
            iso_dates.append(f"{y}-{int(m_val):02d}-{int(d_val):02d}")

    if len(iso_dates) >= 2:
        return iso_dates[0], iso_dates[1]
    elif len(iso_dates) == 1:
        return iso_dates[0], ""

    return "", ""


def parse_duration_nights(duration_str: str) -> int:
    """Parses '8 dni' or '7' into integer nights."""
    if not duration_str:
        return 7
    m = re.search(r"(\d+)", str(duration_str))
    if m:
        val = int(m.group(1))
        # Usually '8 dni' means 7 nights
        return max(1, val - 1) if "dni" in str(duration_str).lower() else val
    return 7


def run_migration(v1_db_path: str = DEFAULT_V1_DB, v2_db_path: str = DEFAULT_V2_DB):
    if not os.path.isfile(v1_db_path):
        logger.error(f"v1 database not found at '{v1_db_path}'")
        return

    logger.info(f"Opening v1 source database: {v1_db_path}")
    src_conn = sqlite3.connect(v1_db_path)
    src_conn.row_factory = sqlite3.Row

    logger.info(f"Opening v2 target database: {v2_db_path}")
    dst_conn = sqlite3.connect(v2_db_path)
    dst_cursor = dst_conn.cursor()

    # Create target tables if using SQLite for v2 testing
    dst_cursor.executescript("""
    CREATE TABLE IF NOT EXISTS hotels (
        hotel_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        country TEXT NOT NULL,
        region TEXT,
        stars INTEGER DEFAULT 4,
        ta_rating REAL,
        ta_reviews INTEGER DEFAULT 0,
        specs TEXT,
        reputation TEXT,
        main_image_url TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS offer_cohorts (
        cohort_hash TEXT PRIMARY KEY,
        hotel_id TEXT NOT NULL,
        destination_code TEXT NOT NULL,
        checkin_date TEXT NOT NULL,
        checkout_date TEXT,
        duration_nights INTEGER NOT NULL,
        airport_code TEXT NOT NULL,
        board_basis TEXT DEFAULT 'All Inclusive',
        room_type TEXT,
        adults INTEGER DEFAULT 2,
        children INTEGER DEFAULT 0,
        operator TEXT,
        offer_url TEXT,
        is_active INTEGER DEFAULT 1,
        first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (hotel_id) REFERENCES hotels (hotel_id)
    );

    CREATE TABLE IF NOT EXISTS price_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cohort_hash TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        total_price_pln REAL NOT NULL,
        price_per_night_per_pax REAL NOT NULL,
        currency TEXT DEFAULT 'PLN',
        source TEXT DEFAULT 'fly_pl',
        FOREIGN KEY (cohort_hash) REFERENCES offer_cohorts (cohort_hash)
    );
    """)

    # 1. Migrate Hotels from unique offers
    logger.info("Extracting and migrating unique hotels catalog from offers...")
    hotel_rows = src_conn.execute("""
        SELECT 
            COALESCE(canonical_hotel_name, hotel_name) as canon_name,
            hotel_name,
            filter_id,
            ta_rating,
            ta_review_count,
            image_url
        FROM offers
        GROUP BY canon_name
    """).fetchall()

    migrated_hotels = 0
    for h in hotel_rows:
        canon_name = h["canon_name"]
        h_id = slugify(canon_name)
        flt = str(h["filter_id"] or "").lower()
        country = "Египет" if "egypt" in flt else "Турция" if "turkey" in flt else "Греция" if "greece" in flt else "Кипр" if "cyprus" in flt else "Испания" if "spain" in flt else "Другие"
        
        dst_cursor.execute("""
            INSERT OR IGNORE INTO hotels (hotel_id, display_name, country, region, stars, ta_rating, ta_reviews, main_image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            h_id,
            h["hotel_name"],
            country,
            "",
            4,
            h["ta_rating"],
            h["ta_review_count"] or 0,
            h["image_url"] or ""
        ))
        migrated_hotels += 1

    # 2. Migrate Offers into OfferCohorts and PriceSnapshots
    logger.info("Migrating 43,000+ offers into OfferCohorts and PriceSnapshots...")
    offer_rows = src_conn.execute("""
        SELECT id, filter_id, hotel_name, canonical_hotel_name, price, dates,
               departure_date, return_date, duration, duration_days, departure_airport,
               scraped_at, offer_url
        FROM offers
        ORDER BY scraped_at ASC
    """).fetchall()

    migrated_cohorts = 0
    migrated_snapshots = 0
    seen_cohorts = set()

    for off in offer_rows:
        h_name = off["hotel_name"]
        h_id = slugify(h_name)
        price = float(off["price"])
        if price <= 0:
            continue

        raw_dates = off["dates"] or ""
        checkin_iso, checkout_iso = parse_departure_date(raw_dates)
        if not checkin_iso:
            checkin_iso = "2026-12-01"

        duration_n = parse_duration_nights(off["duration"])
        airport = off["departure_airport"] or "WAW"
        scraped_at = off["scraped_at"] or datetime.utcnow().isoformat()

        # Compute deterministic signature
        cohort_hash = compute_cohort_hash(
            hotel_id=h_id,
            checkin_date=datetime.strptime(checkin_iso, "%Y-%m-%d").date() if checkin_iso else datetime.utcnow().date(),
            duration_nights=duration_n,
            airport_code=airport,
            adults=2,
            board_basis="All Inclusive",
        )

        if cohort_hash not in seen_cohorts:
            dst_cursor.execute("""
                INSERT OR IGNORE INTO offer_cohorts (
                    cohort_hash, hotel_id, destination_code, checkin_date, checkout_date,
                    duration_nights, airport_code, board_basis, adults, offer_url, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cohort_hash, h_id, off["filter_id"], checkin_iso, checkout_iso,
                duration_n, airport, "All Inclusive", 2, off["offer_url"], scraped_at, scraped_at
            ))
            seen_cohorts.add(cohort_hash)
            migrated_cohorts += 1

        # Calculate normalized price: PLN / day / pax (2 adults default)
        p_per_night_pax = price / (max(1, duration_n) * 2)

        dst_cursor.execute("""
            INSERT INTO price_snapshots (cohort_hash, recorded_at, total_price_pln, price_per_night_per_pax, source)
            VALUES (?, ?, ?, ?, ?)
        """, (cohort_hash, scraped_at, price, p_per_night_pax, "fly_pl"))
        migrated_snapshots += 1

    dst_conn.commit()
    logger.info(f"✅ Migration completed successfully!")
    logger.info(f"   Hotels imported: {migrated_hotels}")
    logger.info(f"   Cohorts created: {migrated_cohorts}")
    logger.info(f"   Price snapshots recorded: {migrated_snapshots}")

    src_conn.close()
    dst_conn.close()


if __name__ == "__main__":
    run_migration()

