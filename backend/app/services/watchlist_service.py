import uuid
import logging
import time
import re
import urllib.parse
from collections import defaultdict
from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple, Dict, Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, delete, text

from app.models.hotel import Hotel
from app.models.cohort import OfferCohort
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist import WatchlistItem
from app.schemas.watchlist import (
    WatchlistCreateRequest,
    WatchlistItemResponse,
    WatchlistListResponse,
    WatchlistAlertPayload,
)
from app.schemas.hotel import HotelPassportResponse, HotelHistoryPoint

logger = logging.getLogger("travel_monitor_2.watchlist")


_HOTEL_ALIAS_CACHE: Dict[str, List[str]] = {}
_ALIAS_CACHE_TS: float = 0.0
_ALIAS_CACHE_TTL: float = 3600.0  # 1 hour

COUNTRY_MAP = {
    "египет": "egypt",
    "турция": "turkey",
    "греция": "greece",
    "кипр": "cyprus",
    "испания": "spain",
    "болгария": "bulgaria",
}


def _norm_country(c: Optional[str]) -> str:
    if not c:
        return ""
    c_lower = c.strip().lower()
    return COUNTRY_MAP.get(c_lower, c_lower)


def _smart_hotel_tokens(title: str) -> str:
    # 1. Remove all parentheses
    n = re.sub(r"\s*\([^)]*\)", "", title)
    # 2. Remove country and common resort/city tokens
    n = re.sub(
        r"\b(?:turcja|egipt|grecja|cypr|hiszpania|turkey|egypt|greece|cyprus|spain|alanya|kemer|side|belek|antalya|sharm|hurghada|türkler|okurcalar|el|sheikh)\b",
        " ",
        n,
        flags=re.I,
    )
    n = re.sub(r"[^\w\s]", " ", n.lower())
    stop = {
        "hotel", "hotels", "resort", "resorts", "spa", "beach", "club",
        "palace", "deluxe", "aqua", "park", "the", "and", "di", "ex"
    }
    tokens = [t for t in n.split() if len(t) > 1 and t not in stop]
    return " ".join(sorted(tokens)) if tokens else title.strip().lower()


