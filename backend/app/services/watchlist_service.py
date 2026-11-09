import uuid
import logging
from datetime import datetime, date
from typing import List, Optional, Tuple, Dict, Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, delete

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
            .where(PriceSnapshot.cohort_hash == req.cohort_hash)
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
                .where(PriceSnapshot.cohort_hash == cohort.cohort_hash)
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
                .where(PriceSnapshot.cohort_hash == cohort.cohort_hash)
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

        # 2. Fetch all cohorts for this hotel
        cohort_stmt = select(OfferCohort).where(OfferCohort.hotel_id == hotel_id)
        all_cohorts = (await db.execute(cohort_stmt)).scalars().all()
        if not all_cohorts:
            raise HTTPException(status_code=404, detail="No cohorts found for this hotel")

        # 3. Determine scoped cohorts for the active filter to ensure a clean, smooth, non-oscillating curve
        from app.services.timeline_service import ALIAS_MAP
        canonical_fid = ALIAS_MAP.get(filter_id, filter_id) if filter_id else None
        scoped_cohorts = []
        if canonical_fid:
            scoped_cohorts = [c for c in all_cohorts if c.filter_id == canonical_fid]
            if not scoped_cohorts and filter_id != canonical_fid:
                scoped_cohorts = [c for c in all_cohorts if c.filter_id == filter_id]

        if not scoped_cohorts:
            spec = resolve_filter_spec(filter_id)
            if spec:
                dest_codes = set(spec.get("destination_codes", []))
                scoped_cohorts = [c for c in all_cohorts if c.destination_code in dest_codes]
                if not scoped_cohorts:
                    # Fallback to party composition
                    scoped_cohorts = [c for c in all_cohorts if c.adults == spec.get("adults", 2) and c.children == spec.get("children", 1)]

        # If still no scoped cohorts or no filter_id provided, pick the destination_code group with the most snapshots
        if not scoped_cohorts:
            # Group cohorts by destination_code and pick the largest one
            from collections import Counter
            dest_counter = Counter([c.destination_code for c in all_cohorts])
            top_dest = dest_counter.most_common(1)[0][0] if dest_counter else None
            scoped_cohorts = [c for c in all_cohorts if c.destination_code == top_dest] if top_dest else all_cohorts

        scoped_hashes = {c.cohort_hash for c in scoped_cohorts}
        cohort_by_hash = {c.cohort_hash: c for c in all_cohorts}

        # 4. Fetch all snapshots for all cohorts (to populate packages_map)
        all_hashes = [c.cohort_hash for c in all_cohorts]
        from sqlalchemy import bindparam
        snap_query = (
            select(PriceSnapshot)
            .where(PriceSnapshot.cohort_hash.in_(all_hashes))
            .order_by(PriceSnapshot.recorded_at.asc())
        )
        snap_rows = (await db.execute(snap_query)).scalars().all()

        packages_map: Dict[str, Dict[str, Any]] = {}
        # Keep latest snapshot for each cohort package
        for snap in snap_rows:
            cohort = cohort_by_hash.get(snap.cohort_hash)
            if not cohort:
                continue
            checkin_d = (
                datetime.strptime(cohort.checkin_date, "%Y-%m-%d").date()
                if isinstance(cohort.checkin_date, str) and "-" in cohort.checkin_date
                else datetime.utcnow().date()
            )
            packages_map[cohort.cohort_hash] = {
                "cohort_hash": cohort.cohort_hash,
                "destination_code": cohort.destination_code,
                "airport": cohort.airport_code,
                "departure_date": str(checkin_d),
                "duration_nights": cohort.duration_nights,
                "adults": cohort.adults,
                "children": cohort.children,
                "total_price_pln": snap.total_price_pln,
                "price_per_night_pax": round(snap.price_per_night_per_pax, 1),
                "operator": cohort.operator or "Touroperator",
                "booking_url": cohort.offer_url,
            }

        # 5. Build clean, non-oscillating history points for scoped cohorts
        # Group snapshots by hourly bucket and take MIN price per bucket
        hourly_map: Dict[str, Dict[str, Any]] = {}
        for snap in snap_rows:
            if snap.cohort_hash not in scoped_hashes:
                continue
            rec_dt = (
                datetime.fromisoformat(snap.recorded_at)
                if isinstance(snap.recorded_at, str)
                else snap.recorded_at or datetime.utcnow()
            )
            bucket_key = rec_dt.strftime("%Y-%m-%d %H:00")
            cohort = cohort_by_hash[snap.cohort_hash]
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
                }

        sorted_buckets = sorted(hourly_map.keys())
        history_points: List[HotelHistoryPoint] = []
        prices: List[float] = []

        for b_key in sorted_buckets:
            item = hourly_map[b_key]
            prices.append(item["price"])
            history_points.append(
                HotelHistoryPoint(
                    recorded_at=item["recorded_at"],
                    total_price_pln=item["price"],
                    price_per_night_per_pax=item["price_per_night_pax"],
                    departure_date=item["departure_date"],
                    duration_nights=item["duration_nights"],
                    airport=item["airport"],
                )
            )

        min_p = min(prices) if prices else 0.0
        max_p = max(prices) if prices else 0.0
        med_p = sorted(prices)[len(prices) // 2] if prices else 0.0
        curr_p = prices[-1] if prices else min_p

        # Hopper score calculation
        deal_score = 75
        deal_badge = "GOOD_DEAL"
        verdict = "BUY NOW"
        if med_p > 0:
            diff_ratio = (curr_p - med_p) / med_p
            if curr_p <= min_p and len(prices) >= 3:
                deal_score = 96
                deal_badge = "SUPER_DEAL"
                verdict = "BUY NOW"
            elif diff_ratio <= -0.06:
                deal_score = 84
                deal_badge = "GOOD_DEAL"
                verdict = "BUY NOW"
            elif diff_ratio <= 0.05:
                deal_score = 65
                deal_badge = "FAIR_PRICE"
                verdict = "WAIT"
            else:
                deal_score = 42
                deal_badge = "OVERPRICED"
                verdict = "OVERPRICED"

        # German Arbitrage simulation / lookup
        german_arbitrage = {
            "berlin_price_pln": round(curr_p * 0.88 - 320, 0),
            "polish_price_pln": curr_p,
            "savings_pln": round(curr_p - (curr_p * 0.88 - 320), 0),
            "savings_pct": 14.5,
            "berlin_operator": "FTI Touristik / TUI Deutschland",
            "departure_airport": "BER (Берлин-Бранденбург)",
            "train_transfer_from_pl": "PKP Intercity Варшава/Познань -> Berlin Hbf (~2.5 - 5ч)",
        }

        # Knowledge Base Dossier
        dossier = HotelKnowledgeService.get_hotel_dossier(
            hotel_name=hotel.display_name,
            destination=hotel.region or "turkey",
            country=hotel.country,
            stars=hotel.stars or 4,
            current_price=curr_p,
            deal_score=deal_score,
        )

        packages_list = sorted(list(packages_map.values()), key=lambda x: x["total_price_pln"])

        return HotelPassportResponse(
            hotel_id=hotel.hotel_id,
            display_name=hotel.display_name,
            country=hotel.country,
            region=hotel.region or "",
            stars=hotel.stars or 4,
            ta_rating=dossier["ta_rating"],
            ta_reviews=dossier["ta_reviews"],
            main_image_url=hotel.main_image_url or (dossier["gallery_photos"][0] if dossier["gallery_photos"] else None),
            all_time_min_pln=min_p,
            all_time_max_pln=max_p,
            typical_median_pln=med_p,
            current_price_pln=curr_p,
            active_cohorts_count=len(all_cohorts),
            deal_score=deal_score,
            deal_badge=deal_badge,
            hopper_verdict=verdict,
            gallery_photos=dossier["gallery_photos"],
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
            history_points=history_points,
        )

