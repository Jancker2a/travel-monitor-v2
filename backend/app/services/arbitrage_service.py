"""
Cross-border German Arbitrage Service for Travel Monitor 2.0.
Ported from v1 cross_border_arbitrage.py:
Compares departures from Berlin (BER) against Polish hubs (WAW, KTW, WRO, POZ)
to find price discrepancies and identify massive savings via German operators.
"""
import logging
import time
import json
import re
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models.cohort import OfferCohort
from app.models.price_snapshot import PriceSnapshot
from app.models.hotel import Hotel

logger = logging.getLogger("travel_monitor_2.arbitrage")

_ARBITRAGE_CACHE: Dict[float, Tuple[float, List[Dict[str, Any]]]] = {}
_CACHE_TTL_SECONDS = 600  # 10 minutes cache
_CHECK24_KB: Optional[Dict[str, Any]] = None


def get_check24_kb() -> Dict[str, Any]:
    global _CHECK24_KB
    if _CHECK24_KB is None:
        try:
            kb_path = Path(__file__).resolve().parents[1] / "knowledge" / "check24_offers_kb.json"
            if kb_path.exists():
                with open(kb_path, "r", encoding="utf-8") as f:
                    _CHECK24_KB = json.load(f)
            else:
                _CHECK24_KB = {}
        except Exception as e:
            logger.warning(f"Failed to load check24_offers_kb.json: {e}")
            _CHECK24_KB = {}
    return _CHECK24_KB


def find_check24_offer(name: str) -> Optional[Dict[str, Any]]:
    kb = get_check24_kb()
    if not kb or not name:
        return None
    c = name.lower().strip()
    if c in kb:
        return kb[c]
    tokens = set(re.findall(r"[a-z0-9]{3,}", c)) - {"hotel", "resort", "spa", "beach", "club", "palace"}
    best = None
    best_ov = 0
    for k, v in kb.items():
        kt = set(re.findall(r"[a-z0-9]{3,}", k)) - {"hotel", "resort", "spa", "beach", "club", "palace"}
        if tokens and kt:
            ov = len(tokens & kt)
            if ov >= 2 and ov > best_ov:
                best_ov = ov
                best = v
    return best


