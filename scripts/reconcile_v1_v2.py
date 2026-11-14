#!/usr/bin/env python3
"""
Reconciliation tool: compares the latest data from V1 (Git CSVs) with V2 (PostgreSQL catalog).
"""

import asyncio
import csv
import io
import os
import subprocess
import sys

# Ensure backend path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from app.database import AsyncSessionLocal
from app.services.catalog_service import CatalogService

V1_REPO_PATH = "/Users/andreiyankouski/travel-price-monitor"

FILTERS_TO_COMPARE = [
    ("filter_turkey_7_10_days", "Турция 7-10 дней (2 взр + 1 реб)"),
    ("filter_7_10_days", "Египет Марса/Хургада 7-10 дней (2 взр + 1 реб)"),
    ("filter_egypt_sharm_dec20_28_1p", "Египет Шарм 1 взр (Декабрь)"),
]

def normalize_name(name: str) -> str:
    return name.lower().replace("hotel", "").replace("resort", "").replace("spa", "").replace("&", "").replace("-", " ").strip()

async def reconcile_filter(db, filter_id: str, label: str):
    print(f"\n{'='*75}")
    print(f"📊 СВЕРКА ДАННЫХ: {label} [{filter_id}]")
    print(f"{'='*75}")

    # 1. Read V1 from Git
    try:
        cmd = ["git", "-C", V1_REPO_PATH, "show", f"origin/main:data/filters/{filter_id}/travel_prices.csv"]
        v1_raw = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
        v1_reader = csv.reader(io.StringIO(v1_raw))
        v1_rows = list(v1_reader)
    except Exception as e:
        print(f"❌ Не удалось прочитать V1 CSV: {e}")
        return

    timestamps = [r[10] for r in v1_rows if len(r) > 10 and r[10].startswith("2026")]
    latest_v1_ts = max(timestamps) if timestamps else "Н/Д"
    v1_latest = [r for r in v1_rows if len(r) > 10 and r[10] == latest_v1_ts]

    v1_dict = {}
    for r in v1_latest:
        name = r[0].strip()
        try:
            p = float(r[1])
        except (ValueError, TypeError):
            continue
        v1_dict[name] = {
            "price": p,
            "dates": r[2] if len(r) > 2 else "",
            "duration": r[3] if len(r) > 3 else "",
            "operator": r[9] if len(r) > 9 else "",
            "norm": normalize_name(name),
        }

    # 2. Read V2 from DB
    v2_data = await CatalogService.get_filter_hotels(db, filter_id, sort_by="price", order="asc")
    v2_hotels = v2_data.get("hotels", [])
    v2_updated_at = v2_data.get("last_updated_at", "Н/Д")

    v2_dict = {}
    for h in v2_hotels:
        name = h["display_name"].strip()
        v2_dict[name] = {
            "price": float(h["current_min_price"]),
            "deal_score": h.get("deal_score", 0),
            "dates": h.get("checkin_date", ""),
            "duration": f"{h.get('duration_nights', '')}n",
            "airport": h.get("departure_airport", ""),
            "operator": h.get("operator", ""),
            "norm": normalize_name(name),
        }

    print(f"🕒 Время последнего сбора V1: {latest_v1_ts}")
    print(f"🕒 Время последнего сбора V2: {v2_updated_at}")
    print(f"🏨 Всего отелей в каталоге: V1 = {len(v1_dict)} шт. | V2 = {len(v2_dict)} шт.")

    # Match hotels
    v1_sorted = sorted(v1_dict.items(), key=lambda x: x[1]["price"])
    v2_sorted = sorted(v2_dict.items(), key=lambda x: x[1]["price"])

    print("\n🔍 Топ-10 САМЫХ ДЕШЕВЫХ ПРЕДЛОЖЕНИЙ (Сравнение цен V1 vs V2):")
    print(f"{'Название отеля':<32} | {'Цена V1':>9} | {'Цена V2':>9} | {'Разница':>10} | {'Статус':<15}")
    print("-" * 85)

    exact_matches = 0
    price_diffs = 0
    missing_in_v2 = 0

    for name, v1_info in v1_sorted[:12]:
        p1 = v1_info["price"]
        # Try exact or normalized match in V2
        v2_info = v2_dict.get(name)
        if not v2_info:
            for v2_k, v2_v in v2_dict.items():
                if v2_v["norm"] == v1_info["norm"] or v1_info["norm"] in v2_v["norm"] or v2_v["norm"] in v1_info["norm"]:
                    v2_info = v2_v
                    break

        if v2_info:
            p2 = v2_info["price"]
            diff = p2 - p1
            if abs(diff) < 1.0:
                diff_str = "0 zł (100%)"
                status = "✅ Совпало"
                exact_matches += 1
            else:
                diff_str = f"{diff:+.0f} zł"
                status = "🔄 Изменилась" if abs(diff) < 200 else "⚠️ Дельта"
                price_diffs += 1
            print(f"{name[:32]:<32} | {p1:>7.0f} zł | {p2:>7.0f} zł | {diff_str:>10} | {status:<15}")
        else:
            missing_in_v2 += 1
            print(f"{name[:32]:<32} | {p1:>7.0f} zł | {'Н/Д':>9} | {'—':>10} | ❌ Нет в V2")

    # Check top 5 deal score in V2
    v2_by_score = sorted(v2_dict.items(), key=lambda x: x[1]["deal_score"], reverse=True)[:5]
    print("\n🔥 Топ-5 лучших предложений по Deal Score в V2:")
    for name, v2_info in v2_by_score:
        print(f"  • {name[:35]:<35} -> Deal Score: {v2_info['deal_score']:>2} | Цена: {v2_info['price']:.0f} zł")

async def main():
    async with AsyncSessionLocal() as db:
        for fid, label in FILTERS_TO_COMPARE:
            await reconcile_filter(db, fid, label)

if __name__ == "__main__":
    asyncio.run(main())

