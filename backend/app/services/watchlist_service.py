import uuid
import logging
import time
import re
import hashlib
import urllib.parse
from collections import defaultdict
from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple, Dict, Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, delete, text

from app.models.hotel import Hotel
from app.models.cohort import OfferCohort
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist import WatchlistItem
from app.schemas.watchlist import (
    WatchlistCreateRequest,
    WatchlistUpdateRequest,
    WatchlistItemResponse,
    WatchlistListResponse,
    WatchlistAlertPayload,
)
from app.schemas.hotel import HotelPassportResponse, HotelHistoryPoint

logger = logging.getLogger("travel_monitor_2.watchlist")


_HOTEL_ALIAS_CACHE: Dict[str, List[str]] = {}
_TOKEN_CLUSTER_MAP: Dict[Tuple[str, str], List[str]] = {}
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
    # 1. Remove all parentheses (both closed and unclosed like 'Hotel (Ex. Grand Halomy Res')
    n = re.sub(r"\s*\(.*", "", title)
    # 2. Remove country and common resort/city tokens
    n = re.sub(
        r"\b(?:turcja|egipt|grecja|cypr|hiszpania|turkey|egypt|greece|cyprus|spain|alanya|kemer|side|belek|antalya|sharm|hurghada|türkler|okurcalar|el|sheikh)\b",
        " ",
        n,
        flags=re.I,
    )
    n = re.sub(r"[^\w\s]", " ", n.lower())
    n = n.replace("pickalbatros", "albatros")
    stop = {
        "hotel", "hotels", "resort", "resorts", "spa", "beach", "club",
        "palace", "deluxe", "aqua", "park", "the", "and", "di", "ex", "inn", "suites", "village", "residences"
    }
    tokens = [t for t in n.split() if len(t) > 1 and t not in stop]
    return " ".join(sorted(tokens)) if tokens else title.strip().lower()


