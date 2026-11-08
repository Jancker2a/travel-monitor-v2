"""
Re-normalization Engine for Travel Monitor 2.0.
Processes 43K+ historical snapshots and generates a clean, dedicated
normalized price history (1 person, 8 nights benchmark) based on
empirical econometric parameters derived from Fly.pl focus groups.
"""
import sys
import os
import sqlite3
import time
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "travel_monitor_v2.db")

DESTINATION_FLIGHT_BENCHMARKS = {
    "turkey": 1200.0,
    "egypt": 1250.0,
    "greece": 1300.0,
    "spain": 1350.0,
    "cyprus": 1300.0,
}
DEFAULT_FLIGHT_BENCHMARK = 1250.0

SINGLE_SUPPLEMENT_FACTORS = {
    "turkey": 1.18,
    "egypt": 1.17,
    "greece": 1.30,
    "spain": 1.29,
}
DEFAULT_SINGLE_SUPPLEMENT = 1.20

CHILD_HOTEL_WEIGHT = 0.20  # Children <12 pay ~20% of adult hotel rate

def re_normalize():
    print(f"⚡ Opening database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Create normalized_price_snapshots table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS normalized_price_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hotel_id VARCHAR(128) NOT NULL,
        destination_code VARCHAR(32),
        recorded_at DATETIME NOT NULL,
        normalized_price_1p_8n FLOAT NOT NULL,
        pure_hotel_night_rate FLOAT NOT NULL,
        flight_estimate_seat FLOAT NOT NULL,
        source_type VARCHAR(32) NOT NULL DEFAULT 'renormalized_v1_cohort',
        source_cohort_hash VARCHAR(32),
        is_crawler_standard BOOLEAN DEFAULT 0
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_norm_hotel_time ON normalized_price_snapshots (hotel_id, recorded_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_norm_dest_price ON normalized_price_snapshots (destination_code, normalized_price_1p_8n);")
    conn.commit()

    # Clear previous re-normalized records to prevent duplicate runs
    cursor.execute("DELETE FROM normalized_price_snapshots WHERE source_type = 'renormalized_v1_cohort';")
    conn.commit()

    # 2. Query all price snapshots joined with their cohort details
    print("⏳ Fetching raw snapshots and cohorts...")
    t0 = time.time()
    cursor.execute("""
        SELECT 
            p.id,
            p.cohort_hash,
            p.recorded_at,
            p.total_price_pln,
            c.hotel_id,
            c.destination_code,
            c.duration_nights,
            c.adults,
            c.children
        FROM price_snapshots p
        JOIN offer_cohorts c ON p.cohort_hash = c.cohort_hash
        WHERE p.total_price_pln > 0
    """)
    rows = cursor.fetchall()
    print(f"Loaded {len(rows)} raw snapshots in {time.time() - t0:.2f}s")

    batch = []
    batch_size = 5000
    total_inserted = 0

    for r in rows:
        snap_id, cohort_hash, recorded_at, total_price, hotel_id, dest, nights, adults, children = r
        nights = max(1, nights or 7)
        adults = max(1, adults or 2)
        children = max(0, children or 0)
        dest_key = str(dest or "turkey").lower().strip()

        # Flight benchmark & Single factor
        f_seat = DESTINATION_FLIGHT_BENCHMARKS.get(dest_key, DEFAULT_FLIGHT_BENCHMARK)
        s_single = SINGLE_SUPPLEMENT_FACTORS.get(dest_key, DEFAULT_SINGLE_SUPPLEMENT)

        # Cost decomposition
        flight_total = (adults + children) * f_seat
        effective_guests = adults + (CHILD_HOTEL_WEIGHT * children)
        hotel_total = max(10.0, total_price - flight_total)
        pure_hotel_night = hotel_total / (nights * effective_guests)

        # Standard benchmark: 1 person, 8 nights
        norm_1p_8n = f_seat + (8.0 * pure_hotel_night * s_single)

        batch.append((
            hotel_id,
            dest,
            recorded_at,
            round(norm_1p_8n, 2),
            round(pure_hotel_night, 2),
            round(f_seat, 2),
            "renormalized_v1_cohort",
            cohort_hash,
            0
        ))

        if len(batch) >= batch_size:
            cursor.executemany("""
                INSERT INTO normalized_price_snapshots (
                    hotel_id, destination_code, recorded_at,
                    normalized_price_1p_8n, pure_hotel_night_rate, flight_estimate_seat,
                    source_type, source_cohort_hash, is_crawler_standard
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            conn.commit()
            total_inserted += len(batch)
            batch = []

    if batch:
        cursor.executemany("""
            INSERT INTO normalized_price_snapshots (
                hotel_id, destination_code, recorded_at,
                normalized_price_1p_8n, pure_hotel_night_rate, flight_estimate_seat,
                source_type, source_cohort_hash, is_crawler_standard
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch)
        conn.commit()
        total_inserted += len(batch)

    # 3. Verification & Metrics
    cursor.execute("SELECT COUNT(*) FROM normalized_price_snapshots;")
    count_norm = cursor.fetchone()[0]

    cursor.execute("""
        SELECT 
            MIN(normalized_price_1p_8n),
            AVG(normalized_price_1p_8n),
            MAX(normalized_price_1p_8n),
            AVG(pure_hotel_night_rate)
        FROM normalized_price_snapshots;
    """)
    min_p, avg_p, max_p, avg_h = cursor.fetchone()

    print("\n" + "=" * 60)
    print("✅ RE-NORMALIZATION COMPLETE!")
    print(f"   Total normalized snapshots: {count_norm}")
    print(f"   Benchmark (1 pax, 8 nights): Min = {min_p:.0f} zł | Avg = {avg_p:.0f} zł | Max = {max_p:.0f} zł")
    print(f"   Average pure hotel rate:     {avg_h:.0f} zł / night")
    print("=" * 60)

    conn.close()

if __name__ == "__main__":
    re_normalize()
