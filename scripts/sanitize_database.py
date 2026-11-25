#!/usr/bin/env python3
"""
Idempotent Database Sanitization & Data Quality Repair Script for Travel Monitor 2.0 (Neon PG).
Fixes:
1. Orphaned test user monitor cohorts/snapshots (monitor_* not present in user_monitors).
2. Corrupted check-in dates (e.g. eb_egypt_oct27_7_10 2026-10 -> authoritative offer_url departureDate 2027-10).
3. Cross-country hotel collisions (shams-safaga -> Египет, mountain-view -> Кипр, sandy-beach Turkey split).
4. Duplicate same-country hotel records (e.g. 'LIMAK LARA DELUXE' vs 'Limak Lara De Luxe').
5. Airport code normalization (Warszawa/Okęcie -> WAW, Modlin -> WMI, ВСЕ АЭРОПО recovered from offer_url).
6. Board basis canonicalization ('All inclusive' -> 'All Inclusive', 'Ultra AI' -> 'Ultra All Inclusive', etc.).
7. Exact same-minute duplicate snapshots removal + consistent price_per_night_per_pax recalculation.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from app.database import engine
from app.services.normalization import (
    normalize_airport_code,
    normalize_board_basis,
    extract_offer_url_dates,
    normalize_dest_slug,
)


async def sanitize():
    print("=== Starting Deep DB Sanitization ===")

    # 1. Remove orphaned test monitor_% snapshots/cohorts (only where user_monitor does not exist)
    async with engine.begin() as conn:
        r_orphan_snaps = await conn.execute(text("""
            DELETE FROM price_snapshots
            WHERE filter_id LIKE 'monitor_%'
              AND NOT EXISTS (
                  SELECT 1 FROM user_monitors um WHERE 'monitor_' || um.id = price_snapshots.filter_id
              )
        """))
        r_orphan_coh = await conn.execute(text("""
            DELETE FROM offer_cohorts
            WHERE filter_id LIKE 'monitor_%'
              AND NOT EXISTS (
                  SELECT 1 FROM user_monitors um WHERE 'monitor_' || um.id = offer_cohorts.filter_id
              )
        """))
        print(f"1. Deleted orphan test monitor rows: {r_orphan_snaps.rowcount} snapshots, {r_orphan_coh.rowcount} cohorts")

    # 2. Repair corrupted checkin_date / checkout_date where offer_url explicitly holds authoritative departureDate
    async with engine.begin() as conn:
        bad_dates = (await conn.execute(text("""
            SELECT cohort_id, filter_id, hotel_id, checkin_date, checkout_date, offer_url,
                   duration_nights, airport_code, adults, board_basis, cohort_hash
            FROM offer_cohorts
            WHERE checkin_date < DATE(first_seen_at)
               OR (filter_id LIKE '%27%' AND EXTRACT(YEAR FROM checkin_date) = 2026)
        """))).fetchall()

        fixed_dates = 0
        merged_collisions = 0
        for cid, fid, hid, chk, ret, url, dur, air, ad, brd, chash in bad_dates:
            dep_u, ret_u = extract_offer_url_dates(url)
            new_chk = dep_u
            if not new_chk and chk and "27" in (fid or "") and chk.year == 2026:
                try:
                    new_chk = chk.replace(year=2027)
                except ValueError:
                    new_chk = chk.replace(year=2027, day=28)
            if not new_chk or new_chk == chk:
                continue
            new_ret = ret_u or ret
            if not new_ret and dur:
                from datetime import timedelta
                new_ret = new_chk + timedelta(days=int(dur))

            from app.models.cohort import compute_cohort_hash
            new_hash = compute_cohort_hash(
                hotel_id=hid,
                checkin_date=new_chk,
                duration_nights=int(dur or 7),
                airport_code=air or "WAW",
                adults=int(ad or 2),
                board_basis=brd or "All Inclusive",
                filter_id=fid,
            )
            existing_target = (await conn.execute(
                text("SELECT cohort_id FROM offer_cohorts WHERE cohort_hash = :h AND cohort_id != :cid"),
                {"h": new_hash, "cid": cid},
            )).scalar()
            if existing_target:
                await conn.execute(
                    text("UPDATE price_snapshots SET cohort_id = :tgt WHERE cohort_id = :src"),
                    {"tgt": existing_target, "src": cid},
                )
                await conn.execute(text("DELETE FROM offer_cohorts WHERE cohort_id = :cid"), {"cid": cid})
                merged_collisions += 1
            else:
                await conn.execute(
                    text("""
                        UPDATE offer_cohorts
                        SET checkin_date = :chk, checkout_date = :ret, cohort_hash = :h
                        WHERE cohort_id = :cid
                    """),
                    {"chk": new_chk, "ret": new_ret, "h": new_hash, "cid": cid},
                )
                fixed_dates += 1
        print(f"2. Repaired bad check-in dates: {fixed_dates} updated, {merged_collisions} merged into existing cohorts")

    # 3. Fix cross-country hotel collisions & country misattributions
    async with engine.begin() as conn:
        # Correct clear single-country misattributions verified from Safaga / Cyprus cohorts
        await conn.execute(text("""
            UPDATE hotels SET country = 'Египет', region = COALESCE(NULLIF(region, ''), 'Сафага')
            WHERE hotel_id = 'shams-safaga' AND LOWER(country) != 'египет'
        """))
        await conn.execute(text("""
            UPDATE hotels SET country = 'Кипр'
            WHERE hotel_id = 'mountain-view'
              AND NOT EXISTS (SELECT 1 FROM offer_cohorts oc WHERE oc.hotel_id = 'mountain-view' AND LOWER(oc.destination_code) LIKE '%gre%')
              AND EXISTS (SELECT 1 FROM offer_cohorts oc WHERE oc.hotel_id = 'mountain-view' AND LOWER(oc.destination_code) LIKE '%cyp%')
        """))

        # Split sandy-beach Turkey cohorts out of Cyprus 'sandy-beach'
        sb_tr = (await conn.execute(text("""
            SELECT COUNT(*) FROM offer_cohorts WHERE hotel_id = 'sandy-beach' AND LOWER(destination_code) LIKE '%turk%'
        """))).scalar() or 0
        if sb_tr > 0:
            await conn.execute(text("""
                INSERT INTO hotels (hotel_id, display_name, country, region, stars)
                VALUES ('tr-sandy-beach', 'Sandy Beach (Turkey)', 'Турция', 'Турция', 4)
                ON CONFLICT (hotel_id) DO NOTHING
            """))
            await conn.execute(text("""
                UPDATE offer_cohorts
                SET hotel_id = 'tr-sandy-beach'
                WHERE hotel_id = 'sandy-beach' AND LOWER(destination_code) LIKE '%turk%'
            """))
        print(f"3. Fixed cross-country hotel collisions (split {sb_tr} tr-sandy-beach cohorts)")

    # 4. Merge same-country duplicate hotel records (ignoring case/punctuation)
    async with engine.begin() as conn:
        dup_groups = (await conn.execute(text("""
            SELECT REGEXP_REPLACE(LOWER(TRIM(display_name)), '[^a-zа-я0-9]+', '', 'g') as norm_nm,
                   LOWER(TRIM(country)) as c,
                   ARRAY_AGG(hotel_id ORDER BY LENGTH(display_name) DESC, hotel_id ASC) as hids
            FROM hotels
            GROUP BY 1, 2
            HAVING COUNT(*) > 1
        """))).fetchall()
        merged_hotels = 0
        for _, _, hids in dup_groups:
            if len(hids) < 2:
                continue
            # Prefer hotel with most snapshots as canonical target
            cnt_rows = (await conn.execute(text("""
                SELECT h.hotel_id, COUNT(ps.id) as s_cnt
                FROM hotels h
                LEFT JOIN offer_cohorts oc ON oc.hotel_id = h.hotel_id
                LEFT JOIN price_snapshots ps ON ps.cohort_id = oc.cohort_id
                WHERE h.hotel_id = ANY(:hids)
                GROUP BY 1
                ORDER BY 2 DESC, 1 ASC
            """), {"hids": list(hids)})).fetchall()
            keep_id = cnt_rows[0][0]
            drop_ids = [r[0] for r in cnt_rows[1:]]
            for drop_id in drop_ids:
                await conn.execute(text("""
                    UPDATE offer_cohorts SET hotel_id = :keep WHERE hotel_id = :drop
                """), {"keep": keep_id, "drop": drop_id})
                await conn.execute(text("""
                    UPDATE normalized_price_snapshots SET hotel_id = :keep WHERE hotel_id = :drop
                """), {"keep": keep_id, "drop": drop_id})
                # Preserve metadata onto keep_id if missing
                await conn.execute(text("""
                    UPDATE hotels k
                    SET ta_rating = COALESCE(k.ta_rating, d.ta_rating),
                        ta_reviews = GREATEST(COALESCE(k.ta_reviews, 0), COALESCE(d.ta_reviews, 0)),
                        main_image_url = COALESCE(k.main_image_url, d.main_image_url),
                        specs = COALESCE(k.specs, d.specs),
                        reputation = COALESCE(k.reputation, d.reputation)
                    FROM hotels d
                    WHERE k.hotel_id = :keep AND d.hotel_id = :drop
                """), {"keep": keep_id, "drop": drop_id})
                await conn.execute(text("DELETE FROM hotels WHERE hotel_id = :drop"), {"drop": drop_id})
                merged_hotels += 1
        print(f"4. Merged same-country duplicate hotel entities: {merged_hotels}")

    # 5. Normalize airport_code across offer_cohorts (including recovering 'ВСЕ АЭРОПО' from offer_url)
    async with engine.begin() as conn:
        non_iata = (await conn.execute(text("""
            SELECT cohort_id, airport_code, offer_url
            FROM offer_cohorts
            WHERE airport_code IS NULL
               OR LENGTH(TRIM(airport_code)) != 3
               OR airport_code != UPPER(airport_code)
               OR airport_code ~ '[^A-Z]'
        """))).fetchall()
        ap_updates = []
        for cid, raw_ap, url in non_iata:
            norm_ap = normalize_airport_code(raw_ap, url)
            if norm_ap and norm_ap != raw_ap:
                ap_updates.append({"cid": cid, "ap": norm_ap})
        for i in range(0, len(ap_updates), 2000):
            batch = ap_updates[i:i + 2000]
            await conn.execute(text("UPDATE offer_cohorts SET airport_code = :ap WHERE cohort_id = :cid"), batch)
        print(f"5. Normalized airport codes across {len(ap_updates)} cohorts")

    # 6. Normalize board_basis across offer_cohorts & destination_code slugs
    async with engine.begin() as conn:
        raw_boards = [r[0] for r in (await conn.execute(text("SELECT DISTINCT board_basis FROM offer_cohorts"))).fetchall()]
        brd_cnt = 0
        for rb in raw_boards:
            nb = normalize_board_basis(rb)
            if rb != nb:
                res = await conn.execute(
                    text("UPDATE offer_cohorts SET board_basis = :nb WHERE board_basis IS NOT DISTINCT FROM :rb"),
                    {"nb": nb, "rb": rb},
                )
                brd_cnt += res.rowcount or 0
        # Canonicalize non-filter_ destination_codes like 'турция' -> 'turkey'
        await conn.execute(text("""
            UPDATE offer_cohorts
            SET destination_code = CASE
                WHEN LOWER(destination_code) IN ('турция','turkey') THEN 'turkey'
                WHEN LOWER(destination_code) IN ('египет','egypt') THEN 'egypt'
                WHEN LOWER(destination_code) IN ('греция','greece') THEN 'greece'
                WHEN LOWER(destination_code) IN ('кипр','cyprus') THEN 'cyprus'
                WHEN LOWER(destination_code) IN ('испания','spain') THEN 'spain'
                ELSE destination_code
            END
            WHERE LOWER(destination_code) IN ('турция','египет','греция','кипр','испания')
        """))
        print(f"6. Normalized board_basis on {brd_cnt} cohorts & localized destination_code slugs")

    # 7. Deduplicate identical (cohort_id, minute, total_price_pln) snapshots & align price_per_night_per_pax
    async with engine.begin() as conn:
        dedup_res = await conn.execute(text("""
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY cohort_id, DATE_TRUNC('minute', recorded_at), total_price_pln
                           ORDER BY id ASC
                       ) as rn
                FROM price_snapshots
            )
            DELETE FROM price_snapshots
            WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
        """))
        ppnp_res = await conn.execute(text("""
            UPDATE price_snapshots ps
            SET price_per_night_per_pax = ROUND(
                (ps.total_price_pln / GREATEST(1, oc.duration_nights * (oc.adults + oc.children)))::numeric,
                2
            )::double precision
            FROM offer_cohorts oc
            WHERE ps.cohort_id = oc.cohort_id
              AND ABS(
                  COALESCE(ps.price_per_night_per_pax, 0) -
                  (ps.total_price_pln / GREATEST(1, oc.duration_nights * (oc.adults + oc.children)))
              ) > 1.0
        """))
        print(f"7. Deduplicated {dedup_res.rowcount} identical-minute snapshots; recalculated ppnp on {ppnp_res.rowcount} rows")

    print("=== Sanitization Complete ===")


if __name__ == "__main__":
    asyncio.run(sanitize())
