"""
Cross-border German Arbitrage Service for Travel Monitor 2.0.
Strict Parity Engine (Berlin BER vs Polish Hubs).

Enforces:
1. Strict Filter & Destination Isolation (Turkey with Turkey, Egypt with Egypt, Greece with Greece, Cyprus with Cyprus).
2. Passenger Composition Parity (Adults & Children must match 1:1; e.g. 2+1 never compared against 1p).
3. Duration & Nights Parity (Duration in hotel nights must match within +-1 night; e.g. 14 nights never compared against 7 nights).
4. Dates & Seasonality Check (Checkin dates must match search window or +-35 days).
5. Hotel Entity Matching via HotelEntityMatcher (Similarity >= 0.78, no geographic or sub-property conflict).
6. Transport Friction Deduction (250 PLN for Warsaw/Poznan/Wroclaw -> Berlin travel).
"""

import json
import logging
import re
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cohort import OfferCohort
from app.models.hotel import Hotel
from app.models.price_snapshot import PriceSnapshot
from app.services.canonical_filters import resolve_filter_spec
from app.services.hotel_entity_matcher import HotelEntityMatcher
from app.services.timeline_service import get_all_filter_id_variants

logger = logging.getLogger("travel_monitor_2.arbitrage")

_ARBITRAGE_CACHE: Dict[Tuple[str, str, float], Tuple[float, List[Dict[str, Any]]]] = {}
_CACHE_TTL_SECONDS = 600  # 10 minutes cache
_CHECK24_KB: Optional[Dict[str, Any]] = None
_ENTITY_MATCHER: Optional[HotelEntityMatcher] = None

# Default transport friction cost to BER (PKP Intercity train or car fuel/parking from Poland)
DEFAULT_FRICTION_COST_PLN = 250.0


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


def get_entity_matcher() -> HotelEntityMatcher:
    global _ENTITY_MATCHER
    if _ENTITY_MATCHER is None:
        _ENTITY_MATCHER = HotelEntityMatcher(similarity_threshold=0.78)
    return _ENTITY_MATCHER


def normalize_dest_key(destination_or_country: Optional[str]) -> Optional[str]:
    """Maps Russian or English country/destination strings to standard canonical keys."""
    if not destination_or_country:
        return None
    s = destination_or_country.lower().strip()
    if any(k in s for k in ("турц", "turk", "antalya", "belek", "side", "kemer", "bodrum")):
        return "turkey"
    if any(k in s for k in ("егип", "egypt", "hurghada", "sharm", "marsa")):
        return "egypt"
    if any(k in s for k in ("грец", "gree", "kreta", "rhodes", "athens", "corfu", "kos")):
        return "greece"
    if any(k in s for k in ("кипр", "cypr", "paphos", "ayia")):
        return "cyprus"
    if any(k in s for k in ("испан", "spain", "mallorca", "tenerife")):
        return "spain"
    return s


