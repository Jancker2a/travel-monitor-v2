#!/usr/bin/env python3
"""
Normalize hotel countries and resort regions in Supabase PostgreSQL and SQLite.
Translates countries to canonical Russian ('Египет', 'Турция', 'Греция', 'Кипр', 'Испания')
and identifies correct resort regions from hotel names, slugs, and associated cohorts.
"""

import asyncio
import asyncpg
import sqlite3
from pathlib import Path

SUPABASE_URL = "postgresql://postgres.diwrmsoiyhxbfzwrtumi:5J4VB6%2BiU%25UkCZb@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
SQLITE_PATH = Path("/Users/andreiyankouski/travel-monitor-v2/travel_monitor_v2.db")

EGYPT_KW = [
    "sharm", "hurghada", "marsa", "makadi", "el gouna", "soma bay", "safaga",
    "dahab", "taba", "cairo", "luxor", "egipt", "egypt", "red sea"
]
TURKEY_KW = [
    "alanya", "kemer", "side", "belek", "bodrum", "marmaris", "fethiye", "kusadasi",
    "didim", "lara", "antalya", "tekirova", "beldibi", "goynuk", "konakli",
    "avsallar", "okurcalar", "incekum", "turunc", "icmeler", "turkey", "turcja"
]
GREECE_KW = [
    "crete", "rhodes", "kos", "corfu", "zakynthos", "chalkidiki", "chania",
    "heraklion", "rethymno", "hersonissos", "malia", "faliraki", "lindos",
    "kallithea", "ialyssos", "kolymbia", "mastichari", "kardamena", "tigaki",
    "greece", "grecja"
]
CYPRUS_KW = [
    "ayia napa", "protaras", "paphos", "larnaca", "limassol", "cyprus", "cypr"
]


def detect_country_and_region(name: str, hid: str, fids: list, curr_c: str, curr_r: str):
    name_l = (name or "").lower()
    hid_l = (hid or "").lower()
    text = f"{name_l} {hid_l}"

    country = None
    region = curr_r or ""

    # 1. Check Keywords
    for kw in EGYPT_KW:
        if kw in text:
            country = "Египет"
            if "sharm" in text: region = "Шарм-эль-Шейх"
            elif "hurghada" in text: region = "Хургада"
            elif "marsa" in text: region = "Марса-Алам"
            elif "makadi" in text: region = "Макади Бэй"
            elif "el gouna" in text: region = "Эль-Гуна"
            elif "soma bay" in text: region = "Сома Бэй"
            elif "safaga" in text: region = "Сафага"
            elif "dahab" in text: region = "Дахаб"
            elif "taba" in text: region = "Таба"
            break

    if not country:
        for kw in TURKEY_KW:
            if kw in text:
                country = "Турция"
                if any(x in text for x in ["alanya", "konakli", "avsallar", "okurcalar", "incekum"]): region = "Аланья"
                elif any(x in text for x in ["kemer", "tekirova", "beldibi", "goynuk"]): region = "Кемер"
                elif "side" in text: region = "Сиде"
                elif "belek" in text: region = "Белек"
                elif any(x in text for x in ["lara", "antalya"]): region = "Анталья"
                elif "bodrum" in text: region = "Бодрум"
                elif any(x in text for x in ["marmaris", "turunc", "icmeler"]): region = "Мармарис"
                elif "fethiye" in text: region = "Фетхие"
                elif "kusadasi" in text: region = "Кушадасы"
                elif "didim" in text: region = "Дидим"
                break

    if not country:
        for kw in GREECE_KW:
            if kw in text:
                country = "Греция"
                if any(x in text for x in ["crete", "chania", "heraklion", "rethymno", "hersonissos", "malia"]): region = "Крит"
                elif any(x in text for x in ["rhodes", "faliraki", "lindos", "kallithea", "ialyssos", "kolymbia"]): region = "Родос"
                elif any(x in text for x in ["kos", "mastichari", "kardamena", "tigaki"]): region = "Кос"
                elif "corfu" in text: region = "Корфу"
                elif "zakynthos" in text: region = "Закинф"
                break

    if not country:
        for kw in CYPRUS_KW:
            if kw in text:
                country = "Кипр"
                if "ayia napa" in text: region = "Айя-Напа"
                elif "protaras" in text: region = "Протарас"
                elif "paphos" in text: region = "Пафос"
                elif "larnaca" in text: region = "Ларнака"
                elif "limassol" in text: region = "Лимассол"
                break

    # 2. Check Associated Cohort Filters if country still not determined
    if not country and fids:
        fids_str = " ".join(str(f).lower() for f in fids)
        if any(x in fids_str for x in ["egypt", "7_10_days", "13_16_days", "sharm"]):
            country = "Египет"
        elif "turkey" in fids_str:
            country = "Турция"
        elif "greece" in fids_str:
            country = "Греция"
        elif "cyprus" in fids_str:
            country = "Кипр"

    # 3. Fallback translation of current country
    if not country:
        c_low = (curr_c or "").lower()
        if "turk" in c_low or "турц" in c_low: country = "Турция"
        elif "egypt" in c_low or "егип" in c_low: country = "Египет"
        elif "gree" in c_low or "грец" in c_low: country = "Греция"
        elif "cypr" in c_low or "кипр" in c_low: country = "Кипр"
        elif "spain" in c_low or "испан" in c_low: country = "Испания"
        else: country = curr_c or "Египет"

    return country, region