class ArbitrageService:
    @classmethod
    async def get_arbitrage_deals(
        cls, db: AsyncSession, min_savings_pln: float = 300.0, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Finds identical hotels and date windows where Berlin departures are significantly cheaper."""
        now_ts = time.time()
        if min_savings_pln in _ARBITRAGE_CACHE:
            c_time, c_deals = _ARBITRAGE_CACHE[min_savings_pln]
            if now_ts - c_time < _CACHE_TTL_SECONDS:
                return c_deals[:limit]

        # 1. Fetch only recent snapshots (last 14 days) to keep query ultra fast
        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False
        recent_cutoff = (
            datetime.now(timezone.utc) - timedelta(days=14)
            if is_pg
            else (datetime.utcnow() - timedelta(days=14)).isoformat()
        )

        join_col = "cohort_id"
        try:
            if db.bind and db.bind.dialect.name == "sqlite":
                from sqlalchemy import text
                pragma_res = await db.execute(text("PRAGMA table_info(price_snapshots)"))
                pragma_cols = {r[1] for r in pragma_res.fetchall()}
                if "cohort_hash" in pragma_cols:
                    join_col = "cohort_hash"
        except Exception:
            pass

        from sqlalchemy import text
        arb_sql = f"""
            SELECT 
                c.hotel_id,
                h.display_name,
                h.country,
                h.stars,
                h.main_image_url,
                c.airport_code,
                c.checkin_date,
                c.duration_nights,
                c.operator,
                c.offer_url,
                s.total_price_pln
            FROM offer_cohorts c
            JOIN hotels h ON c.hotel_id = h.hotel_id
            JOIN (
                SELECT 
                    {join_col} as cid,
                    total_price_pln,
                    ROW_NUMBER() OVER (PARTITION BY {join_col} ORDER BY recorded_at DESC) as rn
                FROM price_snapshots
                WHERE recorded_at >= :cutoff
            ) s ON c.{join_col} = s.cid AND s.rn = 1
        """
        res = await db.execute(text(arb_sql), {"cutoff": recent_cutoff})
        rows = res.fetchall()

        # Group by (hotel_id, checkin_date, duration_nights)
        grouped: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            hotel_id, name, country, stars, img, airport, checkin, nights, operator, offer_url, price = r
            if not checkin or price <= 0:
                continue

            airport_clean = str(airport or "").upper()
            is_berlin = "BER" in airport_clean or "BERLIN" in airport_clean

            key = f"{hotel_id}_{checkin}_{nights}"
            if key not in grouped:
                grouped[key] = {
                    "hotel_id": hotel_id,
                    "hotel_name": name,
                    "country": country,
                    "stars": stars or 4,
                    "main_image_url": img,
                    "checkin_date": checkin,
                    "duration_nights": nights,
                    "berlin_offers": [],
                    "polish_offers": [],
                }

            entry = {"airport": airport, "price_pln": price, "operator": operator, "offer_url": offer_url}
            if is_berlin:
                grouped[key]["berlin_offers"].append(entry)
            else:
                grouped[key]["polish_offers"].append(entry)

        deals: List[Dict[str, Any]] = []
        seen_hotels = set()

        # 1. Evaluate cohort-based matches (where database has direct Berlin departures)
        for key, g in grouped.items():
            if not g["berlin_offers"] or not g["polish_offers"]:
                continue

            cheapest_ber = min(g["berlin_offers"], key=lambda x: x["price_pln"])
            cheapest_pl = min(g["polish_offers"], key=lambda x: x["price_pln"])

            p_ber = cheapest_ber["price_pln"]
            p_pl = cheapest_pl["price_pln"]

            diff_pln = p_pl - p_ber
            if diff_pln >= min_savings_pln:
                savings_pct = (diff_pln / p_pl) * 100.0
                enc_h = urllib.parse.quote_plus(g['hotel_name'])
                ber_url = cheapest_ber.get("offer_url")
                if not ber_url:
                    c24 = find_check24_offer(g["hotel_name"])
                    ber_url = c24["offer_url"] if c24 else f"https://www.check24.de/suche/?q={enc_h}"
                pl_url = cheapest_pl.get("offer_url") or f"https://fly.pl/szukaj-wycieczek/?hotelName={enc_h}"
                deals.append({
                    "hotel_id": g["hotel_id"],
                    "hotel_name": g["hotel_name"],
                    "country": g["country"],
                    "stars": g["stars"],
                    "main_image_url": g["main_image_url"],
                    "checkin_date": g["checkin_date"],
                    "duration_nights": g["duration_nights"],
                    "berlin_airport": cheapest_ber["airport"] or "BER",
                    "berlin_price_pln": p_ber,
                    "berlin_operator": cheapest_ber["operator"] or "Exim / TUI",
                    "berlin_booking_url": ber_url,
                    "polish_airport": cheapest_pl["airport"] or "WAW",
                    "polish_price_pln": p_pl,
                    "polish_operator": cheapest_pl["operator"] or "PL Operator",
                    "polish_booking_url": pl_url,
                    "savings_pln": round(diff_pln, 0),
                    "savings_pct": round(savings_pct, 1),
                    "verdict": f"Выгода: {round(diff_pln):,} zł (-{savings_pct:.0f}%)",
                })
                seen_hotels.add(g["hotel_id"])

        # 2. Evaluate Check24 cross-border matches (Check24 specific offer URLs with hotelId)
        for key, g in grouped.items():
            if g["hotel_id"] in seen_hotels or not g["polish_offers"]:
                continue

            c24 = find_check24_offer(g["hotel_name"])
            if not c24 or not c24.get("price_pln") or c24["price_pln"] <= 0:
                continue

            cheapest_pl = min(g["polish_offers"], key=lambda x: x["price_pln"])
            p_pl = cheapest_pl["price_pln"]
            p_ber = c24["price_pln"]

            diff_pln = p_pl - p_ber
            if diff_pln >= min_savings_pln:
                savings_pct = (diff_pln / p_pl) * 100.0
                enc_h = urllib.parse.quote_plus(g["hotel_name"])
                pl_url = cheapest_pl.get("offer_url") or f"https://fly.pl/szukaj-wycieczek/?hotelName={enc_h}"
                deals.append({
                    "hotel_id": g["hotel_id"],
                    "hotel_name": g["hotel_name"],
                    "country": g["country"],
                    "stars": g["stars"],
                    "main_image_url": g["main_image_url"],
                    "checkin_date": g["checkin_date"],
                    "duration_nights": g["duration_nights"],
                    "berlin_airport": c24.get("departure_airport") or "BER",
                    "berlin_price_pln": p_ber,
                    "berlin_operator": c24.get("operator") or "Check24 / TUI Deutschland",
                    "berlin_booking_url": c24["offer_url"],
                    "polish_airport": cheapest_pl["airport"] or "WAW",
                    "polish_price_pln": p_pl,
                    "polish_operator": cheapest_pl["operator"] or "PL Operator",
                    "polish_booking_url": pl_url,
                    "savings_pln": round(diff_pln, 0),
                    "savings_pct": round(savings_pct, 1),
                    "verdict": f"Выгода: {round(diff_pln):,} zł (-{savings_pct:.0f}%)",
                })
                seen_hotels.add(g["hotel_id"])

        deals.sort(key=lambda x: x["savings_pln"], reverse=True)
        _ARBITRAGE_CACHE[min_savings_pln] = (now_ts, deals)
        return deals[:limit]

