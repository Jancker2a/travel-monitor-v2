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
        cls, db: AsyncSession, hotel_id: str
    ) -> HotelPassportResponse:
        # Fetch Hotel
        h_stmt = select(Hotel).where(Hotel.hotel_id == hotel_id)
        hotel = (await db.execute(h_stmt)).scalar_one_or_none()
        if not hotel:
            raise HTTPException(status_code=404, detail="Hotel not found")

        # Fetch all snapshots for this hotel across all cohorts
        snap_stmt = (
            select(PriceSnapshot, OfferCohort)
            .join(OfferCohort, PriceSnapshot.cohort_hash == OfferCohort.cohort_hash)
            .where(OfferCohort.hotel_id == hotel_id)
            .order_by(PriceSnapshot.recorded_at.asc())
        )
        snap_rows = (await db.execute(snap_stmt)).all()

        history_points: List[HotelHistoryPoint] = []
        prices: List[float] = []

        cohorts_set = set()
        for snap, cohort in snap_rows:
            cohorts_set.add(cohort.cohort_hash)
            prices.append(snap.total_price_pln)

            rec_dt = (
                datetime.fromisoformat(snap.recorded_at)
                if isinstance(snap.recorded_at, str)
                else snap.recorded_at or datetime.utcnow()
            )
            checkin_d = (
                datetime.strptime(cohort.checkin_date, "%Y-%m-%d").date()
                if isinstance(cohort.checkin_date, str) and "-" in cohort.checkin_date
                else datetime.utcnow().date()
            )

            history_points.append(
                HotelHistoryPoint(
                    recorded_at=rec_dt,
                    total_price_pln=snap.total_price_pln,
                    price_per_night_per_pax=snap.price_per_night_per_pax,
                    departure_date=checkin_d,
                    duration_nights=cohort.duration_nights,
                    airport=cohort.airport_code,
                )
            )

        min_p = min(prices) if prices else 0.0
        max_p = max(prices) if prices else 0.0
        med_p = sorted(prices)[len(prices) // 2] if prices else 0.0

        return HotelPassportResponse(
            hotel_id=hotel.hotel_id,
            display_name=hotel.display_name,
            country=hotel.country,
            region=hotel.region or "",
            stars=hotel.stars or 4,
            ta_rating=hotel.ta_rating,
            ta_reviews=hotel.ta_reviews or 0,
            main_image_url=hotel.main_image_url,
            all_time_min_pln=min_p,
            all_time_max_pln=max_p,
            typical_median_pln=med_p,
            active_cohorts_count=len(cohorts_set),
            history_points=history_points,
        )

