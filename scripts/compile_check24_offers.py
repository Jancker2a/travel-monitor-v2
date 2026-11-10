#!/usr/bin/env python3
"""
Compile multi-filter Check24 German tour offers from V1 archives
into backend/app/knowledge/check24_offers_kb.json for Travel Monitor 2.0.
Preserves strict party composition (adults, children), exact hotel nights,
destination/country tag, and search date windows.
"""

import glob
import json
import os
import re
from pathlib import Path
from urllib.parse import unquote
import pandas as pd


def parse_travelers(url: str, text: str):
    s = unquote(str(url or "")) + " " + str(text or "")
    m_alloc = re.search(r"roomAllocation=([A-Za-z0-9\-,]+)", s)
    if m_alloc:
        alloc = m_alloc.group(1)
        tokens = [t for t in re.split(r"[,-]", alloc) if t]
        adults = sum(1 for t in tokens if t.upper() == "A")
        children = sum(1 for t in tokens if t.isdigit() or t.upper().startswith("C"))
        return adults, children
    m_pers = re.search(r"(\d+)\s*Pers", s, re.I)
    if m_pers:
        p = int(m_pers.group(1))
        return (p, 0) if p <= 2 else (2, p - 2)
    return 2, 0


def parse_nights(text: str):
    m_days = re.search(r"(\d+)\s*(?:Tage?|dni|days?)", str(text), re.I)
    if m_days:
        val = int(m_days.group(1))
        return max(1, val - 1)
    m_noc = re.search(r"(\d+)\s*(?:Nächte?|nocy)", str(text), re.I)
    if m_noc:
        return int(m_noc.group(1))
    return 7


def main():
    root_v1 = Path("/Users/andreiyankouski/travel-price-monitor/data/filters")
    out_path = Path("/Users/andreiyankouski/travel-monitor-v2/backend/app/knowledge/check24_offers_kb.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    dest_map = {
        "turkey": "Turkey",
        "egypt": "Egypt",
        "greece": "Greece",
        "cyprus": "Cyprus",
        "spain": "Spain",
    }

    offers = []
    by_hotel_latest = {}

    for csv_file in sorted(glob.glob(str(root_v1 / "*" / "germany_prices.csv"))):
        fdir = os.path.basename(os.path.dirname(csv_file))
        df = pd.read_csv(csv_file)
        raw_dest = str(df["destination"].iloc[0] if "destination" in df else "").strip()
        dest_str = "Turkey"
        if "cyprus" in fdir.lower():
            dest_str = "Cyprus"
        elif "greece" in fdir.lower():
            dest_str = "Greece"
        elif "egypt" in fdir.lower():
            dest_str = "Egypt"
        elif "turkey" in fdir.lower():
            dest_str = "Turkey"

        for _, row in df.iterrows():
            hname = str(row.get("hotel_name", "")).strip()
            if not hname or hname.startswith(("<<<", "===", ">>>")):
                continue
            try:
                price_eur = float(row.get("price", 0))
            except Exception:
                continue
            if price_eur <= 0:
                continue

            row_dest = str(row.get("destination", "")).strip()
            item_dest = dest_str
            if row_dest in ("Turkey", "Egypt", "Greece", "Cyprus", "Spain"):
                item_dest = row_dest
            elif "cyprus" in fdir.lower():
                item_dest = "Cyprus"

            url = str(row.get("offer_url", "")).strip()
            # Enforce strict specific offer URL: discard generic search pages or empty hotelId=
            if not url or "/suche/?q=" in url:
                continue
            if "check24" in url and not re.search(r"hotelId=\d+", url):
                continue
            dur = str(row.get("duration", "")).strip()
            dates = str(row.get("dates", "")).strip()
            ad, ch = parse_travelers(url, dur)
            nights = parse_nights(dur)

            dep_d = None
            ret_d = None
            m_dep = re.search(r"departureDate=(\d{4}-\d{2}-\d{2})", url)
            m_ret = re.search(r"returnDate=(\d{4}-\d{2}-\d{2})", url)
            if m_dep and m_ret:
                dep_d = m_dep.group(1)
                ret_d = m_ret.group(1)
            elif "_" in dates:
                p = dates.split("_")
                dep_d = p[0][:10]
                ret_d = p[1][:10] if len(p) > 1 else None

            price_pln = round(price_eur * 4.30, 0)

            rec = {
                "hotel_name": hname,
                "filter_id": fdir,
                "destination": item_dest,
                "departure_airport": "BER",
                "duration_nights": nights,
                "duration_label": dur,
                "adults": ad,
                "children": ch,
                "departure_date_start": dep_d,
                "departure_date_end": ret_d,
                "dates": dates,
                "price_eur": price_eur,
                "price_pln": price_pln,
                "operator": "Check24 / TUI Deutschland",
                "offer_url": url,
            }
            offers.append(rec)

            # Also maintain single-entry dictionary by lowercased hotel name for fallback lookups
            c_key = hname.lower().strip()
            if c_key not in by_hotel_latest or rec["price_pln"] < by_hotel_latest[c_key]["price_pln"]:
                by_hotel_latest[c_key] = rec

    payload = {
        "version": "2.0.0",
        "total_offers": len(offers),
        "offers": offers,
        "by_hotel": by_hotel_latest,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Successfully compiled {len(offers)} Check24 offers into {out_path}")
    print(f"Indexed {len(by_hotel_latest)} unique hotels")


if __name__ == "__main__":
    main()