async def run_clean():
    print("Connecting to Supabase PostgreSQL...")
    conn = await asyncpg.connect(SUPABASE_URL)

    rows = await conn.fetch("""
        SELECT h.hotel_id, h.display_name, h.country, h.region, 
               COALESCE(ARRAY_AGG(DISTINCT oc.filter_id) FILTER (WHERE oc.filter_id IS NOT NULL), '{}') as fids
        FROM hotels h
        LEFT JOIN offer_cohorts oc ON h.hotel_id = oc.hotel_id
        GROUP BY h.hotel_id, h.display_name, h.country, h.region
    """)

    updates = []
    for r in rows:
        hid = r["hotel_id"]
        name = r["display_name"]
        curr_c = r["country"]
        curr_r = r["region"]
        fids = r["fids"]

        new_c, new_r = detect_country_and_region(name, hid, fids, curr_c, curr_r)
        if new_c != curr_c or new_r != curr_r:
            updates.append((new_c, new_r, hid))

    print(f"Applying {len(updates)} hotel country/region updates to Supabase PostgreSQL...")
    await conn.executemany("""
        UPDATE hotels 
        SET country = $1, region = $2
        WHERE hotel_id = $3
    """, updates)

    # Also update offer_cohorts destination_code where filter is egypt/turkey/greece/cyprus
    await conn.execute("""
        UPDATE offer_cohorts
        SET destination_code = 'egypt'
        WHERE (filter_id ILIKE '%egypt%' OR filter_id IN ('7_10_days', '13_16_days', 'filter_7_10_days', 'filter_13_16_days'))
          AND destination_code != 'egypt';
    """)
    await conn.execute("""
        UPDATE offer_cohorts
        SET destination_code = 'turkey'
        WHERE filter_id ILIKE '%turkey%'
          AND destination_code != 'turkey';
    """)
    await conn.execute("""
        UPDATE offer_cohorts
        SET destination_code = 'greece'
        WHERE filter_id ILIKE '%greece%'
          AND destination_code != 'greece';
    """)
    await conn.execute("""
        UPDATE offer_cohorts
        SET destination_code = 'cyprus'
        WHERE filter_id ILIKE '%cyprus%'
          AND destination_code != 'cyprus';
    """)
    print("✅ Supabase PostgreSQL updated successfully.")

    # Check updated stats
    stats = await conn.fetch("SELECT country, count(*) FROM hotels GROUP BY country ORDER BY count(*) DESC")
    print("\nUpdated country counts in Supabase:")
    for s in stats:
        print(f"  {s['country']}: {s['count']}")

    # Verify Jaz Sharm Dreams
    jaz = await conn.fetchrow("SELECT hotel_id, display_name, country, region FROM hotels WHERE hotel_id = 'jaz-sharm-dreams'")
    print(f"\nJaz Sharm Dreams verification: {dict(jaz) if jaz else 'Not found'}")

    await conn.close()

    # Also update local SQLite if exists
    if SQLITE_PATH.exists():
        print("\nUpdating local SQLite database...")
        s_conn = sqlite3.connect(SQLITE_PATH)
        s_cur = s_conn.cursor()
        s_cur.executemany("""
            UPDATE hotels SET country = ?, region = ? WHERE hotel_id = ?
        """, updates)
        s_conn.commit()
        s_conn.close()
        print("✅ Local SQLite updated successfully.")


if __name__ == "__main__":
    asyncio.run(run_clean())
