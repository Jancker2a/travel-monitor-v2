#!/usr/bin/env python3
"""
Normalize hotel countries and resort regions in Supabase PostgreSQL and SQLite.
Translates countries to canonical Russian ('Египет', 'Турция', 'Греция', 'Кипр', 'Испания')
and identifies correct resort regions from hotel names, slugs, and associated cohorts.
"""

import asyncio
import asyncpg
import sqlite3
import re
from pathlib import Path

PG_URL = (os.environ.get("DATABASE_URL") or "").replace("postgresql+asyncpg://", "postgresql://")
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
    "athens", "ateny", "attyka", "attica", "vravrona", "crete", "rhodes", "kos", "corfu",
    "zakynthos", "chalkidiki", "chania", "heraklion", "rethymno", "hersonissos", "malia",
    "faliraki", "lindos", "kallithea", "ialyssos", "kolymbia", "mastichari", "kardamena",
    "tigaki", "greece", "grecja", "olympic", "fix", "peloponnese"
]
CYPRUS_KW = [
    "ayia napa", "protaras", "paphos", "larnaca", "limassol", "cyprus", "cypr"
]


def has_kw(kw: str, text: str) -> bool:
    # Match as full word or token separated by spaces/hyphens/underscores
    return bool(re.search(rf"(?:^|[\s\-_]){re.escape(kw)}(?:$|[\s\-_])", text))


def detect_country_and_region(name: str, hid: str, fids: list, curr_c: str, curr_r: str):
    name_l = (name or "").lower()
    hid_l = (hid or "").lower()
    text = f" {name_l} {hid_l} "

    country = None
    region = curr_r or ""

    # Priority 0: Check Associated Cohort Filters first if they are specific
    fids_str = " ".join(str(f).lower() for f in fids) if fids else ""
    if "greece" in fids_str:
        country = "Греция"
    elif "cyprus" in fids_str:
        country = "Кипр"
    elif "turkey" in fids_str:
        country = "Турция"

    # Priority 1: Check Greece Keywords
    if not country:
        for kw in GREECE_KW:
            if has_kw(kw, text) or (len(kw) >= 5 and kw in text):
                country = "Греция"
                break

    # Priority 2: Check Egypt Keywords
    if not country:
        for kw in EGYPT_KW:
            if has_kw(kw, text) or (len(kw) >= 5 and kw in text):
                country = "Египет"
                break

    # Priority 3: Check Turkey Keywords
    if not country:
        for kw in TURKEY_KW:
            if has_kw(kw, text) or (len(kw) >= 5 and kw in text):
                country = "Турция"
                break

    # Priority 4: Check Cyprus Keywords
    if not country:
        for kw in CYPRUS_KW:
            if has_kw(kw, text) or (len(kw) >= 5 and kw in text):
                country = "Кипр"
                break

    # Fallback to fids
    if not country and fids_str:
        if any(x in fids_str for x in ["egypt", "filter_7_10_days", "filter_13_16_days", "sharm"]):
            country = "Египет"

    # Fallback to current country string
    if not country:
        c_low = (curr_c or "").lower()
        if "turk" in c_low or "турц" in c_low: country = "Турция"
        elif "egypt" in c_low or "егип" in c_low: country = "Египет"
        elif "gree" in c_low or "грец" in c_low: country = "Греция"
        elif "cypr" in c_low or "кипр" in c_low: country = "Кипр"
        elif "spain" in c_low or "испан" in c_low: country = "Испания"
        else: country = "Греция" if "greece" in fids_str else (curr_c or "Египет")

    # Region determination based on resolved country
    if country == "Греция":
        if any(has_kw(x, text) or x in text for x in ["athens", "ateny", "fix", "olympic"]):
            region = "Афины"
        elif any(has_kw(x, text) or x in text for x in ["attyka", "attica", "vravrona", "dolce"]):
            region = "Аттика"
        elif any(has_kw(x, text) or x in text for x in ["crete", "chania", "heraklion", "rethymno", "hersonissos", "malia"]):
            region = "Крит"
        elif any(has_kw(x, text) or x in text for x in ["rhodes", "faliraki", "lindos", "kallithea", "ialyssos", "kolymbia"]):
            region = "Родос"
        elif any(has_kw(x, text) or x in text for x in ["kos", "mastichari", "kardamena", "tigaki"]):
            region = "Кос"
        elif "corfu" in text:
            region = "Корфу"
        elif "zakynthos" in text:
            region = "Закинф"
        elif not region or region in ("Сиде", "Кемер", "Аланья", "Хургада", "Шарм-эль-Шейх"):
            region = "Афины"

    elif country == "Египет":
        if "sharm" in text: region = "Шарм-эль-Шейх"
        elif "hurghada" in text: region = "Хургада"
        elif "marsa" in text: region = "Марса-Алам"
        elif "makadi" in text: region = "Макади Бэй"
        elif "el gouna" in text: region = "Эль-Гуна"
        elif "soma bay" in text: region = "Сома Бэй"
        elif "safaga" in text: region = "Сафага"
        elif "dahab" in text: region = "Дахаб"
        elif "taba" in text: region = "Таба"
        elif not region: region = "Шарм-эль-Шейх"

    elif country == "Турция":
        if any(has_kw(x, text) or x in text for x in ["alanya", "konakli", "avsallar", "okurcalar", "incekum"]): region = "Аланья"
        elif any(has_kw(x, text) or x in text for x in ["kemer", "tekirova", "beldibi", "goynuk"]): region = "Кемер"
        elif has_kw("side", text): region = "Сиде"
        elif has_kw("belek", text): region = "Белек"
        elif any(has_kw(x, text) or x in text for x in ["lara", "antalya"]): region = "Анталья"
        elif has_kw("bodrum", text): region = "Бодрум"
        elif any(has_kw(x, text) or x in text for x in ["marmaris", "turunc", "icmeler"]): region = "Мармарис"
        elif has_kw("fethiye", text): region = "Фетхие"
        elif has_kw("kusadasi", text): region = "Кушадасы"
        elif has_kw("didim", text): region = "Дидим"
        elif not region or region in ("Афины", "Аттика", "Крит", "Родос"): region = "Анталья"

    elif country == "Кипр":
        if "ayia napa" in text: region = "Айя-Напа"
        elif "protaras" in text: region = "Протарас"
        elif "paphos" in text: region = "Пафос"
        elif "larnaca" in text: region = "Ларнака"
        elif "limassol" in text: region = "Лимассол"
        elif not region: region = "Пафос"

    return country, region


async def run_clean():
    print("Connecting to Supabase PostgreSQL...")
    conn = await asyncpg.connect(PG_URL)

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

    # Offer Cohorts synchronization
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

    # Verify Athens Hotels
    athens_hotels = await conn.fetch("""
        SELECT hotel_id, display_name, country, region 
        FROM hotels 
        WHERE hotel_id IN ('nlh-fix', 'zeus-wyndham-grand-athens', 'zeus-essence-wyndham-athens-residence', 'royal-olympic', 'zeus-dolce-athens-ex-hotel-dolce-attica-riviera-resort')
    """)
    print("\nAthens hotels verification:")
    for h in athens_hotels:
        print(f"  {h['display_name']} -> {h['country']} • {h['region']}")

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
