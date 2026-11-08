import asyncio
import json
import urllib.parse
from datetime import date
from typing import Dict, Any, List
import pandas as pd
from playwright.async_api import async_playwright

DESTINATIONS = [
    {"name": "Турция", "code": "39"},
    {"name": "Египет", "code": "11"},
    {"name": "Греция", "code": "14"},
    {"name": "Испания", "code": "18"},
]

DEPARTURE_AIRPORT = "Warszawa"

async def fetch_offers(page, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Query Fly.pl internal search API directly from page context."""
    query_str = urllib.parse.urlencode(params)
    api_url = f"https://fly.pl/api/fqs/v1/offers/search?{query_str}"
    
    data = await page.evaluate(f'''async () => {{
        try {{
            const resp = await fetch("{api_url}");
            if (!resp.ok) return null;
            return await resp.json();
        }} catch(e) {{
            return null;
        }}
    }}''')
    
    if not data or "data" not in data or "offers" not in data["data"]:
        return []
    return data["data"]["offers"]

async def run_study():
    print("🚀 Launching Fly.pl Empirical Study via Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        # Initialize session cookies
        await page.goto("https://fly.pl/szukaj-wycieczek/", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        results = []

        for dest in DESTINATIONS:
            print(f"\n=======================================================")
            print(f"🌍 Studying Destination: {dest['name']} (code {dest['code']})")
            print(f"=======================================================")
            
            # Base query params for 7 nights, June 2027 (Summer season)
            base_params = {
                "destinationLocation[0]": dest["code"],
                "departureLocation[0]": DEPARTURE_AIRPORT,
                "durationFrom": 7,
                "durationTo": 7,
                "offerTypes[0]": "accommodation_flight",
                "pager[group]": "objects",
                "pager[orderBy][0][direction]": "asc",
                "pager[orderBy][0][field]": "price",
                "pager[page]": 1,
                "pager[size]": 30,
                "priceType": "total",
                "totalPrice": 1,
            }

            # Config 1: 1 Adult (7 nights)
            params_1_adult = dict(base_params)
            params_1_adult["adults"] = 1
            offers_1_adult = await fetch_offers(page, params_1_adult)
            await asyncio.sleep(0.5)

            # Config 2: 2 Adults (7 nights)
            params_2_adults = dict(base_params)
            params_2_adults["adults"] = 2
            offers_2_adults = await fetch_offers(page, params_2_adults)
            await asyncio.sleep(0.5)

            # Config 3: 2 Adults + 1 Child (<12, age 7: born 2019-06-01)
            params_child_under_12 = dict(base_params)
            params_child_under_12["adults"] = 2
            params_child_under_12["children[0]"] = "2019-06-01"
            offers_child_u12 = await fetch_offers(page, params_child_under_12)
            await asyncio.sleep(0.5)

            # Config 4: 2 Adults + 1 Child (>12, age 14: born 2012-06-01)
            params_child_over_12 = dict(base_params)
            params_child_over_12["adults"] = 2
            params_child_over_12["children[0]"] = "2012-06-01"
            offers_child_o12 = await fetch_offers(page, params_child_over_12)
            await asyncio.sleep(0.5)

            # Config 5: 2 Adults (14 nights)
            params_14_nights = dict(base_params)
            params_14_nights["adults"] = 2
            params_14_nights["durationFrom"] = 14
            params_14_nights["durationTo"] = 14
            offers_14_nights = await fetch_offers(page, params_14_nights)
            await asyncio.sleep(0.5)

            # Build index by objectId / hotel name
            def to_dict(offers_list):
                res = {}
                for o in offers_list:
                    oid = o.get("objectId") or o.get("name")
                    if oid:
                        res[str(oid)] = {
                            "name": o.get("name"),
                            "total": float(o.get("total") or o.get("price") or 0),
                            "operator": o.get("operatorName") or o.get("operator"),
                            "dates": f"{o.get('departureDate', '')[:10]}",
                            "nights": o.get("nights", 7),
                        }
                return res

            map_1 = to_dict(offers_1_adult)
            map_2 = to_dict(offers_2_adults)
            map_u12 = to_dict(offers_child_u12)
            map_o12 = to_dict(offers_child_o12)
            map_14 = to_dict(offers_14_nights)

            print(f"Fetched counts: 1ad={len(map_1)}, 2ad={len(map_2)}, u12={len(map_u12)}, o12={len(map_o12)}, 14n={len(map_14)}")

            # Find matching hotels across configurations
            matched = 0
            for oid, o2 in map_2.items():
                p2 = o2["total"]
                if p2 <= 0:
                    continue

                p1 = map_1[oid]["total"] if oid in map_1 else None
                pu12 = map_u12[oid]["total"] if oid in map_u12 else None
                po12 = map_o12[oid]["total"] if oid in map_o12 else None
                p14 = map_14[oid]["total"] if oid in map_14 else None

                # We need at least 2 adults + either 1 adult or children to derive empirical laws
                if p1 or pu12 or po12 or p14:
                    item = {
                        "destination": dest["name"],
                        "hotel": o2["name"],
                        "operator": o2["operator"],
                        "departure_date": o2["dates"],
                        "p_1_adult": p1,
                        "p_2_adults": p2,
                        "p_2_plus_child_u12": pu12,
                        "p_2_plus_child_o12": po12,
                        "p_14_nights": p14,
                    }
                    results.append(item)
                    matched += 1

            print(f"Matched hotels with multi-configuration pricing in {dest['name']}: {matched}")

        await browser.close()

    # Convert to DataFrame for rigorous empirical econometric analysis
    df = pd.DataFrame(results)
    print(f"\n=======================================================")
    print(f"📈 EMPIRICAL DATASET: {len(df)} hotels successfully matched across focus groups")
    print(f"=======================================================")
    
    # Save raw dataset
    df.to_csv("scripts/focus_group_normalization_raw.csv", index=False)

    # 1. Single Supplement Analysis (1 adult vs 2 adults)
    df_single = df[df["p_1_adult"].notnull() & df["p_2_adults"].notnull()].copy()
    if not df_single.empty:
        df_single["adult_half_p2"] = df_single["p_2_adults"] / 2.0
        df_single["single_supplement_ratio"] = df_single["p_1_adult"] / df_single["adult_half_p2"]
        df_single["single_penalty_pct"] = (df_single["single_supplement_ratio"] - 1.0) * 100.0

        print("\n--- 1. SINGLE SUPPLEMENT (1 Взрослый vs 2 Взрослых) ---")
        print(f"Sample size: {len(df_single)} hotels")
        print(f"Средний штраф за 1 взрослого: +{df_single['single_penalty_pct'].mean():.1f}% к цене за человека в 2-местном номере")
        print(f"Медианный коэффициент: {df_single['single_supplement_ratio'].median():.2f}x (Мин: {df_single['single_supplement_ratio'].min():.2f}x, Макс: {df_single['single_supplement_ratio'].max():.2f}x)")
        print(df_single[["hotel", "destination", "p_1_adult", "p_2_adults", "single_supplement_ratio"]].head(6).to_string())

    # 2. Child under 12 Analysis (2 adults + child < 12 vs 2 adults)
    df_u12 = df[df["p_2_plus_child_u12"].notnull() & df["p_2_adults"].notnull()].copy()
    if not df_u12.empty:
        df_u12["adult_half_p2"] = df_u12["p_2_adults"] / 2.0
        df_u12["child_u12_delta"] = df_u12["p_2_plus_child_u12"] - df_u12["p_2_adults"]
        df_u12["child_u12_relative_weight"] = df_u12["child_u12_delta"] / df_u12["adult_half_p2"]

        print("\n--- 2. ДЕТИ ДО 12 ЛЕТ (2 Взр + 1 Реб < 12 vs 2 Взрослых) ---")
        print(f"Sample size: {len(df_u12)} hotels")
        print(f"Средняя доплата за ребенка <12 лет: {df_u12['child_u12_delta'].mean():.1f} zł")
        print(f"Медианная доплата: {df_u12['child_u12_delta'].median():.1f} zł")
        print(f"Средний вес ребенка к взрослому билету (W_child_u12): {df_u12['child_u12_relative_weight'].mean() * 100.0:.1f}%")
        print(f"Медианный вес: {df_u12['child_u12_relative_weight'].median() * 100.0:.1f}%")
        print(df_u12[["hotel", "destination", "p_2_adults", "p_2_plus_child_u12", "child_u12_delta", "child_u12_relative_weight"]].head(6).to_string())

    # 3. Child over 12 Analysis (2 adults + child > 12 vs 2 adults)
    df_o12 = df[df["p_2_plus_child_o12"].notnull() & df["p_2_adults"].notnull()].copy()
    if not df_o12.empty:
        df_o12["adult_half_p2"] = df_o12["p_2_adults"] / 2.0
        df_o12["child_o12_delta"] = df_o12["p_2_plus_child_o12"] - df_o12["p_2_adults"]
        df_o12["child_o12_relative_weight"] = df_o12["child_o12_delta"] / df_o12["adult_half_p2"]

        print("\n--- 3. ДЕТИ СТАРШЕ 12 ЛЕТ (2 Взр + 1 Реб > 12 vs 2 Взрослых) ---")
        print(f"Sample size: {len(df_o12)} hotels")
        print(f"Средняя доплата за подростка >12 лет: {df_o12['child_o12_delta'].mean():.1f} zł")
        print(f"Средний вес подростка к взрослому билету (W_child_o12): {df_o12['child_o12_relative_weight'].mean() * 100.0:.1f}%")
        print(df_o12[["hotel", "destination", "p_2_adults", "p_2_plus_child_o12", "child_o12_delta", "child_o12_relative_weight"]].head(6).to_string())

    # 4. Duration Scaling & Flight Benchmark Decomposition (7 nights vs 14 nights)
    df_dur = df[df["p_14_nights"].notnull() & df["p_2_adults"].notnull()].copy()
    if not df_dur.empty:
        # P_7 = 2*F + 7*H_room
        # P_14 = 2*F + 14*H_room
        # => H_room_daily = (P_14 - P_7) / 7
        # => 2*F = P_7 - 7*H_room = 2*P_7 - P_14
        # => F (per seat) = (2*P_7 - P_14) / 4
        df_dur["hotel_daily_room_rate"] = (df_dur["p_14_nights"] - df_dur["p_2_adults"]) / 7.0
        df_dur["implied_flight_cost_per_seat"] = (2.0 * df_dur["p_2_adults"] - df_dur["p_14_nights"]) / 4.0
        df_dur["duration_ratio_14_to_7"] = df_dur["p_14_nights"] / df_dur["p_2_adults"]

        print("\n--- 4. ДЛИТЕЛЬНОСТЬ И ДЕКОМПОЗИЦИЯ ПЕРЕЛЕТА (7 ночей vs 14 ночей) ---")
        print(f"Sample size: {len(df_dur)} hotels")
        print(f"Среднее отношение 14 ночей к 7 ночам: {df_dur['duration_ratio_14_to_7'].mean():.2f}x (не 2.0x, а значительно меньше из-за фикса перелета!)")
        print(f"Вычисленная средняя стоимость чартерного перелета (туда-обратно): {df_dur['implied_flight_cost_per_seat'].mean():.1f} zł/чел.")
        print(f"Медианная стоимость чартера: {df_dur['implied_flight_cost_per_seat'].median():.1f} zł/чел.")
        print(f"Средняя чистая стоимость отеля (номер/сутки): {df_dur['hotel_daily_room_rate'].mean():.1f} zł/сутки")
        print(df_dur[["hotel", "destination", "p_2_adults", "p_14_nights", "duration_ratio_14_to_7", "implied_flight_cost_per_seat", "hotel_daily_room_rate"]].head(6).to_string())

if __name__ == "__main__":
    asyncio.run(run_study())

