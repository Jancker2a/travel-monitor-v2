import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, text, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.dashboard_subscription import DashboardAlertSubscription
from app.models.watchlist import WatchlistItem
from app.models.hotel import Hotel
from app.models.cohort import OfferCohort
from app.models.price_snapshot import PriceSnapshot
from app.schemas.dashboard_subscription import (
    DashboardSubscriptionResponse,
    DashboardSubscriptionUpdateRequest,
    DashboardSubscriptionTestResponse,
)
from app.services.telegram_service import TelegramService

logger = logging.getLogger("travel_monitor_2.dashboard_alerts")


class DashboardAlertService:
    """Service for managing per-monitor / per-dashboard alert subscriptions and daily digests."""

    @classmethod
    def normalize_monitor_id(cls, monitor_id: str) -> str:
        clean = monitor_id.strip()
        if clean.startswith("filter_"):
            return clean[7:]
        return clean

    @classmethod
    async def get_subscription(
        cls,
        db: AsyncSession,
        user_id: str,
        monitor_id: str,
        default_title: Optional[str] = None,
    ) -> DashboardAlertSubscription:
        """Retrieves user subscription or creates an inactive default if none exists."""
        clean_id = cls.normalize_monitor_id(monitor_id)
        stmt = select(DashboardAlertSubscription).where(
            and_(
                DashboardAlertSubscription.user_id == user_id,
                DashboardAlertSubscription.monitor_id.in_([clean_id, f"filter_{clean_id}", monitor_id]),
            )
        )
        res = await db.execute(stmt)
        sub = res.scalars().first()

        if not sub:
            # Return uncommitted default object
            sub = DashboardAlertSubscription(
                id=uuid.uuid4().hex,
                user_id=user_id,
                monitor_id=clean_id,
                monitor_title=default_title or f"Мониторинг {clean_id}",
                is_active=False,
                notify_mode="INSTANT",
                min_drop_pct=5.0,
                min_drop_pln=None,
                min_deal_score=80,
                max_budget_pln=None,
                only_historic_low=False,
                min_ta_rating=4.0,
                preferred_airports=None,
            )
        return sub

    @classmethod
    async def save_subscription(
        cls,
        db: AsyncSession,
        user_id: str,
        monitor_id: str,
        monitor_title: str,
        data: DashboardSubscriptionUpdateRequest,
    ) -> DashboardAlertSubscription:
        """Saves or updates user alert subscription for a monitor."""
        clean_id = cls.normalize_monitor_id(monitor_id)
        stmt = select(DashboardAlertSubscription).where(
            and_(
                DashboardAlertSubscription.user_id == user_id,
                DashboardAlertSubscription.monitor_id.in_([clean_id, f"filter_{clean_id}", monitor_id]),
            )
        )
        res = await db.execute(stmt)
        sub = res.scalars().first()

        if not sub:
            sub = DashboardAlertSubscription(
                id=uuid.uuid4().hex,
                user_id=user_id,
                monitor_id=clean_id,
                monitor_title=data.monitor_title or monitor_title,
                is_active=data.is_active if data.is_active is not None else True,
                notify_mode=data.notify_mode or "INSTANT",
                min_drop_pct=data.min_drop_pct if data.min_drop_pct is not None else 5.0,
                min_drop_pln=data.min_drop_pln,
                min_deal_score=data.min_deal_score if data.min_deal_score is not None else 80,
                max_budget_pln=data.max_budget_pln,
                only_historic_low=bool(data.only_historic_low),
                min_ta_rating=data.min_ta_rating,
                preferred_airports=data.preferred_airports,
            )
            db.add(sub)
        else:
            if data.is_active is not None:
                sub.is_active = data.is_active
            if data.notify_mode is not None:
                sub.notify_mode = data.notify_mode
            if data.min_drop_pct is not None:
                sub.min_drop_pct = data.min_drop_pct
            if data.min_drop_pln is not None:
                sub.min_drop_pln = data.min_drop_pln
            if data.min_deal_score is not None:
                sub.min_deal_score = data.min_deal_score
            if data.max_budget_pln is not None:
                sub.max_budget_pln = data.max_budget_pln
            if data.only_historic_low is not None:
                sub.only_historic_low = data.only_historic_low
            if data.min_ta_rating is not None:
                sub.min_ta_rating = data.min_ta_rating
            if data.preferred_airports is not None:
                sub.preferred_airports = data.preferred_airports
            if data.monitor_title:
                sub.monitor_title = data.monitor_title

        await db.commit()
        await db.refresh(sub)
        return sub

    @classmethod
    async def list_user_subscriptions(
        cls,
        db: AsyncSession,
        user_id: str,
    ) -> List[DashboardAlertSubscription]:
        """Lists all dashboard subscriptions configured by this user."""
        stmt = (
            select(DashboardAlertSubscription)
            .where(DashboardAlertSubscription.user_id == user_id)
            .order_by(desc(DashboardAlertSubscription.updated_at))
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def send_test_dashboard_alert(
        cls,
        db: AsyncSession,
        user: User,
        monitor_id: str,
        monitor_title: Optional[str] = None,
    ) -> DashboardSubscriptionTestResponse:
        """
        Gathers the current best offer for this monitor from Neon and delivers a test alert.
        """
        chat_id = user.telegram_chat_id
        if not chat_id:
            return DashboardSubscriptionTestResponse(
                success=False,
                message="У вас не указан Telegram Chat ID. Пожалуйста, сохраните его в настройках профиля.",
            )

        clean_id = cls.normalize_monitor_id(monitor_id)
        display_title = monitor_title or f"Мониторинг {clean_id}"

        # Find best offer for this monitor from price_snapshots + offer_cohorts
        query = text("""
            SELECT 
                h.display_name,
                h.country,
                ps.total_price_pln,
                oc.checkin_date,
                oc.duration_nights,
                oc.airport_code,
                oc.offer_url,
                h.ta_rating
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.cohort_id = oc.cohort_id
            JOIN hotels h ON oc.hotel_id = h.hotel_id
            WHERE (oc.filter_id = :id1 OR oc.filter_id = :id2 OR ps.filter_id = :id1 OR ps.filter_id = :id2)
            ORDER BY ps.recorded_at DESC, ps.total_price_pln ASC
            LIMIT 1
        """)
        res = await db.execute(query, {"id1": clean_id, "id2": f"filter_{clean_id}"})
        row = res.fetchone()

        if not row:
            # Fallback to any recent hotel if specific filter hasn't finished crawl
            fallback_q = text("""
                SELECT 
                    h.display_name,
                    h.country,
                    ps.total_price_pln,
                    oc.checkin_date,
                    oc.duration_nights,
                    oc.airport_code,
                    oc.offer_url,
                    h.ta_rating
                FROM price_snapshots ps
                JOIN offer_cohorts oc ON ps.cohort_id = oc.cohort_id
                JOIN hotels h ON oc.hotel_id = h.hotel_id
                ORDER BY ps.recorded_at DESC
                LIMIT 1
            """)
            fallback_res = await db.execute(fallback_q)
            row = fallback_res.fetchone()

        if not row:
            return DashboardSubscriptionTestResponse(
                success=False,
                message=f"Для мониторинга '{display_title}' пока не накоплено предложений в базе данных.",
                offer_found=False,
            )

        hotel_name, country, price_pln, checkin_date, duration_nights, airport_code, offer_url, ta_rating = row

        # Mock drop for illustration in test alert
        mock_prev = round(price_pln * 1.12, -1)
        mock_drop_pct = round(((mock_prev - price_pln) / mock_prev) * 100, 1)
        mock_norm = round(price_pln * 1.15, -1)

        tg_res = await TelegramService.send_dashboard_alert(
            chat_id=chat_id,
            monitor_title=display_title,
            hotel_name=hotel_name,
            country=country or "Курорт",
            current_price=float(price_pln),
            previous_price=float(mock_prev),
            drop_pct=mock_drop_pct,
            deal_score=88,
            deal_badge="🔥 Hot Deal",
            dates=str(checkin_date),
            duration_nights=int(duration_nights or 7),
            airport=airport_code or "WAW",
            is_historic_low=True,
            booking_url=offer_url,
            is_test=True,
            seasonal_norm=float(mock_norm),
            archetype="LATE_DUMPER",
            urgency_text="🟢 ПОКУПАТЬ СЕЙЧАС (окно лучшей цены сезона)",
        )

        return DashboardSubscriptionTestResponse(
            success=tg_res.get("success", False),
            message=tg_res.get("message", "Тестовое уведомление отправлено"),
            offer_found=True,
            hotel_name=hotel_name,
            price_pln=float(price_pln),
            simulated=tg_res.get("simulated", False),
        )

    @classmethod
    async def send_test_daily_digest(
        cls,
        db: AsyncSession,
        user: User,
    ) -> Dict[str, Any]:
        """
        Assembles actual live metrics from Neon DB and delivers a test Daily Digest to user's Telegram.
        """
        chat_id = user.telegram_chat_id
        if not chat_id:
            return {
                "success": False,
                "message": "У вас не указан Telegram Chat ID. Сохраните его в профиле перед отправкой дайджеста.",
            }

        max_offers = user.digest_max_offers or 5
        min_deal_score = user.digest_min_deal_score or 80

        # 1. Watchlist items
        watchlist_items = []
        if user.digest_include_watchlist and user.telegram_chat_id:
            try:
                from app.services.watchlist_service import WatchlistService
                wl_res = await WatchlistService.get_user_watchlist(db, user.telegram_chat_id)
                for item in wl_res.items[:max_offers]:
                    watchlist_items.append({
                        "hotel_name": item.hotel_name,
                        "country": item.destination_code or "",
                        "current_price_pln": float(item.current_price or 0),
                        "initial_price_pln": float(item.initial_price) if item.initial_price else None,
                        "target_price_pln": float(item.target_price) if item.target_price else None,
                        "deal_score": 85,
                    })
            except Exception as e:
                logger.warning(f"Error fetching watchlist for digest: {e}")


        # 2. Top drops in database
        top_drops = []
        if user.digest_include_top_drops:
            drops_query = text("""
                WITH recent_cohorts AS (
                    SELECT 
                        cohort_id,
                        filter_id,
                        hotel_id
                    FROM offer_cohorts
                    LIMIT 200
                ),
                ranked_snaps AS (
                    SELECT 
                        ps.cohort_id,
                        ps.total_price_pln,
                        ps.recorded_at,
                        ROW_NUMBER() OVER(PARTITION BY ps.cohort_id ORDER BY ps.recorded_at DESC) as rn
                    FROM price_snapshots ps
                )
                SELECT 
                    h.display_name,
                    curr.total_price_pln as curr_price,
                    prev.total_price_pln as prev_price,
                    ROUND(((prev.total_price_pln - curr.total_price_pln) / prev.total_price_pln * 100)::numeric, 1) as drop_pct
                FROM ranked_snaps curr
                JOIN ranked_snaps prev ON curr.cohort_id = prev.cohort_id AND prev.rn = 2
                JOIN offer_cohorts oc ON curr.cohort_id = oc.cohort_id
                JOIN hotels h ON oc.hotel_id = h.hotel_id
                WHERE curr.rn = 1 AND prev.total_price_pln > curr.total_price_pln
                ORDER BY drop_pct DESC
                LIMIT :limit
            """)
            try:
                drops_res = await db.execute(drops_query, {"limit": max_offers})
                for r in drops_res.fetchall():
                    top_drops.append({
                        "hotel_name": r[0],
                        "current_price_pln": float(r[1]),
                        "previous_price_pln": float(r[2]),
                        "drop_pct": float(r[3]),
                    })
            except Exception as e:
                logger.warning(f"Could not compute top drops for digest: {e}")

        # 3. Hot Deals
        hot_deals = []
        if user.digest_include_hot_deals:
            hot_query = text("""
                SELECT 
                    h.display_name,
                    h.country,
                    ps.total_price_pln,
                    88 as deal_score
                FROM price_snapshots ps
                JOIN offer_cohorts oc ON ps.cohort_id = oc.cohort_id
                JOIN hotels h ON oc.hotel_id = h.hotel_id
                ORDER BY ps.recorded_at DESC, ps.total_price_pln ASC
                LIMIT :limit
            """)
            hot_res = await db.execute(hot_query, {"limit": max_offers})
            for r in hot_res.fetchall():
                hot_deals.append({
                    "hotel_name": r[0],
                    "country": r[1] or "",
                    "price_pln": float(r[2]),
                    "deal_score": int(r[3]),
                })

        # 4. Historic Lows
        historic_lows = []
        if user.digest_include_historic_lows and hot_deals:
            # Use top 2 lowest price hotels as historic lows for demonstration
            historic_lows = hot_deals[:2]

        return await TelegramService.send_daily_digest(
            chat_id=chat_id,
            user_name=user.full_name or user.email.split("@")[0],
            watchlist_items=watchlist_items,
            top_drops=top_drops,
            hot_deals=hot_deals,
            historic_lows=historic_lows,
            max_offers=max_offers,
            is_test=True,
        )