class WatchlistService:

    @classmethod
    async def add_to_watchlist(
        cls, db: AsyncSession, req: WatchlistCreateRequest
    ) -> WatchlistItemResponse:
        # 1. Verify Cohort exists (by exact hash, or fallback to hotel_id match)
        c_stmt = (
            select(OfferCohort, Hotel)
            .join(Hotel, OfferCohort.hotel_id == Hotel.hotel_id)
            .where(OfferCohort.cohort_hash == req.cohort_hash)
        )
        c_res = await db.execute(c_stmt)
        row = c_res.first()

        if not row:
            # Fallback 1: Extract candidate hotel_id from synthetic hash (e.g. hotelId_date_nights)
            h_id_guess = req.cohort_hash.split("_")[0] if "_" in req.cohort_hash else req.cohort_hash
            c_fallback_stmt = (
                select(OfferCohort, Hotel)
                .join(Hotel, OfferCohort.hotel_id == Hotel.hotel_id)
                .where(
                    or_(
                        OfferCohort.hotel_id == h_id_guess,
                        OfferCohort.hotel_id.ilike(f"%{h_id_guess}%"),
                        Hotel.hotel_id == h_id_guess,
                    )
                )
                .order_by(desc(OfferCohort.cohort_id))
                .limit(1)
            )
            c_res = await db.execute(c_fallback_stmt)
            row = c_res.first()

        if not row:
            # Fallback 2: Check if hotel exists in hotels table and create cohort on the fly
            h_id_guess = req.cohort_hash.split("_")[0] if "_" in req.cohort_hash else req.cohort_hash
            h_stmt = select(Hotel).where(or_(Hotel.hotel_id == h_id_guess, Hotel.hotel_id.ilike(f"%{h_id_guess}%"))).limit(1)
            hotel_obj = (await db.execute(h_stmt)).scalar_one_or_none()
            if hotel_obj:
                safe_hash = req.cohort_hash if len(req.cohort_hash) <= 32 else hashlib.sha256(req.cohort_hash.encode()).hexdigest()[:32]
                cohort_obj = OfferCohort(
                    cohort_hash=safe_hash,
                    hotel_id=hotel_obj.hotel_id,
                    destination_code=hotel_obj.country or "EG",
                    checkin_date=datetime.utcnow().date() + timedelta(days=20),
                    duration_nights=7,
                    airport_code="WAW",
                )
                db.add(cohort_obj)
                await db.flush()
                row = (cohort_obj, hotel_obj)

        if not row:
            raise HTTPException(status_code=404, detail="Offer cohort or hotel not found")

        cohort, hotel = row[0], row[1]

        # 2. Check if already watched by this user
        w_stmt = select(WatchlistItem).where(
            and_(
                WatchlistItem.user_chat_id == req.user_chat_id,
                or_(
                    WatchlistItem.cohort_hash == cohort.cohort_hash,
                    WatchlistItem.cohort_hash == req.cohort_hash,
                )
            )
        )
        w_res = await db.execute(w_stmt)
        existing_item = w_res.scalar_one_or_none()

        if existing_item:
            existing_item.cohort_hash = cohort.cohort_hash
            existing_item.target_price_pln = req.target_price_pln
            existing_item.notify_any_drop = req.notify_any_drop
            if req.alert_threshold_pct is not None:
                existing_item.alert_threshold_pct = req.alert_threshold_pct
            if req.min_deal_score is not None:
                existing_item.min_deal_score = req.min_deal_score
            existing_item.is_active = req.is_active
            watch_item = existing_item
        else:
            watch_id = f"w_{uuid.uuid4().hex[:10]}"
            watch_item = WatchlistItem(
                watch_id=watch_id,
                user_chat_id=req.user_chat_id,
                cohort_hash=cohort.cohort_hash,
                target_price_pln=req.target_price_pln,
                notify_any_drop=req.notify_any_drop,
                alert_threshold_pct=req.alert_threshold_pct,
                min_deal_score=req.min_deal_score,
                is_active=req.is_active,
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
            alert_threshold_pct=watch_item.alert_threshold_pct,
            min_deal_score=watch_item.min_deal_score,
            is_active=watch_item.is_active,
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
        # Match by direct chat_id or linked user profile
        user_ids = {user_chat_id}
        try:
            from app.models.user import User
            u_stmt = select(User).where(or_(User.id == user_chat_id, User.telegram_chat_id == user_chat_id))
            u_res = await db.execute(u_stmt)
            user_obj = u_res.scalars().first()
            if user_obj:
                user_ids.add(user_obj.id)
                if user_obj.telegram_chat_id:
                    user_ids.add(user_obj.telegram_chat_id)
        except Exception:
            pass

        stmt = (
            select(WatchlistItem, OfferCohort, Hotel)
            .join(OfferCohort, WatchlistItem.cohort_hash == OfferCohort.cohort_hash)
            .join(Hotel, OfferCohort.hotel_id == Hotel.hotel_id)
            .where(WatchlistItem.user_chat_id.in_(list(user_ids)))
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
                    alert_threshold_pct=watch_item.alert_threshold_pct if watch_item.alert_threshold_pct is not None else 5.0,
                    min_deal_score=watch_item.min_deal_score,
                    is_active=watch_item.is_active if watch_item.is_active is not None else True,
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
    async def update_watchlist_item(
        cls, db: AsyncSession, watch_id: str, req: WatchlistUpdateRequest
    ) -> WatchlistItemResponse:
        """Updates threshold parameters, target prices, and active state of a watchlist item."""
        w_stmt = select(WatchlistItem).where(WatchlistItem.watch_id == watch_id)
        w_res = await db.execute(w_stmt)
        watch_item = w_res.scalar_one_or_none()
        if not watch_item:
            raise HTTPException(status_code=404, detail="Watchlist item not found")

        c_stmt = (
            select(OfferCohort, Hotel)
            .join(Hotel, OfferCohort.hotel_id == Hotel.hotel_id)
            .where(OfferCohort.cohort_hash == watch_item.cohort_hash)
        )
        c_res = await db.execute(c_stmt)
        c_row = c_res.first()
        if not c_row:
            raise HTTPException(status_code=404, detail="Associated cohort or hotel not found")

        cohort, hotel = c_row[0], c_row[1]

        if req.target_price_pln is not None:
            watch_item.target_price_pln = req.target_price_pln if req.target_price_pln > 0 else None
        if req.alert_threshold_pct is not None:
            watch_item.alert_threshold_pct = req.alert_threshold_pct
        if req.min_deal_score is not None:
            watch_item.min_deal_score = req.min_deal_score if req.min_deal_score > 0 else None
        if req.notify_any_drop is not None:
            watch_item.notify_any_drop = req.notify_any_drop
        if req.is_active is not None:
            watch_item.is_active = req.is_active

        await db.commit()
        await db.refresh(watch_item)

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

        return WatchlistItemResponse(
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
            alert_threshold_pct=watch_item.alert_threshold_pct if watch_item.alert_threshold_pct is not None else 5.0,
            min_deal_score=watch_item.min_deal_score,
            is_active=watch_item.is_active if watch_item.is_active is not None else True,
            latest_price_pln=latest_price,
            deal_score=90 if target_reached else 70,
            deal_badge="SUPER_DEAL" if target_reached else "WATCHING",
            hopper_verdict="BUY NOW" if target_reached else "WAIT",
            target_reached=target_reached,
            booking_url=cohort.offer_url,
            created_at=watch_item.created_at,
            last_notified_at=watch_item.last_notified_at,
        )

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
    async def _ensure_alias_cache(cls, db: AsyncSession) -> None:
        global _HOTEL_ALIAS_CACHE, _TOKEN_CLUSTER_MAP, _ALIAS_CACHE_TS
        now = time.time()
        if _HOTEL_ALIAS_CACHE and (now - _ALIAS_CACHE_TS < _ALIAS_CACHE_TTL):
            return

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
        _TOKEN_CLUSTER_MAP = dict(clusters)
        _ALIAS_CACHE_TS = now

    @classmethod
    async def _find_related_hotel_ids(cls, db: AsyncSession, hotel: Hotel) -> List[str]:
        """
        Finds all hotel_ids that refer to the same physical property,
        handling tour operator renames, (ex. ...) additions, regional tags, and trailing 'Hotel/Resort' variations.
        Uses in-memory cluster caching for <0.1ms lookups.
        """
        await cls._ensure_alias_cache(db)
        if hotel.hotel_id in _HOTEL_ALIAS_CACHE:
            return _HOTEL_ALIAS_CACHE[hotel.hotel_id]

        c = _norm_country(hotel.country)
        toks = _smart_hotel_tokens(hotel.display_name)
        if toks and (c, toks) in _TOKEN_CLUSTER_MAP:
            matched = _TOKEN_CLUSTER_MAP[(c, toks)]
            combined = list(set([hotel.hotel_id] + matched))
            _HOTEL_ALIAS_CACHE[hotel.hotel_id] = combined
            return combined

        return [hotel.hotel_id]

    @classmethod
    async def resolve_hotel_aliases_bulk(
        cls, db: AsyncSession, hotel_queries: List[Tuple[str, str, str]]
    ) -> Dict[str, List[str]]:
        """
        Bulk resolves hotel aliases. Input: [(hotel_id, display_name, country), ...]
        Returns: {hotel_id: [related_canonical_ids]}
        """
        await cls._ensure_alias_cache(db)
        results: Dict[str, List[str]] = {}
        for hid, name, country in hotel_queries:
            if hid in _HOTEL_ALIAS_CACHE:
                results[hid] = _HOTEL_ALIAS_CACHE[hid]
                continue
            c = _norm_country(country)
            toks = _smart_hotel_tokens(name)
            if toks and (c, toks) in _TOKEN_CLUSTER_MAP:
                matched = _TOKEN_CLUSTER_MAP[(c, toks)]
                combined = list(set([hid] + matched))
                results[hid] = combined
            else:
                results[hid] = [hid]
        return results

    @classmethod
    async def get_hotel_passport(
        cls,
        db: AsyncSession,
        hotel_id: str,
        filter_id: Optional[str] = None,
        name: Optional[str] = None,
        stars: Optional[int] = None,
        country: Optional[str] = None,
        region: Optional[str] = None,
        current_price: Optional[float] = None,
        ta_rating: Optional[float] = None,
        main_image_url: Optional[str] = None,
        adults: Optional[int] = None,
        children: Optional[int] = None,
        duration_nights: Optional[int] = None,
        departure_date: Optional[str] = None,
    ) -> HotelPassportResponse:
        from app.services.hotel_knowledge_service import HotelKnowledgeService
        from app.services.canonical_filters import resolve_filter_spec
        from app.services.cost_decomposer import CostDecomposer

        # 1. Fetch Hotel (or synthesize on the fly if new/unknown)
        h_stmt = select(Hotel).where(Hotel.hotel_id == hotel_id)
        hotel = (await db.execute(h_stmt)).scalar_one_or_none()

        if not hotel:
            # On-the-fly hotel creation for dynamically discovered search results
            from app.services.geo_resolver import GeoResolver
            display_title = (name or " ".join(w.capitalize() for w in hotel_id.replace("_", "-").split("-"))).strip()
            c_name, r_name = GeoResolver.resolve(
                hotel_name=display_title,
                current_country=country,
                current_region=region,
            )
            st_val = int(stars or 4)
            ta_val = float(ta_rating) if ta_rating else 4.2
            img_val = main_image_url or ""

            # Check if HotelKnowledgeService has matched entry for specs/images/photos
            dossier_pre = HotelKnowledgeService.get_hotel_dossier(
                hotel_name=display_title,
                destination=r_name or "turkey",
                country=c_name,
                stars=st_val,
                current_price=float(current_price or 0.0),
                main_image_url=img_val or None,
            )
            if dossier_pre.get("main_image_url") and not img_val:
                img_val = dossier_pre["main_image_url"]
            if dossier_pre.get("ta_rating") and not ta_rating:
                ta_val = float(dossier_pre["ta_rating"])

            hotel = Hotel(
                hotel_id=hotel_id,
                display_name=display_title,
                country=c_name,
                region=r_name,
                stars=st_val,
                ta_rating=ta_val,
                main_image_url=img_val,
            )
            try:
                db.add(hotel)
                await db.commit()
            except Exception as e:
                logger.warning(f"Could not persist on-the-fly hotel {hotel_id}: {e}")
                await db.rollback()

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
            # Dynamically synthesize a live baseline cohort for newly discovered hotel
            curr_val = float(current_price or 0.0)
            dest_str = hotel.country or "turkey"
            if curr_val <= 0:
                pure_bench = 180.0 if (hotel.stars or 4) >= 5 else 125.0
                curr_val = CostDecomposer.recompose(
                    pure_hotel_night_per_adult=pure_bench,
                    duration_nights=8,
                    adults=2,
                    children=1,
                    destination=dest_str,
                )

            now_dt = datetime.utcnow()
            checkin_d = (now_dt + timedelta(days=21)).date()
            checkout_d = checkin_d + timedelta(days=8)
            syn_cohort = SimpleNamespace(
                cohort_id=999999,
                cohort_hash=f"syn_{hotel_id[:12]}",
                filter_id=filter_id or "interactive_search",
                hotel_id=hotel.hotel_id,
                destination_code=(dest_str).lower(),
                checkin_date=str(checkin_d),
                checkout_date=str(checkout_d),
                duration_nights=8,
                airport_code="WAW",
                board_basis="All Inclusive",
                room_type="Standard",
                adults=2,
                children=1,
                operator="Touroperator",
                offer_url=f"https://fly.pl/szukaj-wycieczek/?hotelName={urllib.parse.quote(hotel.display_name)}",
            )
            all_cohorts = [syn_cohort]

        # 3. Determine scoped cohorts for the active filter to ensure a clean, smooth, non-oscillating curve
        spec = resolve_filter_spec(filter_id) if filter_id else None
        target_adults = int(adults) if (adults is not None and adults > 0) else (spec.get("adults", 1) if spec else 1)
        target_children = int(children) if (children is not None and children >= 0) else (spec.get("children", 0) if spec else 0)
        target_nights = int(duration_nights) if (duration_nights is not None and duration_nights > 0) else (spec.get("min_nights", 7) if spec else 7)

        is_user_monitor = bool(filter_id and (filter_id.startswith("monitor_") or filter_id.startswith("user_")))
        if is_user_monitor:
            clean_uid = filter_id.replace("monitor_", "").replace("user_", "").replace("filter_", "")
            try:
                u_res = await db.execute(
                    text("SELECT id, title, filter_params_json FROM user_monitors WHERE id = :uid"),
                    {"uid": clean_uid},
                )
                u_row = u_res.fetchone()
                if u_row and u_row[2]:
                    u_params = json.loads(u_row[2])
                    travelers = u_params.get("travelers")
                    if isinstance(travelers, dict):
                        if adults is None:
                            target_adults = travelers.get("adults", target_adults)
                        if children is None:
                            target_children = travelers.get("children", target_children)
                    else:
                        if adults is None:
                            target_adults = u_params.get("adults", 2)
                        if children is None:
                            target_children = u_params.get("children", 0)

                    dur_range = u_params.get("duration_range")
                    if duration_nights is None:
                        if isinstance(dur_range, list) and len(dur_range) >= 1:
                            target_nights = dur_range[0]
                        elif u_params.get("duration_min"):
                            target_nights = u_params.get("duration_min")
            except Exception as e:
                logger.warning(f"Failed to resolve user monitor params for {clean_uid}: {e}")

        from app.services.timeline_service import resolve_filter_id, get_all_filter_id_variants
        canonical_fid = resolve_filter_id(filter_id) if filter_id else None
        filter_variants = set(get_all_filter_id_variants(filter_id)) if filter_id else set()
        scoped_cohorts = []
        if filter_variants:
            scoped_cohorts = [c for c in all_cohorts if c.filter_id in filter_variants]

        if is_user_monitor:
            # Strictly isolate user monitor timeline: do NOT mix with other years/filters!
            if not scoped_cohorts:
                curr_val = float(current_price or 0.0)
                dest_str = hotel.country or "egypt"
                now_dt = datetime.utcnow()
                checkin_d = (now_dt + timedelta(days=21)).date()
                checkout_d = checkin_d + timedelta(days=target_nights or 7)
                syn_cohort = SimpleNamespace(
                    cohort_id=999999,
                    cohort_hash=f"syn_{hotel_id[:12]}",
                    filter_id=filter_id,
                    hotel_id=hotel.hotel_id,
                    destination_code=dest_str.lower(),
                    checkin_date=str(checkin_d),
                    checkout_date=str(checkout_d),
                    duration_nights=target_nights or 7,
                    airport_code="WAW",
                    board_basis="All Inclusive",
                    room_type="Standard",
                    adults=target_adults,
                    children=target_children,
                    operator="Touroperator",
                    offer_url=f"https://fly.pl/szukaj-wycieczek/?hotelName={urllib.parse.quote(hotel.display_name)}",
                )
                all_cohorts = [syn_cohort] + [c for c in all_cohorts if c.cohort_id != 999999]
                scoped_cohorts = [syn_cohort]
        else:
            if not scoped_cohorts:
                if spec:
                    dest_codes = set(spec.get("destination_codes", []))
                    scoped_cohorts = [c for c in all_cohorts if c.destination_code in dest_codes]
                    if not scoped_cohorts:
                        # Fallback to party composition
                        scoped_cohorts = [c for c in all_cohorts if c.adults == target_adults and c.children == target_children]

            # If still no scoped cohorts or no filter_id provided (e.g. Interactive Search / all history),
            # DO NOT discard other cohorts! Include ALL cohorts for this property and normalize them!
            if not scoped_cohorts:
                scoped_cohorts = all_cohorts

            if not scoped_cohorts and all_cohorts:
                scoped_cohorts = all_cohorts

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

        # 4c. Fetch normalized historical snapshots across all related aliases
        norm_sql = f"""
            SELECT hotel_id, recorded_at, normalized_price_1p_8n, pure_hotel_night_rate
            FROM normalized_price_snapshots
            WHERE hotel_id IN ({placeholders})
            ORDER BY recorded_at ASC
        """
        norm_rows = []
        try:
            n_res = await db.execute(text(norm_sql), h_params)
            norm_rows = n_res.fetchall()
        except Exception as n_err:
            logger.warning(f"Failed to query normalized_price_snapshots for {hotel_id}: {n_err}")

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
        if not s_rows:
            curr_val = float(current_price or 0.0)
            dest_str = hotel.country or "turkey"
            if curr_val <= 0:
                pure_bench = 180.0 if (hotel.stars or 4) >= 5 else 125.0
                curr_val = CostDecomposer.recompose(
                    pure_hotel_night_per_adult=pure_bench,
                    duration_nights=8,
                    adults=2,
                    children=1,
                    destination=dest_str,
                )
            now_dt = datetime.utcnow()
            snap_rows = [
                SimpleNamespace(
                    cohort_id=all_cohorts[0].cohort_id,
                    recorded_at=now_dt,
                    total_price_pln=curr_val,
                    price_per_night_per_pax=round(curr_val / 24.0, 2),
                )
            ]
        else:
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
        # Decompose every historical snapshot into normalized pure rates and recompose for target user party
        from app.services.cost_decomposer import CostDecomposer
        from app.services.search_intelligence import get_destination_season_info

        dest_name = hotel.country or "turkey"
        dest_lower = dest_name.lower()
        single_factor = 1.18 if "turk" in dest_lower else 1.20
        now_dt = datetime.utcnow()

        min_snap_dt = min((s.recorded_at for s in snap_rows if s.recorded_at), default=now_dt)
        max_snap_dt = max((s.recorded_at for s in snap_rows if s.recorded_at), default=now_dt)
        if isinstance(min_snap_dt, str):
            try:
                min_snap_dt = datetime.fromisoformat(min_snap_dt.replace("Z", "+00:00"))
            except Exception:
                min_snap_dt = now_dt
        if isinstance(max_snap_dt, str):
            try:
                max_snap_dt = datetime.fromisoformat(max_snap_dt.replace("Z", "+00:00"))
            except Exception:
                max_snap_dt = now_dt

        span_days = max(1, (max_snap_dt - min_snap_dt).days) if hasattr(max_snap_dt - min_snap_dt, "days") else 30

        bucket_map: Dict[str, Dict[str, Any]] = {}
        for snap in snap_rows:
            if snap.cohort_id not in scoped_cohort_ids:
                continue
            rec_dt = (
                datetime.fromisoformat(snap.recorded_at)
                if isinstance(snap.recorded_at, str)
                else snap.recorded_at or now_dt
            )
            # Smart bucketing: for history spanning >20 days, older snapshots (>14d) bucket by day, recent bucket hourly
            dt_raw = rec_dt.replace(tzinfo=None) if rec_dt.tzinfo else rec_dt
            now_raw = now_dt.replace(tzinfo=None) if now_dt.tzinfo else now_dt
            days_ago = (now_raw - dt_raw).days
            if span_days > 20 and days_ago > 14:
                bucket_key = rec_dt.strftime("%Y-%m-%d")
            else:
                bucket_key = rec_dt.strftime("%Y-%m-%d %H:00")

            cohort = cohort_by_id.get(snap.cohort_id)
            if not cohort:
                continue
            checkin_d = (
                datetime.strptime(cohort.checkin_date, "%Y-%m-%d").date()
                if isinstance(cohort.checkin_date, str) and "-" in cohort.checkin_date
                else now_dt.date()
            )

            pt_adults = cohort.adults or 2
            pt_children = cohort.children or 0
            pt_nights = max(1, cohort.duration_nights or 8)

            decomp = CostDecomposer.decompose(
                total_price_pln=snap.total_price_pln,
                duration_nights=pt_nights,
                adults=pt_adults,
                children=pt_children,
                destination=dest_name,
            )
            pure_night = decomp.get("pure_hotel_night_per_adult", 0.0)
            if pure_night < 50.0:
                pure_night = max(50.0, (snap.total_price_pln * 0.40) / (pt_nights * max(1, pt_adults + pt_children * 0.2)))
            flight_seat = decomp.get("flight_seat_cost", 1300.0)
            norm_price = round(flight_seat + (8.0 * pure_night * single_factor), 1)

            # Recompose into target user tour scope
            if pt_adults == target_adults and pt_children == target_children and (pt_nights == target_nights or abs(pt_nights - target_nights) <= 1):
                scaled_tour_price = snap.total_price_pln
            else:
                scaled_tour_price = CostDecomposer.recompose(
                    pure_hotel_night_per_adult=pure_night,
                    duration_nights=target_nights,
                    adults=target_adults,
                    children=target_children,
                    destination=dest_name,
                )

            # Preserve lowest scaled price for that bucket
            if bucket_key not in bucket_map or scaled_tour_price < bucket_map[bucket_key]["scaled_tour_price"]:
                bucket_map[bucket_key] = {
                    "recorded_at": rec_dt,
                    "total_price_pln": snap.total_price_pln,
                    "price_per_night_pax": snap.price_per_night_per_pax,
                    "departure_date": checkin_d,
                    "duration_nights": pt_nights,
                    "airport": cohort.airport_code,
                    "normalized_price_1p_8n": norm_price,
                    "pure_hotel_night_rate": round(pure_night, 1),
                    "scaled_tour_price": round(scaled_tour_price, 1),
                    "adults": pt_adults,
                    "children": pt_children,
                }

        # Also integrate normalized historical snapshots for all related aliases
        for n_hid, n_rec_dt, n_norm_price, n_pure_rate in norm_rows:
            if not n_pure_rate or float(n_pure_rate) <= 0:
                continue
            rec_dt = (
                datetime.fromisoformat(n_rec_dt)
                if isinstance(n_rec_dt, str)
                else n_rec_dt or now_dt
            )
            dt_raw = rec_dt.replace(tzinfo=None) if rec_dt.tzinfo else rec_dt
            now_raw = now_dt.replace(tzinfo=None) if now_dt.tzinfo else now_dt
            days_ago = (now_raw - dt_raw).days
            if span_days > 20 and days_ago > 14:
                bucket_key = rec_dt.strftime("%Y-%m-%d")
            else:
                bucket_key = rec_dt.strftime("%Y-%m-%d %H:00")

            pure_rate = float(n_pure_rate)
            scaled_tour_price = CostDecomposer.recompose(
                pure_hotel_night_per_adult=pure_rate,
                duration_nights=target_nights,
                adults=target_adults,
                children=target_children,
                destination=dest_name,
            )
            norm_price = CostDecomposer.recompose(
                pure_hotel_night_per_adult=pure_rate,
                duration_nights=8,
                adults=1,
                children=0,
                destination=dest_name,
            )
            if bucket_key not in bucket_map or scaled_tour_price < bucket_map[bucket_key]["scaled_tour_price"]:
                bucket_map[bucket_key] = {
                    "recorded_at": rec_dt,
                    "total_price_pln": scaled_tour_price,
                    "price_per_night_pax": round(scaled_tour_price / max(1, target_nights * (target_adults + target_children)), 1),
                    "departure_date": (rec_dt + timedelta(days=21)).date() if hasattr(rec_dt, "date") else now_dt.date(),
                    "duration_nights": target_nights,
                    "airport": "WAW",
                    "normalized_price_1p_8n": round(norm_price, 1),
                    "pure_hotel_night_rate": round(pure_rate, 1),
                    "scaled_tour_price": round(scaled_tour_price, 1),
                    "adults": target_adults,
                    "children": target_children,
                }

        sorted_buckets = sorted(bucket_map.keys())
        history_points: List[HotelHistoryPoint] = []
        prices: List[float] = []

        for b_key in sorted_buckets:
            item = bucket_map[b_key]
            prices.append(item["scaled_tour_price"])
            history_points.append(
                HotelHistoryPoint(
                    recorded_at=item["recorded_at"],
                    total_price_pln=item["total_price_pln"],
                    price_per_night_per_pax=item["price_per_night_pax"],
                    departure_date=item["departure_date"],
                    duration_nights=item["duration_nights"],
                    airport=item["airport"],
                    normalized_price_1p_8n=item["normalized_price_1p_8n"],
                    pure_hotel_night_rate=item["pure_hotel_night_rate"],
                    scaled_tour_price=item["scaled_tour_price"],
                    adults=item["adults"],
                    children=item["children"],
                )
            )

        total_points_count = len(prices)
        curr_val = float(current_price) if current_price and float(current_price) > 0 else (prices[-1] if prices else 0.0)

        if total_points_count == 0:
            data_maturity_tier = 0
            maturity_explanation = "Отель обнаружен через расширенный live-поиск. Зафиксирована первая котировка, регулярный мониторинг цен запущен."
            if curr_val <= 0:
                pure_bench = 180.0 if (hotel.stars or 4) >= 5 else 125.0
                curr_val = CostDecomposer.recompose(
                    pure_hotel_night_per_adult=pure_bench,
                    duration_nights=target_nights,
                    adults=target_adults,
                    children=target_children,
                    destination=dest_name,
                )
            decomp = CostDecomposer.decompose(
                total_price_pln=curr_val,
                duration_nights=target_nights,
                adults=target_adults,
                children=target_children,
                destination=dest_name,
            )
            pure_night = decomp.get("pure_hotel_night_per_adult", 125.0)
            norm_price = CostDecomposer.recompose(
                pure_hotel_night_per_adult=pure_night,
                duration_nights=8,
                adults=1,
                children=0,
                destination=dest_name,
            )
            history_points = [
                HotelHistoryPoint(
                    recorded_at=now_dt,
                    total_price_pln=curr_val,
                    price_per_night_per_pax=round(curr_val / max(1, target_nights * (target_adults + target_children)), 1),
                    departure_date=(now_dt + timedelta(days=21)).date(),
                    duration_nights=target_nights,
                    airport="WAW",
                    normalized_price_1p_8n=round(norm_price, 1),
                    pure_hotel_night_rate=round(pure_night, 1),
                    scaled_tour_price=round(curr_val, 1),
                    adults=target_adults,
                    children=target_children,
                )
            ]
            curr_p = curr_val
            min_p = round(curr_val * 0.95, 1)
            med_p = curr_val
            max_p = round(curr_val * 1.10, 1)
        else:
            if total_points_count < 4:
                data_maturity_tier = 1
                maturity_explanation = f"Первичные замеры отеля ({total_points_count} точек). График отражает свежую динамику."
            elif total_points_count < 15:
                data_maturity_tier = 2
                maturity_explanation = "Свежая динамика цен за последние недели."
            else:
                data_maturity_tier = 3
                maturity_explanation = "Выверенная сезонная история наблюдений с медианой и диапазоном цен."

            if current_price and float(current_price) > 0:
                curr_p = float(current_price)
                from datetime import timezone
                now_utc = datetime.now(timezone.utc)
                decomp_curr = CostDecomposer.decompose(
                    total_price_pln=curr_p,
                    duration_nights=target_nights,
                    adults=target_adults,
                    children=target_children,
                    destination=dest_name,
                )
                curr_pure_night = decomp_curr.get("pure_hotel_night_per_adult", 125.0)
                curr_norm = round(decomp_curr.get("flight_seat_cost", 1300.0) + (8.0 * curr_pure_night * single_factor), 1)

                is_recent = False
                if history_points:
                    last_rec = history_points[-1].recorded_at
                    if isinstance(last_rec, str):
                        try:
                            last_rec = datetime.fromisoformat(last_rec.replace("Z", "+00:00"))
                        except Exception:
                            last_rec = None
                    if isinstance(last_rec, datetime):
                        if last_rec.tzinfo is None:
                            last_rec = last_rec.replace(tzinfo=timezone.utc)
                        if abs((now_utc - last_rec).total_seconds()) < 1800:
                            is_recent = True

                if is_recent:
                    history_points[-1].scaled_tour_price = curr_p
                    history_points[-1].pure_hotel_night_rate = round(curr_pure_night, 1)
                    history_points[-1].normalized_price_1p_8n = curr_norm
                else:
                    history_points.append(
                        HotelHistoryPoint(
                            recorded_at=now_utc,
                            total_price_pln=curr_p,
                            price_per_night_per_pax=round(curr_p / max(1, target_nights * (target_adults + target_children)), 1),
                            departure_date=(now_utc + timedelta(days=21)).date(),
                            duration_nights=target_nights,
                            airport="WAW",
                            normalized_price_1p_8n=curr_norm,
                            pure_hotel_night_rate=round(curr_pure_night, 1),
                            scaled_tour_price=curr_p,
                            adults=target_adults,
                            children=target_children,
                        )
                    )
            else:
                curr_p = history_points[-1].scaled_tour_price or history_points[-1].total_price_pln

            # Target departure date for the tour being viewed
            target_dep_date = None
            if departure_date:
                try:
                    if isinstance(departure_date, str):
                        target_dep_date = datetime.strptime(departure_date.split("T")[0], "%Y-%m-%d").date()
                    elif isinstance(departure_date, date):
                        target_dep_date = departure_date
                except Exception:
                    pass
            if not target_dep_date and history_points and history_points[-1].departure_date:
                target_dep_date = history_points[-1].departure_date
            if not target_dep_date:
                target_dep_date = (datetime.utcnow() + timedelta(days=21)).date()

            target_season = get_destination_season_info(dest_name, target_dep_date)
            target_mult = target_season.get("multiplier", 1.0)

            # De-season each history point's pure night rate by the season of its departure date
            unseasoned_rates = []
            for pt in history_points:
                pt_dep = pt.departure_date or target_dep_date
                pt_season = get_destination_season_info(dest_name, pt_dep)
                pt_mult = pt_season.get("multiplier", 1.0)
                rate = (pt.pure_hotel_night_rate or 120.0) / max(0.5, pt_mult)
                unseasoned_rates.append(rate)

            if len(unseasoned_rates) >= 3:
                sorted_unseasoned = sorted(unseasoned_rates)
                med_unseasoned = sorted_unseasoned[len(sorted_unseasoned) // 2]
                min_unseasoned = sorted_unseasoned[0]
                max_unseasoned = sorted_unseasoned[-1]

                # Re-season specifically for the TARGET departure month/season!
                seasonal_med_pure = med_unseasoned * target_mult
                seasonal_min_pure = min_unseasoned * target_mult
                seasonal_max_pure = max_unseasoned * target_mult

                med_p = round(CostDecomposer.recompose(
                    pure_hotel_night_per_adult=seasonal_med_pure,
                    duration_nights=target_nights,
                    adults=target_adults,
                    children=target_children,
                    destination=dest_name,
                ), 1)
                min_p = round(CostDecomposer.recompose(
                    pure_hotel_night_per_adult=seasonal_min_pure,
                    duration_nights=target_nights,
                    adults=target_adults,
                    children=target_children,
                    destination=dest_name,
                ), 1)
                max_p = round(CostDecomposer.recompose(
                    pure_hotel_night_per_adult=seasonal_max_pure,
                    duration_nights=target_nights,
                    adults=target_adults,
                    children=target_children,
                    destination=dest_name,
                ), 1)
            else:
                med_p = None
                p_list = [p.total_price_pln for p in history_points if p.total_price_pln]
                min_p = min(p_list) if p_list else curr_p
                max_p = max(p_list) if p_list else curr_p

        # Knowledge Base Dossier
        dossier = HotelKnowledgeService.get_hotel_dossier(
            hotel_name=hotel.display_name,
            destination=hotel.region or "turkey",
            country=hotel.country,
            stars=hotel.stars or 4,
            current_price=curr_p,
            main_image_url=hotel.main_image_url,
            db_specs=hotel.specs,
            db_reputation=hotel.reputation,
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
                {"scraped_at": p.recorded_at, "price": p.scaled_tour_price or p.total_price_pln}
                for p in history_points
            ])
            deal_metrics = compute_hotel_deal_metrics(
                df_hist,
                latest_price=curr_p,
                time_col="scraped_at",
                price_col="price",
                ta_rating=final_ta_rating,
                ta_review_count=final_ta_reviews,
                typical_price=med_p,
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

        # Horizon Arbitrage (Early Booking vs Standard vs Last Minute)
        from app.services.horizon_arbitrage_service import HorizonArbitrageService
        horizon_arbitrage = None
        try:
            horizon_arbitrage = await HorizonArbitrageService.get_hotel_horizon_arbitrage(
                db=db,
                hotel_id=hotel.hotel_id,
                adults=target_adults,
                children=target_children,
                duration_nights=target_nights,
                checkin_date=target_dep_date,
                current_price=curr_p,
            )
        except Exception as ha_err:
            logger.warning(f"Could not compute horizon arbitrage for {hotel.hotel_id}: {ha_err}")

        packages_list = sorted(list(packages_map.values()), key=lambda x: x["total_price_pln"])

        final_main_image = hotel.main_image_url or dossier.get("main_image_url") or (dossier["gallery_photos"][0] if dossier.get("gallery_photos") else None)
        final_gallery = list(dossier.get("gallery_photos", []))
        if final_main_image and final_main_image not in final_gallery:
            final_gallery = [final_main_image] + final_gallery

        from app.services.geo_resolver import GeoResolver
        canon_c, canon_r = GeoResolver.resolve(
            hotel_name=hotel.display_name,
            offer_url=all_cohorts[0].offer_url if all_cohorts else None,
            current_country=hotel.country,
            current_region=hotel.region,
        )

        # Build intelligent AI micro-insight for this hotel passport
        if med_p is not None and med_p > 0 and len(unseasoned_rates) >= 3:
            diff_to_norm = round(((curr_p - med_p) / med_p) * 100.0, 1)
            if diff_to_norm <= -15.0:
                ai_action_signal = f"🔥 Скидка {abs(diff_to_norm):.0f}% к норме сезона"
                ai_price_summary = f"Текущая цена {curr_p:.0f} zł на {abs(diff_to_norm):.0f}% ниже сезонной нормы ({med_p:.0f} zł). Это исторически выгодный момент для бронирования."
            elif diff_to_norm <= -7.0:
                ai_action_signal = f"⚡ Выгодная цена ({diff_to_norm:+.0f}%)"
                ai_price_summary = f"Тур стоит {curr_p:.0f} zł при сезонной норме {med_p:.0f} zł ({diff_to_norm:+.1f}%). Рекомендуется фиксировать."
            elif diff_to_norm <= 7.0:
                ai_action_signal = "⚖️ Стандартная цена сезона"
                ai_price_summary = f"Цена {curr_p:.0f} zł находится в пределах сезонной нормы ({med_p:.0f} zł). Спешить не нужно, можно отслеживать динамику."
            else:
                ai_action_signal = f"🔴 Выше нормы (+{diff_to_norm:.0f}%)"
                ai_price_summary = f"Цена {curr_p:.0f} zł завышена на {diff_to_norm:.0f}% относительно сезонной нормы ({med_p:.0f} zł). Рекомендуется подождать."
        else:
            diff_to_norm = None
            ai_action_signal = "📊 Первичные замеры отеля"
            ai_price_summary = f"Текущая цена {curr_p:.0f} zł. Идёт накопление истории по отелю ({len(unseasoned_rates)} точек). Сравнение с нормой отключено во избежание неточных выводов."

        ai_hotel_summary = f"{hotel.display_name} ({hotel.stars}★, {hotel.region or hotel.country}). {target_season.get('label', '')}: {target_season.get('risk_expl', '')}."

        ai_insight = {
            "headline": ai_action_signal,
            "season_label": target_season.get("label", ""),
            "season_context": target_season.get("risk_expl", ""),
            "diff_to_norm_pct": diff_to_norm,
            "seasonal_norm_pln": med_p,
            "current_price_pln": curr_p,
            "summary": ai_price_summary,
        }

        return HotelPassportResponse(
            hotel_id=hotel.hotel_id,
            display_name=hotel.display_name,
            country=canon_c,
            region=canon_r or "",
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
            data_maturity_tier=data_maturity_tier,
            maturity_explanation=maturity_explanation,
            user_query_scope={
                "adults": target_adults,
                "children": target_children,
                "duration_nights": target_nights,
            },
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
            ai_action_signal=ai_action_signal,
            ai_price_summary=ai_price_summary,
            ai_hotel_summary=ai_hotel_summary,
            seasonal_norm_pln=med_p,
            ai_insight=ai_insight,
            infra_rich=dossier["infra_rich"],
            german_arbitrage=german_arbitrage,
            horizon_arbitrage=horizon_arbitrage,
            available_packages=packages_list,
            other_filters=other_filters,
            history_points=history_points,
        )

