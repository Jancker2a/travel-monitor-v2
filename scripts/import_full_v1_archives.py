#!/usr/bin/env python3
"""
Full Historical Archives Importer for Travel Monitor 2.0
Imports ~2.3M+ historical rows from all 23 filters in travel-price-monitor/data/filters/*/
into travel_monitor_v2.db (SQLite / PostgreSQL) with isolated cohorts per filter.
"""

import os
import re
import sys
import glob
import time
import urllib.parse
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
import sqlite3
import pandas as pd

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.models.cohort import compute_cohort_hash

SOURCE_FILTERS_DIR = "/Users/andreiyankouski/travel-price-monitor/data/filters"
DEFAULT_V2_DB = "/Users/andreiyankouski/travel-monitor-v2/travel_monitor_v2.db"

# Mapping from folder name to (canonical_monitor_id, destination_code, default_adults, default_children)
FOLDER_CONFIG = {
    "filter_13_16_days": ("13_16_days", "egypt", 2, 1),
    "filter_7_10_days": ("7_10_days", "egypt", 2, 1),
    "filter_cyprus_7_10": ("cyprus_7_10", "cyprus", 1, 0),
    "filter_benchmark_cyprus_1p_7_8": ("benchmark_cyprus_1p_7_8", "cyprus", 1, 0),
    "filter_benchmark_egypt_1p_7_8": ("benchmark_egypt_1p_7_8", "egypt", 1, 0),
    "filter_benchmark_greece_1p_7_8": ("benchmark_greece_1p_7_8", "greece", 1, 0),
    "filter_benchmark_turkey_1p_7_8": ("benchmark_turkey_1p_7_8", "turkey", 1, 0),
    "filter_lastminute_turkey_0_4": ("lastminute_turkey_0_4", "turkey", 2, 0),
    "filter_lastminute_egypt_0_4": ("lastminute_egypt_0_4", "egypt", 2, 0),
    "filter_lastminute_greece_0_4": ("lastminute_greece_0_4", "greece", 2, 0),
    "filter_lastminute_cyprus_0_4": ("lastminute_cyprus_0_4", "cyprus", 2, 0),
    "filter_eb_egypt_aug27_7_10": ("eb_egypt_aug27_7_10", "egypt", 2, 1),
    "filter_eb_egypt_jul27_7_10": ("eb_egypt_jul27_7_10", "egypt", 2, 1),
    "filter_eb_egypt_oct27_7_10": ("eb_egypt_oct27_7_10", "egypt", 2, 1),
    "filter_eb_greece_aug27_7_10": ("eb_greece_aug27_7_10", "greece", 2, 1),
    "filter_eb_greece_jul27_7_10": ("eb_greece_jul27_7_10", "greece", 2, 1),
    "filter_eb_turkey_aug27_7_10": ("eb_turkey_aug27_7_10", "turkey", 2, 1),
    "filter_eb_turkey_jul27_13_16": ("eb_turkey_jul27_13_16", "turkey", 2, 1),
    "filter_eb_turkey_jul27_7_10": ("eb_turkey_jul27_7_10", "turkey", 2, 1),
    "filter_egypt_autumn_2026_13_16_days": ("egypt_autumn_2026_13_16_days", "egypt", 2, 1),
    "filter_egypt_autumn_2026_7_10_days": ("egypt_autumn_2026_7_10_days", "egypt", 2, 1),
    "filter_egypt_ny_dec24_2026_7_10_days": ("egypt_ny_dec24_2026_7_10_days", "egypt", 2, 1),
    "filter_egypt_ny_dec28_2026_7_10_days": ("egypt_ny_dec28_2026_7_10_days", "egypt", 2, 1),
    "filter_egypt_sharm_dec20_28_1p": ("egypt_sharm_dec20_28_1p", "egypt", 1, 0),
    "filter_egypt_sharm_dec20_29_1p": ("egypt_sharm_dec20_29_1p", "egypt", 1, 0),
    "filter_greece_13_16_days": ("greece_13_16_days", "greece", 2, 1),
    "filter_greece_7_10_days": ("greece_7_10_days", "greece", 2, 1),
    "filter_turkey_13_16_days": ("turkey_13_16_days", "turkey", 2, 1),
    "filter_turkey_7_10_days": ("turkey_7_10_days", "turkey", 2, 1),
    "filter_turkey_9_11_days": ("turkey_9_11_days", "turkey", 2, 1),
    "filter_turkey_vacation_jul18_2026": ("turkey_vacation_jul18", "turkey", 2, 1),
}