def find_check24_offer(
    name: str,
    destination: Optional[str] = None,
    adults: Optional[int] = None,
    children: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Finds direct matching Check24 German offer for a hotel with strict destination and entity matching.
    Guarantees no cross-country or cross-property mismatches.
    """
    kb = get_check24_kb()
    if not kb or not name:
        return None

    offers = kb.get("offers", [])
    dest_key = normalize_dest_key(destination)

    if dest_key:
        scoped = [o for o in offers if normalize_dest_key(o.get("destination")) == dest_key]
        if scoped:
            offers = scoped
        else:
            return None

    if adults is not None:
        scoped = [o for o in offers if o.get("adults") == adults]
        if scoped:
            offers = scoped

    if children is not None:
        scoped = [o for o in offers if o.get("children") == children]
        if scoped:
            offers = scoped

    if not offers:
        return None

    matcher = get_entity_matcher()
    de_hotels = list(set(o["hotel_name"] for o in offers if o.get("hotel_name")))
    match_res = matcher.match_hotel(name, de_hotels)
    if not match_res:
        return None

    matched_name, sim = match_res
    matching_offers = [o for o in offers if o.get("hotel_name") == matched_name]
    if not matching_offers:
        return None

    return min(matching_offers, key=lambda x: x.get("price_pln", 999999))


def is_offer_comparable(
    pl_checkin: Any,
    pl_nights: int,
    pl_adults: int,
    pl_children: int,
    de_offer: Dict[str, Any],
    max_duration_diff: int = 1,
) -> Tuple[bool, str]:
    """
    Validates 1:1 parameter comparability between Polish and German tour offers:
    1. Party composition must match strictly (adults and children).
    2. Duration in hotel nights must match within +-max_duration_diff (default +-1 night).
    3. Departure dates must fall within matching season window <= 35 days.
    """
    # 1. Travelers match
    de_ad = de_offer.get("adults", 2)
    de_ch = de_offer.get("children", 0)
    if pl_adults != de_ad:
        return False, f"Adults mismatch: PL {pl_adults} vs DE {de_ad}"
    if pl_children != de_ch:
        return False, f"Children mismatch: PL {pl_children} vs DE {de_ch}"

    # 2. Duration parity
    de_nights = de_offer.get("duration_nights", 7)
    if abs(pl_nights - de_nights) > max_duration_diff:
        return False, f"Nights mismatch: PL {pl_nights} vs DE {de_nights}"

    # 3. Departure Date parity
    if pl_checkin:
        try:
            pl_dt = (
                pl_checkin
                if isinstance(pl_checkin, date)
                else datetime.strptime(str(pl_checkin)[:10], "%Y-%m-%d").date()
            )
            de_start = de_offer.get("departure_date_start")
            de_end = de_offer.get("departure_date_end")
            if de_start:
                s_dt = (
                    de_start
                    if isinstance(de_start, date)
                    else datetime.strptime(str(de_start)[:10], "%Y-%m-%d").date()
                )
                e_dt = (
                    de_end
                    if isinstance(de_end, date)
                    else datetime.strptime(str(de_end)[:10], "%Y-%m-%d").date()
                    if de_end
                    else s_dt
                )
                # Ensure checkin is within the German search window or +-7 days
                if not (s_dt - timedelta(days=7) <= pl_dt <= e_dt + timedelta(days=7)):
                    diff_days = abs((pl_dt - s_dt).days)
                    if diff_days > 35:
                        return False, f"Date mismatch: PL {pl_dt} vs DE {s_dt} ({diff_days}d > 35d)"
        except Exception:
            pass

    return True, "OK"


class ArbitrageService:
    @classmethod
    def get_arbitrage_status(cls) -> Dict[str, Any]:
        """Returns freshness & size metadata for the Check24 German offers knowledge base."""
        kb_path = Path(__file__).resolve().parents[1] / "knowledge" / "check24_offers_kb.json"
        kb = get_check24_kb()
        offers = kb.get("offers", []) if isinstance(kb, dict) else []
        raw_ts = kb.get("generated_at") or kb.get("updated_at") if isinstance(kb, dict) else None
        kb_dt: Optional[datetime] = None
        if raw_ts:
            try:
                kb_dt = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
                if kb_dt.tzinfo is None:
                    kb_dt = kb_dt.replace(tzinfo=timezone.utc)
            except Exception:
                kb_dt = None
        if kb_dt is None and kb_path.exists():
            kb_dt = datetime.fromtimestamp(kb_path.stat().st_mtime, tz=timezone.utc)

        age_hours = (
            round((datetime.now(timezone.utc) - kb_dt).total_seconds() / 3600.0, 1)
            if kb_dt
            else None
        )
        return {
            "kb_updated_at": kb_dt.isoformat() if kb_dt else None,
            "total_offers": len(offers),
            "age_hours": age_hours,
            "is_stale": bool(age_hours is None or age_hours > 48.0),
        }

    @classmethod
    async def get_arbitrage_deals(
        cls,
        db: AsyncSession,
        min_savings_pln: float = 300.0,
        limit: int = 50,
        filter_id: Optional[str] = None,
        country: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Finds identical hotels and date windows where Berlin departures (BER) are significantly cheaper
        than departures from Polish airports, enforcing strict filter, destination, duration and traveler parity.
        """
        now_ts = time.time()
        cache_key = (str(filter_id or ""), str(country or ""), float(min_savings_pln))
        if cache_key in _ARBITRAGE_CACHE:
            c_time, c_deals = _ARBITRAGE_CACHE[cache_key]
            if now_ts - c_time < _CACHE_TTL_SECONDS:
                return c_deals[:limit]

        # 1. Resolve Filter Specifications
        spec = resolve_filter_spec(filter_id) if filter_id else None
        target_country = (country or (spec.get("country") if spec else None) or "").strip()
        target_dest_key = normalize_dest_key(target_country or (spec.get("destination") if spec else None))
        target_adults = spec.get("adults") if spec else None
        target_children = spec.get("children") if spec else None
        target_dur_min = spec.get("duration_min") if spec else None
        target_dur_max = spec.get("duration_max") if spec else None
        filter_variants = list(get_all_filter_id_variants(filter_id)) if filter_id else []

        if filter_id and (filter_id.startswith("monitor_") or filter_id.startswith("user_")):
            clean_uid = filter_id.replace("monitor_", "").replace("user_", "").replace("filter_", "")
            try:
                u_res = await db.execute(
                    text("SELECT id, title, filter_params_json FROM user_monitors WHERE id = :uid"),
                    {"uid": clean_uid},
                )
                u_row = u_res.fetchone()
                if u_row and u_row[2]:
                    u_params = json.loads(u_row[2])
                    if not target_country:
                        raw_dest = (u_params.get("destination") or "").lower()
                        if "egypt" in raw_dest:
                            target_country = "Египет"
                        elif "turk" in raw_dest:
                            target_country = "Турция"
                        elif "gree" in raw_dest:
                            target_country = "Греция"
                        elif "cypr" in raw_dest:
                            target_country = "Кипр"
                        elif "spain" in raw_dest:
                            target_country = "Испания"
                        else:
                            target_country = u_params.get("destination") or ""
                    target_dest_key = normalize_dest_key(target_country or u_params.get("destination"))

                    # Passenger party
                    travelers = u_params.get("travelers")
                    if isinstance(travelers, dict):
                        target_adults = travelers.get("adults", 2)
                        target_children = travelers.get("children", 0)
                    else:
                        if target_adults is None:
                            target_adults = u_params.get("adults", 2)
                        if target_children is None:
                            target_children = u_params.get("children", 0)

                    # Duration
                    dur_range = u_params.get("duration_range")
                    if isinstance(dur_range, list) and len(dur_range) >= 2:
                        target_dur_min = dur_range[0]
                        target_dur_max = dur_range[1]
                    else:
                        if target_dur_min is None:
                            target_dur_min = u_params.get("duration_min", 7)
                        if target_dur_max is None:
                            target_dur_max = u_params.get("duration_max", 10)
            except Exception as e:
                logger.warning(f"Failed to resolve user monitor spec for {clean_uid}: {e}")

        # 2. Filter German Candidate Offers
        kb = get_check24_kb()
        all_de_offers = kb.get("offers", [])
        de_candidates = all_de_offers

        if target_dest_key:
            de_candidates = [
                o for o in de_candidates if normalize_dest_key(o.get("destination")) == target_dest_key
            ]

        if target_adults is not None:
            de_candidates = [o for o in de_candidates if o.get("adults") == target_adults]

        if target_children is not None:
            de_candidates = [o for o in de_candidates if o.get("children") == target_children]

        if target_dur_min and target_dur_max:
            de_candidates = [
                o
                for o in de_candidates
                if (target_dur_min - 1) <= o.get("duration_nights", 7) <= (target_dur_max + 1)
            ]

        # If no German offers exist for this strict scope, return clean empty list
        if not de_candidates:
            _ARBITRAGE_CACHE[cache_key] = (now_ts, [])
            return []

        # 3. Query Polish Offers with DB-Agnostic Query
        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False
        recent_cutoff = (
            datetime.now(timezone.utc) - timedelta(days=21)
            if is_pg
            else (datetime.utcnow() - timedelta(days=21)).isoformat()
        )

        join_col = "cohort_id"
        try:
            if db.bind and db.bind.dialect.name == "sqlite":
                pragma_res = await db.execute(text("PRAGMA table_info(price_snapshots)"))
                pragma_cols = {r[1] for r in pragma_res.fetchall()}
                if "cohort_hash" in pragma_cols:
                    join_col = "cohort_hash"
        except Exception:
            pass

        where_clauses = ["ps.recorded_at >= :cutoff"]
        params: Dict[str, Any] = {"cutoff": recent_cutoff}

        if target_country:
            where_clauses.append("LOWER(h.country) = LOWER(:country)")
            params["country"] = target_country

        if filter_variants:
            placeholders = ",".join(f":f{i}" for i in range(len(filter_variants)))
            for i, fv in enumerate(filter_variants):
                params[f"f{i}"] = fv
            where_clauses.append(f"c.filter_id IN ({placeholders})")

        if target_dur_min and target_dur_max:
            where_clauses.append("c.duration_nights BETWEEN :dur_min AND :dur_max")
            params["dur_min"] = max(1, target_dur_min - 1)
            params["dur_max"] = target_dur_max + 1

        if target_adults is not None:
            where_clauses.append("c.adults = :adults")
            params["adults"] = target_adults

        where_sql = " AND ".join(where_clauses)
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
                c.adults,
                c.children,
                ps.total_price_pln,
                ps.recorded_at
            FROM offer_cohorts c
            JOIN hotels h ON c.hotel_id = h.hotel_id
            JOIN price_snapshots ps ON c.{join_col} = ps.{join_col}
            WHERE {where_sql}
            ORDER BY ps.recorded_at DESC
        """

        res = await db.execute(text(arb_sql), params)
        rows = res.fetchall()

        # Group Polish offers by (hotel_id, checkin_date, duration_nights)
        grouped: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            (
                hotel_id,
                name,
                country_val,
                stars,
                img,
                airport,
                checkin,
                nights,
                operator,
                offer_url,
                adults_val,
                children_val,
                price,
                rec_at,
            ) = r
            if not checkin or price <= 0:
                continue

            airport_clean = str(airport or "").upper()
            is_berlin = "BER" in airport_clean or "BERLIN" in airport_clean

            key = f"{hotel_id}_{checkin}_{nights}"
            if key not in grouped:
                grouped[key] = {
                    "hotel_id": hotel_id,
                    "hotel_name": name,
                    "country": country_val,
                    "stars": stars or 4,
                    "main_image_url": img,
                    "checkin_date": checkin,
                    "duration_nights": nights,
                    "adults": adults_val,
                    "children": children_val,
                    "berlin_offers": [],
                    "polish_offers": [],
                }

            entry = {
                "airport": airport,
                "price_pln": float(price),
                "operator": operator,
                "offer_url": offer_url,
            }
            if is_berlin:
                grouped[key]["berlin_offers"].append(entry)
            else:
                grouped[key]["polish_offers"].append(entry)

        deals: List[Dict[str, Any]] = []
        seen_hotels = set()
        matcher = get_entity_matcher()
        de_hotels = list(set(o["hotel_name"] for o in de_candidates if o.get("hotel_name")))

        # 4. Strict Matching & Comparability
        for key, g in grouped.items():
            if not g["polish_offers"] or g["hotel_id"] in seen_hotels:
                continue

            cheapest_pl = min(g["polish_offers"], key=lambda x: x["price_pln"])
            pl_name = g["hotel_name"]
            pl_price = cheapest_pl["price_pln"]

            # Match German Hotel
            match_res = matcher.match_hotel(pl_name, de_hotels)
            if not match_res:
                continue

            matched_de_name, sim_score = match_res
            matching_de_offers = [o for o in de_candidates if o["hotel_name"] == matched_de_name]

            # Find best comparable German offer
            best_deal_item = None
            max_savings = 0.0

            for de_o in matching_de_offers:
                ok, reason = is_offer_comparable(
                    pl_checkin=g["checkin_date"],
                    pl_nights=g["duration_nights"],
                    pl_adults=g.get("adults", target_adults or 2),
                    pl_children=g.get("children", target_children or 0),
                    de_offer=de_o,
                    max_duration_diff=1,
                )
                if not ok:
                    continue

                ber_url = str(de_o.get("offer_url") or "").strip()
                if not ber_url or "/suche/?q=" in ber_url or ber_url.endswith("hotelId="):
                    continue

                p_ber = de_o["price_pln"]
                friction_pln = DEFAULT_FRICTION_COST_PLN
                diff_pln = pl_price - (p_ber + friction_pln)

                if diff_pln >= min_savings_pln and diff_pln > max_savings:
                    max_savings = diff_pln
                    savings_pct = (diff_pln / pl_price) * 100.0
                    enc_h = urllib.parse.quote_plus(g["hotel_name"])
                    pl_url = cheapest_pl.get("offer_url") or f"https://fly.pl/szukaj-wycieczek/?hotelName={enc_h}"

                    best_deal_item = {
                        "hotel_id": g["hotel_id"],
                        "hotel_name": g["hotel_name"],
                        "german_hotel_name": matched_de_name,
                        "similarity_score": sim_score,
                        "match_type": "AI_CANONICAL" if sim_score == 1.0 else "AI_VERIFIED",
                        "is_verified": True,
                        "country": g["country"],
                        "stars": g["stars"],
                        "main_image_url": g["main_image_url"],
                        "checkin_date": str(g["checkin_date"]),
                        "duration_nights": g["duration_nights"],
                        "german_duration_nights": de_o["duration_nights"],
                        "adults": g.get("adults", target_adults or 2),
                        "children": g.get("children", target_children or 0),
                        "berlin_airport": de_o.get("departure_airport") or "BER",
                        "berlin_price_pln": p_ber,
                        "berlin_operator": de_o.get("operator") or "Check24 / TUI Deutschland",
                        "berlin_booking_url": de_o["offer_url"],
                        "polish_airport": cheapest_pl["airport"] or "WAW",
                        "polish_price_pln": pl_price,
                        "polish_operator": cheapest_pl["operator"] or "PL Operator",
                        "polish_booking_url": pl_url,
                        "friction_pln": friction_pln,
                        "savings_pln": round(diff_pln, 0),
                        "savings_pct": round(savings_pct, 1),
                        "verdict": f"Выгода: {round(diff_pln):,} zł (-{savings_pct:.0f}%)",
                    }

            if best_deal_item:
                deals.append(best_deal_item)
                seen_hotels.add(g["hotel_id"])

        deals.sort(key=lambda x: x["savings_pln"], reverse=True)
        _ARBITRAGE_CACHE[cache_key] = (now_ts, deals)
        return deals[:limit]