class WatchlistService:

    @classmethod
    async def add_to_watchlist(
        cls, db: AsyncSession, req: WatchlistCreateRequest
    ) -> WatchlistItemResponse:
        # 1. Verify Cohort exists
        c_stmt = (
            select(OfferCohort, Hotel)
            .join(Hotel, OfferCohort.hotel_id == Hotel.hotel_id)
            .where(OfferCohort.cohort_hash == req.cohort_hash)
        )
        c_res = await db.execute(c_stmt)
        row = c_res.first()
        if not row:
            raise HTTPException(status_code=404, detail="Offer cohort not found")

        cohort, hotel = row[0], row[1]

        # 2. Check if already watched by this user
        w_stmt = select(WatchlistItem).where(
            and_(
                WatchlistItem.user_chat_id == req.user_chat_id,
                WatchlistItem.cohort_hash == req.cohort_hash,
            )
        )
        w_res = await db.execute(w_stmt)
        existing_item = w_res.scalar_one_or_none()

        if existing_item:
            existing_item.target_price_pln = req.target_price_pln
            existing_item.notify_any_drop = req.notify_any_drop
            watch_item = existing_item
        else:
            watch_id = f"w_{uuid.uuid4().hex[:10]}"
            watch_item = WatchlistItem(
                watch_id=watch_id,
                user_chat_id=req.user_chat_id,
                cohort_hash=req.cohort_hash,
                target_price_pln=req.target_price_pln,
                notify_any_drop=req.notify_any_drop,
                created_at=datetime.utcnow(),
            )
            db.add(watch_item)

        await db.commit()
        await db.refresh(watch_item)

        # 3. Retrieve latest snapshot
        snap_stmt = (
            select(PriceSnapshot)
            .where(PriceSnapshot.cohort_id == cohort.cohort_id)
            .order_by(PriceSnapshot.recorded_at.desc())
            .limit(1)
        )
        snap = (await db.execute(snap_stmt)).scalar_one_or_none()
        latest_price = snap.total_price_pln if snap else 0.0

        target_reached = False
        if req.target_price_pln is not None and latest_price <= req.target_price_pln:
            target_reached = True

        checkin_d = (
            datetime.strptime(cohort.checkin_date, "%Y-%m-%d").date()
            if isinstance(cohort.checkin_date, str) and "-" in cohort.checkin_date
            else datetime.utcnow().date()
        )

        return WatchlistItemResponse(
            watch_id=watch_item.watch_id,
            user_chat_id=watch_item.user_chat_id,
            cohort_hash=watch_item.cohort_hash,
            hotel_id=hotel.hotel_id,
            hotel_name=hotel.display_name,
            country=hotel.country,
            departure_date=checkin_d,
            duration_nights=cohort.duration_nights,
            airport=cohort.airport_code,
            target_price_pln=watch_item.target_price_pln,
            latest_price_pln=latest_price,
            deal_score=85,
            deal_badge="WATCHING",
            hopper_verdict="BUY NOW" if target_reached else "WAIT",
            target_reached=target_reached,
            booking_url=cohort.offer_url,
            created_at=watch_item.created_at,
            last_notified_at=watch_item.last_notified_at,
        )

    @classmethod
    async def get_user_watchlist(
        cls, db: AsyncSession, user_chat_id: str
    ) -> WatchlistListResponse:
        stmt = (
            select(WatchlistItem, OfferCohort, Hotel)
            .join(OfferCohort, WatchlistItem.cohort_hash == OfferCohort.cohort_hash)
            .join(Hotel, OfferCohort.hotel_id == Hotel.hotel_id)
            .where(WatchlistItem.user_chat_id == user_chat_id)
            .order_by(WatchlistItem.created_at.desc())
        )
        res = await db.execute(stmt)
        rows = res.all()

        items: List[WatchlistItemResponse] = []
        for watch_item, cohort, hotel in rows:
            snap_stmt = (
                select(PriceSnapshot)
                .where(PriceSnapshot.cohort_id == cohort.cohort_id)
                .order_by(PriceSnapshot.recorded_at.desc())
                .limit(1)
            )
            snap = (await db.execute(snap_stmt)).scalar_one_or_none()
            latest_price = snap.total_price_pln if snap else 0.0

            target_reached = False
            if watch_item.target_price_pln and latest_price <= watch_item.target_price_pln:
                target_reached = True

            checkin_d = (
                datetime.strptime(cohort.checkin_date, "%Y-%m-%d").date()
                if isinstance(cohort.checkin_date, str) and "-" in cohort.checkin_date
                else datetime.utcnow().date()
            )

            items.append(
                WatchlistItemResponse(
                    watch_id=watch_item.watch_id,
                    user_chat_id=watch_item.user_chat_id,
                    cohort_hash=cohort.cohort_hash,
                    hotel_id=hotel.hotel_id,
                    hotel_name=hotel.display_name,
                    country=hotel.country,
                    departure_date=checkin_d,
                    duration_nights=cohort.duration_nights,
                    airport=cohort.airport_code,
                    target_price_pln=watch_item.target_price_pln,
                    latest_price_pln=latest_price,
                    deal_score=90 if target_reached else 70,
                    deal_badge="SUPER_DEAL" if target_reached else "WATCHING",
                    hopper_verdict="BUY NOW" if target_reached else "WAIT",
                    target_reached=target_reached,
                    booking_url=cohort.offer_url,
                    created_at=watch_item.created_at,
                    last_notified_at=watch_item.last_notified_at,
                )
            )

        return WatchlistListResponse(total=len(items), items=items)

    @classmethod
    async def delete_watchlist_item(
        cls, db: AsyncSession, watch_id: str, user_chat_id: Optional[str] = None
    ) -> bool:
        stmt = delete(WatchlistItem).where(WatchlistItem.watch_id == watch_id)
        if user_chat_id:
            stmt = stmt.where(WatchlistItem.user_chat_id == user_chat_id)

        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount > 0

    @classmethod
    async def check_watchlist_triggers(
        cls, db: AsyncSession
    ) -> List[WatchlistAlertPayload]:
        """Scans all active watchlists and evaluates price drops and target hits."""
        stmt = (
            select(WatchlistItem, OfferCohort, Hotel)
            .join(OfferCohort, WatchlistItem.cohort_hash == OfferCohort.cohort_hash)
            .join(Hotel, OfferCohort.hotel_id == Hotel.hotel_id)
        )
        res = await db.execute(stmt)
        rows = res.all()

        alerts: List[WatchlistAlertPayload] = []
        now_dt = datetime.utcnow()

        for watch_item, cohort, hotel in rows:
            # Get last 2 snapshots
            snap_stmt = (
                select(PriceSnapshot)
                .where(PriceSnapshot.cohort_id == cohort.cohort_id)
                .order_by(PriceSnapshot.recorded_at.desc())
                .limit(2)
            )
            snaps = (await db.execute(snap_stmt)).scalars().all()
            if not snaps:
                continue

            curr_price = snaps[0].total_price_pln
            prev_price = snaps[1].total_price_pln if len(snaps) > 1 else curr_price

            drop_amount = prev_price - curr_price
            drop_pct = (drop_amount / prev_price * 100) if prev_price > 0 else 0.0

            target_reached = False
            if watch_item.target_price_pln and curr_price <= watch_item.target_price_pln:
                target_reached = True

            should_alert = False
            if target_reached:
                should_alert = True
            elif watch_item.notify_any_drop and drop_amount >= 50.0:  # significant drop >= 50 PLN
                should_alert = True

            if should_alert:
                msg = (
                    f"🔔 <b>Снижение цены по вашему Watchlist!</b>\n\n"
                    f"🏨 <b>{hotel.display_name}</b> ({hotel.country})\n"
                    f"📅 Вылет: <code>{cohort.checkin_date}</code> ({cohort.duration_nights} ночей)\n"
                    f"🛫 Аэропорт: <code>{cohort.airport_code}</code>\n\n"
                    f"💰 Новая цена: <b>{curr_price:.0f} PLN</b> (было: {prev_price:.0f} PLN, -{drop_amount:.0f} PLN / -{drop_pct:.1f}%)\n"
                )
                if target_reached:
                    msg += f"🎯 <b>Целевая цена ({watch_item.target_price_pln:.0f} PLN) достигнута!</b> Рекомендуем бронировать сейчас.\n"
                if cohort.offer_url:
                    msg += f"\n🔗 <a href='{cohort.offer_url}'>Забронировать тур на Fly.pl</a>"

                alerts.append(
                    WatchlistAlertPayload(
                        watch_id=watch_item.watch_id,
                        user_chat_id=watch_item.user_chat_id,
                        hotel_name=hotel.display_name,
                        country=hotel.country,
                        previous_price_pln=prev_price,
                        current_price_pln=curr_price,
                        drop_amount_pln=round(drop_amount, 2),
                        drop_pct=round(drop_pct, 1),
                        target_reached=target_reached,
                        target_price_pln=watch_item.target_price_pln,
                        booking_url=cohort.offer_url,
                        message_text=msg,
                    )
                )

                watch_item.last_notified_at = now_dt

        await db.commit()
        return alerts

    @classmethod
    async def _find_related_hotel_ids(cls, db: AsyncSession, hotel: Hotel) -> List[str]:
        """
        Finds all hotel_ids that refer to the same physical property,
        handling tour operator renames, (ex. ...) additions, regional tags, and trailing 'Hotel/Resort' variations.
        Uses in-memory cluster caching for <0.1ms lookups.
        """
        global _HOTEL_ALIAS_CACHE, _ALIAS_CACHE_TS
        now = time.time()
        if _HOTEL_ALIAS_CACHE and (now - _ALIAS_CACHE_TS < _ALIAS_CACHE_TTL):
            return _HOTEL_ALIAS_CACHE.get(hotel.hotel_id, [hotel.hotel_id])

        # Rebuild alias clusters across all hotels
        stmt = select(Hotel.hotel_id, Hotel.display_name, Hotel.country)
        rows = (await db.execute(stmt)).all()

        clusters = defaultdict(list)
        new_cache: Dict[str, List[str]] = {}
        for hid, name, c_raw in rows:
            new_cache[hid] = [hid]
            c = _norm_country(c_raw)
            toks = _smart_hotel_tokens(name)
            if toks:
                key = (c, toks)
                clusters[key].append(hid)

        for key, hids in clusters.items():
            if len(hids) > 1:
                for hid in hids:
                    new_cache[hid] = hids

        _HOTEL_ALIAS_CACHE = new_cache
        _ALIAS_CACHE_TS = now
        return _HOTEL_ALIAS_CACHE.get(hotel.hotel_id, [hotel.hotel_id])

    @classmethod
    async def get_hotel_passport(
        cls, db: AsyncSession, hotel_id: str, filter_id: Optional[str] = None
    ) -> HotelPassportResponse:
        from app.services.hotel_knowledge_service import HotelKnowledgeService
        from app.services.canonical_filters import resolve_filter_spec

        # 1. Fetch Hotel
        h_stmt = select(Hotel).where(Hotel.hotel_id == hotel_id)
        hotel = (await db.execute(h_stmt)).scalar_one_or_none()
        if not hotel:
            raise HTTPException(status_code=404, detail="Hotel not found")

        # Resolve related hotel_ids (canonical hotel, aliases, renames)
        related_hotel_ids = await cls._find_related_hotel_ids(db, hotel)

        # 2. Fetch all cohorts for this hotel and related aliases (DB-agnostic: detect if price_snapshots uses cohort_hash or cohort_id)
        from types import SimpleNamespace
        join_col = "cohort_id"
        try:
            if db.bind and db.bind.dialect.name == "sqlite":
                pragma_res = await db.execute(text("PRAGMA table_info(price_snapshots)"))
                pragma_cols = {r[1] for r in pragma_res.fetchall()}
                if "cohort_hash" in pragma_cols:
                    join_col = "cohort_hash"
        except Exception:
            pass

        placeholders = ",".join(f":h{i}" for i in range(len(related_hotel_ids)))
        h_params = {f"h{i}": hid for i, hid in enumerate(related_hotel_ids)}

        cohort_sql = f"""
            SELECT 
                {join_col} as cid,
                cohort_hash,
                filter_id,
                hotel_id,
                destination_code,
                checkin_date,
                checkout_date,
                duration_nights,
                airport_code,
                board_basis,
                room_type,
                adults,
                children,
                operator,
                offer_url
            FROM offer_cohorts
            WHERE hotel_id IN ({placeholders})
        """
        c_rows = (await db.execute(text(cohort_sql), h_params)).fetchall()
        all_cohorts = [
            SimpleNamespace(
                cohort_id=r[0],
                cohort_hash=r[1],
                filter_id=r[2],
                hotel_id=r[3],
                destination_code=r[4],
                checkin_date=str(r[5]) if r[5] else "",
                checkout_date=str(r[6]) if r[6] else "",
                duration_nights=int(r[7]) if r[7] else 7,
                airport_code=r[8] or "WAW",
                board_basis=r[9] or "All Inclusive",
                room_type=r[10] or "Standard",
                adults=int(r[11]) if r[11] else 2,
                children=int(r[12]) if r[12] else 0,
                operator=r[13] or "Touroperator",
                offer_url=r[14] or "",
            )
            for r in c_rows
        ]
        if not all_cohorts:
            raise HTTPException(status_code=404, detail="No cohorts found for this hotel")

        # 3. Determine scoped cohorts for the active filter to ensure a clean, smooth, non-oscillating curve
        from app.services.timeline_service import resolve_filter_id, get_all_filter_id_variants
        canonical_fid = resolve_filter_id(filter_id) if filter_id else None
        filter_variants = set(get_all_filter_id_variants(filter_id)) if filter_id else set()
        scoped_cohorts = []
        if filter_variants:
            scoped_cohorts = [c for c in all_cohorts if c.filter_id in filter_variants]

        if not scoped_cohorts:
            spec = resolve_filter_spec(filter_id)
            if spec:
                dest_codes = set(spec.get("destination_codes", []))
                scoped_cohorts = [c for c in all_cohorts if c.destination_code in dest_codes]
                if not scoped_cohorts:
                    # Fallback to party composition
                    scoped_cohorts = [c for c in all_cohorts if c.adults == spec.get("adults", 2) and c.children == spec.get("children", 1)]

        # If still no scoped cohorts or no filter_id provided, pick the dominant party composition
        # to NEVER mix 1-adult and 2+1 family cohorts together into one price curve!
        if not scoped_cohorts:
            from collections import Counter
            party_counter = Counter([(c.adults, c.children) for c in all_cohorts])
            top_party = party_counter.most_common(1)[0][0] if party_counter else (2, 1)
            dest_counter = Counter([c.destination_code for c in all_cohorts if (c.adults, c.children) == top_party])
            top_dest = dest_counter.most_common(1)[0][0] if dest_counter else None
            scoped_cohorts = [
                c for c in all_cohorts 
                if (c.adults, c.children) == top_party and (not top_dest or c.destination_code == top_dest)
            ]

        scoped_cohort_ids = {c.cohort_id for c in scoped_cohorts}
        cohort_by_id = {c.cohort_id: c for c in all_cohorts}

        # 4. Fetch all snapshots for all cohorts (to populate packages_map and history)
        all_cohort_ids = [c.cohort_id for c in all_cohorts]
        c_placeholders = ",".join(f":c{i}" for i in range(len(all_cohort_ids)))
        c_params = {f"c{i}": cid for i, cid in enumerate(all_cohort_ids)}

        # 4b. Find all other monitored filters where this hotel has recorded price snapshots
        from app.services.canonical_filters import CANONICAL_FILTERS
        other_filters_sql = f"""
            SELECT 
                oc.filter_id,
                MIN(ps.total_price_pln) as min_p,
                MAX(ps.total_price_pln) as max_p,
                MAX(ps.recorded_at) as last_seen,
                COUNT(ps.id) as snaps_count,
                MAX(oc.adults) as adults,
                MAX(oc.children) as children,
                MAX(oc.duration_nights) as nights
            FROM offer_cohorts oc
            JOIN price_snapshots ps ON oc.{join_col} = ps.{join_col}
            WHERE oc.hotel_id IN ({placeholders})
              AND oc.filter_id IS NOT NULL
              AND oc.filter_id != ''
            GROUP BY oc.filter_id
            ORDER BY snaps_count DESC
        """
        other_filters = []
        try:
            of_res = await db.execute(text(other_filters_sql), h_params)
            for r in of_res.fetchall():
                f_id = r[0]
                if not f_id:
                    continue
                min_val = float(r[1]) if r[1] else 0.0
                max_val = float(r[2]) if r[2] else 0.0
                last_dt = r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]) if r[3] else ""
                cnt = int(r[4])
                ad = int(r[5]) if r[5] else 2
                ch = int(r[6]) if r[6] else 0
                dur = int(r[7]) if r[7] else 7

                spec = CANONICAL_FILTERS.get(f_id, {})
                f_title = spec.get("title")
                if not f_title:
                    clean_name = f_id.replace("filter_", "").replace("_days", "").replace("_", " ").title()
                    f_title = f"Фильтр {clean_name}"

                party_str = f"{ad} взр" + (f" + {ch} реб" if ch else "") if ad else "Стандарт"

                other_filters.append({
                    "filter_id": f_id,
                    "title": f_title,
                    "min_price_pln": round(min_val, 1),
                    "max_price_pln": round(max_val, 1),
                    "last_seen": last_dt,
                    "snaps_count": cnt,
                    "adults": ad,
                    "children": ch,
                    "party_str": party_str,
                    "duration_nights": dur,
                })
        except Exception as of_err:
            logger.warning(f"Failed to query other_filters for {hotel_id}: {of_err}")

        snap_sql = f"""
            SELECT 
                {join_col} as cid,
                recorded_at,
                total_price_pln,
                price_per_night_per_pax
            FROM price_snapshots
            WHERE {join_col} IN ({c_placeholders})
            ORDER BY recorded_at ASC
        """
        s_rows = (await db.execute(text(snap_sql), c_params)).fetchall()
        snap_rows = [
            SimpleNamespace(
                cohort_id=r[0],
                recorded_at=r[1],
                total_price_pln=float(r[2]),
                price_per_night_per_pax=float(r[3]) if r[3] else float(r[2]) / 14.0,
            )
            for r in s_rows
        ]

        packages_map: Dict[str, Dict[str, Any]] = {}
        # Keep latest snapshot for each cohort package
        for snap in snap_rows:
            cohort = cohort_by_id.get(snap.cohort_id)
            if not cohort:
                continue
            checkin_d = (
                datetime.strptime(cohort.checkin_date, "%Y-%m-%d").date()
                if isinstance(cohort.checkin_date, str) and "-" in cohort.checkin_date
                else datetime.utcnow().date()
            )
            checkout_d = checkin_d + timedelta(days=cohort.duration_nights or 7)
            # Deduplicate by unique travel flight combination (departure date, duration, airport)
            # keeping the cheapest live price for each slot
            today_date = datetime.utcnow().date()
            if checkin_d < today_date:
                continue

            dedup_key = f"{checkin_d}_{cohort.duration_nights}_{cohort.airport_code}"
            if dedup_key not in packages_map or snap.total_price_pln < packages_map[dedup_key]["total_price_pln"]:
                packages_map[dedup_key] = {
                    "cohort_hash": cohort.cohort_hash,
                    "destination_code": cohort.destination_code,
                    "airport": cohort.airport_code,
                    "airport_code": cohort.airport_code,
                    "departure_date": str(checkin_d),
                    "checkin_date": str(checkin_d),
                    "checkout_date": str(checkout_d),
                    "duration_nights": cohort.duration_nights,
                    "adults": cohort.adults,
                    "children": cohort.children,
                    "total_price_pln": snap.total_price_pln,
                    "price_per_night_pax": round(snap.price_per_night_per_pax, 1),
                    "operator": cohort.operator or "Touroperator",
                    "booking_url": cohort.offer_url or f"https://fly.pl/szukaj-wycieczek/?hotelName={hotel.display_name.replace(' ', '+')}",
                }

        # 5. Build clean, non-oscillating history points for scoped cohorts
        # Group snapshots by hourly bucket and take MIN price per bucket
        hourly_map: Dict[str, Dict[str, Any]] = {}
        for snap in snap_rows:
            if snap.cohort_id not in scoped_cohort_ids:
                continue
            rec_dt = (
                datetime.fromisoformat(snap.recorded_at)
                if isinstance(snap.recorded_at, str)
                else snap.recorded_at or datetime.utcnow()
            )
            bucket_key = rec_dt.strftime("%Y-%m-%d %H:00")
            cohort = cohort_by_id[snap.cohort_id]
            checkin_d = (
                datetime.strptime(cohort.checkin_date, "%Y-%m-%d").date()
                if isinstance(cohort.checkin_date, str) and "-" in cohort.checkin_date
                else datetime.utcnow().date()
            )
            if bucket_key not in hourly_map or snap.total_price_pln < hourly_map[bucket_key]["price"]:
                hourly_map[bucket_key] = {
                    "recorded_at": rec_dt,
                    "price": snap.total_price_pln,
                    "price_per_night_pax": snap.price_per_night_per_pax,
                    "departure_date": checkin_d,
                    "duration_nights": cohort.duration_nights,
                    "airport": cohort.airport_code,
                    "adults": cohort.adults,
                    "children": cohort.children,
                }

        from app.services.cost_decomposer import CostDecomposer

        sorted_buckets = sorted(hourly_map.keys())
        history_points: List[HotelHistoryPoint] = []
        prices: List[float] = []

        dest_lower = (hotel.country or "turkey").lower()
        single_factor = 1.18 if "turk" in dest_lower else 1.20

        for b_key in sorted_buckets:
            item = hourly_map[b_key]
            prices.append(item["price"])

            pt_adults = item.get("adults") or 2
            pt_children = item.get("children") or 0
            pt_nights = max(1, item.get("duration_nights") or 8)
            decomp = CostDecomposer.decompose(
                total_price_pln=item["price"],
                duration_nights=pt_nights,
                adults=pt_adults,
                children=pt_children,
                destination=hotel.country or "turkey",
            )
            pure_night = decomp.get("pure_hotel_night_per_adult", 0.0)
            if pure_night < 50.0:
                pure_night = max(50.0, (item["price"] * 0.40) / (pt_nights * max(1, pt_adults + pt_children * 0.2)))
            flight_seat = decomp.get("flight_seat_cost", 1300.0)
            norm_price = round(flight_seat + (8.0 * pure_night * single_factor), 1)

            history_points.append(
                HotelHistoryPoint(
                    recorded_at=item["recorded_at"],
                    total_price_pln=item["price"],
                    price_per_night_per_pax=item["price_per_night_pax"],
                    departure_date=item["departure_date"],
                    duration_nights=item["duration_nights"],
                    airport=item["airport"],
                    normalized_price_1p_8n=norm_price,
                    pure_hotel_night_rate=round(pure_night, 1),
                    adults=pt_adults,
                    children=pt_children,
                )
            )

        min_p = min(prices) if prices else 0.0
        max_p = max(prices) if prices else 0.0
        med_p = sorted(prices)[len(prices) // 2] if prices else 0.0
        curr_p = prices[-1] if prices else min_p

        # Knowledge Base Dossier
        dossier = HotelKnowledgeService.get_hotel_dossier(
            hotel_name=hotel.display_name,
            destination=hotel.region or "turkey",
            country=hotel.country,
            stars=hotel.stars or 4,
            current_price=curr_p,
            main_image_url=hotel.main_image_url,
        )

        final_ta_rating = (
            float(hotel.ta_rating)
            if hotel.ta_rating
            else (float(dossier["ta_rating"]) if dossier.get("ta_rating") else 4.5)
        )
        final_ta_reviews = (
            int(hotel.ta_reviews)
            if hotel.ta_reviews
            else (int(dossier["ta_reviews"]) if dossier.get("ta_reviews") else 0)
        )

        # Hopper score calculation using canonical V1 statistical engine (hotel_deal_score)
        deal_score = 75
        deal_badge = "GOOD_DEAL"
        verdict = "BUY NOW"

        if history_points:
            import pandas as pd
            from app.services.hotel_deal_score import compute_hotel_deal_metrics

            df_hist = pd.DataFrame([
                {"scraped_at": p.recorded_at, "price": p.total_price_pln}
                for p in history_points
            ])
            deal_metrics = compute_hotel_deal_metrics(
                df_hist,
                latest_price=curr_p,
                time_col="scraped_at",
                price_col="price",
                ta_rating=final_ta_rating,
                ta_review_count=final_ta_reviews,
            )
            deal_score = int(deal_metrics.get("deal_score", 75))
            if deal_score >= 85:
                deal_badge = "SUPER_DEAL"
                verdict = "BUY NOW"
            elif deal_score >= 80:
                deal_badge = "GOOD_DEAL"
                verdict = "BUY NOW"
            elif deal_score < 45:
                deal_badge = "OVERPRICED"
                verdict = "OVERPRICED"
            else:
                deal_badge = "FAIR_PRICE"
                verdict = "WAIT"

        # Update dossier deal score
        dossier["deal_score"] = deal_score

        # German Arbitrage direct offer lookup with strict entity matching
        from app.services.arbitrage_service import find_check24_offer
        c24 = find_check24_offer(
            name=hotel.display_name,
            destination=hotel.country,
        )

        german_arbitrage = None
        if c24 and c24.get("price_pln") and c24["price_pln"] > 0:
            ber_url = str(c24.get("offer_url") or "").strip()
            # Strict validation: must lead to a specific offer page, NOT generic /suche/?q= search and not empty hotelId=
            is_specific_offer = bool(
                ber_url
                and "/suche/?q=" not in ber_url
                and ("check24" not in ber_url or ("hotelId=" in ber_url and not ber_url.endswith("hotelId=")))
            )
            if is_specific_offer:
                ber_price = float(c24["price_pln"])
                savings_pln = max(0.0, round(curr_p - ber_price, 0))
                # Only show arbitrage if there is real, positive savings (> 0)
                if savings_pln > 0:
                    savings_pct = round((savings_pln / curr_p) * 100.0, 1) if curr_p > 0 else 0.0
                    german_arbitrage = {
                        "berlin_price_pln": ber_price,
                        "polish_price_pln": curr_p,
                        "savings_pln": savings_pln,
                        "savings_pct": savings_pct,
                        "berlin_operator": c24.get("operator", "Check24 / TUI Deutschland"),
                        "departure_airport": c24.get("departure_airport", "BER (Берлин-Бранденбург)"),
                        "booking_url": ber_url,
                        "train_transfer_from_pl": "PKP Intercity Варшава/Познань -> Berlin Hbf (~2.5 - 5ч)",
                    }

        packages_list = sorted(list(packages_map.values()), key=lambda x: x["total_price_pln"])

        final_main_image = hotel.main_image_url or dossier.get("main_image_url") or (dossier["gallery_photos"][0] if dossier.get("gallery_photos") else None)
        final_gallery = list(dossier.get("gallery_photos", []))
        if final_main_image and final_main_image not in final_gallery:
            final_gallery = [final_main_image] + final_gallery

        return HotelPassportResponse(
            hotel_id=hotel.hotel_id,
            display_name=hotel.display_name,
            country=hotel.country,
            region=hotel.region or "",
            stars=hotel.stars or 4,
            ta_rating=dossier["ta_rating"],
            ta_reviews=dossier["ta_reviews"],
            main_image_url=final_main_image,
            all_time_min_pln=min_p,
            all_time_max_pln=max_p,
            typical_median_pln=med_p,
            current_price_pln=curr_p,
            active_cohorts_count=len(all_cohorts),
            deal_score=deal_score,
            deal_badge=deal_badge,
            hopper_verdict=verdict,
            gallery_photos=final_gallery,
            tripadvisor_url=dossier["tripadvisor_url"],
            google_reviews_url=dossier["google_reviews_url"],
            youtube_search_url=dossier["youtube_search_url"],
            beach_line=dossier["beach_line"],
            beach_type=dossier["beach_type"],
            sea_entry=dossier["sea_entry"],
            has_aquapark=dossier["has_aquapark"],
            has_heated_pools=dossier["has_heated_pools"],
            food_concept=dossier["food_concept"],
            pros=dossier["pros"],
            cons=dossier["cons"],
            verdict=dossier["verdict"],
            suitable_for=dossier["suitable_for"],
            ai_action_signal=dossier["ai_action_signal"],
            ai_price_summary=dossier["ai_price_summary"],
            ai_hotel_summary=dossier["ai_hotel_summary"],
            infra_rich=dossier["infra_rich"],
            german_arbitrage=german_arbitrage,
            available_packages=packages_list,
            other_filters=other_filters,
            history_points=history_points,
        )