def slugify(text: str) -> str:
    text = str(text or "").lower().strip()
    text = re.sub(r"[^\w\d]+", "-", text)
    return text.strip("-") or "hotel"


def parse_dates_string(dates_str: str) -> Tuple[Optional[date], Optional[date]]:
    """Extracts (checkin_date, checkout_date) from date string."""
    if not dates_str or pd.isna(dates_str):
        return None, None
    parts = str(dates_str).split(" - ")
    if len(parts) != 2:
        return None, None
    d1_s, d2_s = parts[0].strip(), parts[1].strip()
    d1, d2 = None, None
    try:
        if "." in d1_s:
            d1 = datetime.strptime(d1_s, "%d.%m.%Y").date()
        else:
            d1 = datetime.strptime(d1_s, "%Y-%m-%d").date()
    except Exception:
        pass
    try:
        if "." in d2_s:
            d2 = datetime.strptime(d2_s, "%d.%m.%Y").date()
        else:
            d2 = datetime.strptime(d2_s, "%Y-%m-%d").date()
    except Exception:
        pass
    return d1, d2


def normalize_airport_code(airport_str: str) -> str:
    s = urllib.parse.unquote(str(airport_str or "")).strip()
    low = s.lower()
    if "modlin" in low:
        return "WMI"
    elif "radom" in low:
        return "RDO"
    elif "okęcie" in low or "okecie" in low or "chopin" in low or low == "warszawa":
        return "WAW"
    elif "berlin" in low or "ber" in low:
        return "BER"
    elif "katowice" in low or "ktw" in low:
        return "KTW"
    elif "gdańsk" in low or "gdansk" in low or "gdn" in low:
        return "GDN"
    elif "kraków" in low or "krakow" in low or "krk" in low:
        return "KRK"
    elif "wrocław" in low or "wroclaw" in low or "wro" in low:
        return "WRO"
    elif "poznań" in low or "poznan" in low or "poz" in low:
        return "POZ"
    elif s:
        return s[:10].upper()
    return "WAW"


def parse_offer_params(offer_url: str, default_adults: int = 2, default_children: int = 1) -> Tuple[int, int, str, str]:
    """Parses adults, children, operator, board_basis from offer_url."""
    adults = default_adults
    children = default_children
    operator = None
    board = "All Inclusive"
    if offer_url and not pd.isna(offer_url):
        try:
            parsed = urllib.parse.urlparse(offer_url)
            qs = urllib.parse.parse_qs(parsed.query)
            if "adults" in qs:
                adults = int(qs["adults"][0])
            if "children" in qs:
                # e.g. children=2020-12-10 or children=1
                children = len(qs["children"]) if qs["children"][0] != "0" else 0
            if "operator" in qs:
                operator = qs["operator"][0]
            if "catering" in qs:
                cat = qs["catering"][0].lower()
                if "all" in cat:
                    board = "All Inclusive"
                elif "hb" in cat or "half" in cat:
                    board = "Half Board"
                elif "bb" in cat or "bed" in cat:
                    board = "Bed & Breakfast"
        except Exception:
            pass
    return adults, children, operator, board


def run_full_import(db_path: str = DEFAULT_V2_DB, wipe_first: bool = True):
    print("=" * 70)
    print("🚀 [TRAVEL MONITOR 2.0] Full Historical Archives Import Starting...")
    print(f"📦 Source Directory: {SOURCE_FILTERS_DIR}")
    print(f"💾 Target Database:  {db_path}")
    print("=" * 70)

    start_total_time = time.time()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Performance PRAGMAs for fast bulk ingestion
    cur.execute("PRAGMA synchronous = OFF;")
    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute("PRAGMA cache_size = 100000;")
    cur.execute("PRAGMA temp_store = MEMORY;")

    # Ensure schema has all columns & indexes
    cur.execute("PRAGMA table_info(offer_cohorts)")
    cohort_cols = [row[1] for row in cur.fetchall()]
    if "filter_id" not in cohort_cols:
        cur.execute("ALTER TABLE offer_cohorts ADD COLUMN filter_id TEXT")

    cur.execute("PRAGMA table_info(price_snapshots)")
    snap_cols = [row[1] for row in cur.fetchall()]
    if "filter_id" not in snap_cols:
        cur.execute("ALTER TABLE price_snapshots ADD COLUMN filter_id TEXT")

    if wipe_first:
        print("🧹 Clearing existing snapshots and cohorts for clean migration...")
        cur.execute("DELETE FROM price_snapshots;")
        cur.execute("DELETE FROM offer_cohorts;")
        conn.commit()

    # Pre-load known hotels
    cur.execute("SELECT hotel_id FROM hotels;")
    seen_hotels = set(r[0] for r in cur.fetchall())
    seen_cohorts = set()

    total_snapshots_imported = 0
    total_cohorts_imported = 0
    total_hotels_imported = 0

    BATCH_SIZE = 25000
    hotel_batch = []
    cohort_batch = []
    snapshot_batch = []

    def flush_batches():
        nonlocal total_snapshots_imported, total_cohorts_imported, total_hotels_imported
        if hotel_batch:
            cur.executemany(
                """INSERT OR IGNORE INTO hotels 
                   (hotel_id, display_name, country, stars, ta_rating, ta_reviews, main_image_url) 
                   VALUES (?, ?, ?, ?, ?, ?, ?);""",
                hotel_batch,
            )
            total_hotels_imported += len(hotel_batch)
            hotel_batch.clear()

        if cohort_batch:
            cur.executemany(
                """INSERT OR IGNORE INTO offer_cohorts 
                   (cohort_hash, filter_id, hotel_id, destination_code, checkin_date, checkout_date, 
                    duration_nights, airport_code, board_basis, adults, children, operator, offer_url, 
                    first_seen_at, last_seen_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                cohort_batch,
            )
            total_cohorts_imported += len(cohort_batch)
            cohort_batch.clear()

        if snapshot_batch:
            cur.executemany(
                """INSERT OR IGNORE INTO price_snapshots 
                   (cohort_hash, filter_id, recorded_at, total_price_pln, price_per_night_per_pax, currency, source) 
                   VALUES (?, ?, ?, ?, ?, 'PLN', 'fly_pl');""",
                snapshot_batch,
            )
            total_snapshots_imported += len(snapshot_batch)
            snapshot_batch.clear()

        conn.commit()

    filter_folders = sorted(os.listdir(SOURCE_FILTERS_DIR))
    for fdir in filter_folders:
        full_fpath = os.path.join(SOURCE_FILTERS_DIR, fdir)
        if not os.path.isdir(full_fpath):
            continue

        cfg = FOLDER_CONFIG.get(fdir)
        if not cfg:
            clean_id = fdir.replace("filter_", "")
            dest = "turkey" if "turkey" in fdir else ("egypt" if "egypt" in fdir else "greece")
            cfg = (clean_id, dest, 2, 1)

        filter_id, destination_code, def_adults, def_children = cfg

        # Collect all archive files + main travel_prices.csv
        archive_dir = os.path.join(full_fpath, "archive")
        csv_files = []
        if os.path.isdir(archive_dir):
            arch_files = sorted(
                glob.glob(os.path.join(archive_dir, "travel_prices_*.csv"))
            )
            csv_files.extend(arch_files)

        main_csv = os.path.join(full_fpath, "travel_prices.csv")
        if os.path.isfile(main_csv):
            csv_files.append(main_csv)

        if not csv_files:
            continue

        print(f"\n📂 Processing [{filter_id}] ({destination_code}): {len(csv_files)} CSV files...")
        filter_start_time = time.time()
        filter_rows_count = 0

        for csv_path in csv_files:
            try:
                # Read with pandas skipping bad lines and conflict markers
                df = pd.read_csv(
                    csv_path,
                    dtype=str,
                    on_bad_lines="skip",
                    quoting=1,  # csv.QUOTE_ALL
                    keep_default_na=False,
                )
            except Exception as read_err:
                # Fallback to python csv reader if needed
                try:
                    df = pd.read_csv(csv_path, dtype=str, on_bad_lines="skip")
                except Exception:
                    continue

            if df.empty or "price" not in df.columns or "scraped_at" not in df.columns:
                continue

            for _, row in df.iterrows():
                p_raw = row.get("price", "")
                if not p_raw or p_raw.startswith("<") or p_raw.startswith("=") or p_raw.startswith(">"):
                    continue

                try:
                    price = float(p_raw)
                except (ValueError, TypeError):
                    continue

                if price < 500 or price > 150000:
                    continue

                raw_scraped_at = row.get("scraped_at", "")
                if not raw_scraped_at or len(raw_scraped_at) < 10:
                    continue

                # Parse date
                d1, d2 = parse_dates_string(row.get("dates", ""))
                if not d1:
                    continue

                duration_nights = (d2 - d1).days if d2 else 7
                if duration_nights <= 0 or duration_nights > 30:
                    duration_nights = 7

                hotel_name = str(row.get("hotel_name", "")).strip()
                if not hotel_name or len(hotel_name) < 2:
                    continue

                hotel_id = slugify(hotel_name)
                airport_code = normalize_airport_code(row.get("departure_airport", ""))
                offer_url = str(row.get("offer_url", "")).strip()

                adults, children, operator, board_basis = parse_offer_params(
                    offer_url, def_adults, def_children
                )

                cohort_hash = compute_cohort_hash(
                    hotel_id=hotel_id,
                    checkin_date=d1,
                    duration_nights=duration_nights,
                    airport_code=airport_code,
                    adults=adults,
                    board_basis=board_basis,
                    filter_id=filter_id,
                )

                # Hotel upsert queue
                if hotel_id not in seen_hotels:
                    stars_val = 5 if ("5" in str(row.get("rating", "")) or "5*" in hotel_name) else 4
                    ta_r = None
                    try:
                        ta_r = float(row.get("ta_rating", "")) if row.get("ta_rating") else None
                    except Exception:
                        pass
                    ta_rev = 0
                    try:
                        ta_rev = int(row.get("ta_review_count", 0)) if row.get("ta_review_count") else 0
                    except Exception:
                        pass
                    img = str(row.get("image_url", "")).strip()
                    hotel_batch.append((hotel_id, hotel_name, destination_code, stars_val, ta_r, ta_rev, img))
                    seen_hotels.add(hotel_id)

                # Cohort queue
                if cohort_hash not in seen_cohorts:
                    cohort_batch.append((
                        cohort_hash,
                        filter_id,
                        hotel_id,
                        destination_code,
                        d1.isoformat(),
                        d2.isoformat() if d2 else None,
                        duration_nights,
                        airport_code,
                        board_basis,
                        adults,
                        children,
                        operator,
                        offer_url,
                        raw_scraped_at,
                        raw_scraped_at,
                    ))
                    seen_cohorts.add(cohort_hash)

                # Snapshot queue
                pax_count = max(1, adults + children)
                price_pax_night = round(price / (max(1, duration_nights) * pax_count), 2)
                snapshot_batch.append((
                    cohort_hash,
                    filter_id,
                    raw_scraped_at,
                    price,
                    price_pax_night,
                ))

                filter_rows_count += 1

                if len(snapshot_batch) >= BATCH_SIZE:
                    flush_batches()

        # Flush any remaining items for this filter
        flush_batches()
        f_elapsed = time.time() - filter_start_time
        print(f"   ↳ Finished [{filter_id}]: {filter_rows_count:,} snapshots in {f_elapsed:.1f}s")

    # Final flush
    flush_batches()

    print("\n⚡ Creating database indexes for sub-millisecond query performance...")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cohort_filter_hotel ON offer_cohorts (filter_id, hotel_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cohort_filter ON offer_cohorts (filter_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_filter_time ON price_snapshots (filter_id, recorded_at);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_cohort_time ON price_snapshots (cohort_hash, recorded_at);")

    # Analyze database for query optimizer
    cur.execute("ANALYZE;")
    conn.commit()
    conn.close()

    total_elapsed = time.time() - start_total_time
    print("=" * 70)
    print(f"🎉 MIGRATION COMPLETE in {total_elapsed:.1f} seconds!")
    print(f"📊 Total Hotels:    {len(seen_hotels):,}")
    print(f"🏷️ Total Cohorts:   {len(seen_cohorts):,}")
    print(f"📈 Total Snapshots: {total_snapshots_imported:,}")
    print("=" * 70)


if __name__ == "__main__":
    run_full_import()
