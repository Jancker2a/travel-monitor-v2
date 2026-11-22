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
from app.services.canonical_filters import resolve_filter_spec

logger = logging.getLogger("travel_monitor_2.dashboard_alerts")


def normalize_pax(adults: int, children: int, filter_id: Optional[str] = None, filter_title: Optional[str] = None, offer_url: Optional[str] = None) -> tuple:
    f_id = (filter_id or "").lower()
    f_title = (filter_title or "").lower()
    url = (offer_url or "").lower()

    spec = None
    if f_id:
        spec = resolve_filter_spec(f_id)
    if not spec and f_title:
        spec = resolve_filter_spec(f_title)

    if spec and "adults" in spec:
        return int(spec["adults"]), int(spec.get("children", 0))

    if any(k in f_id for k in ["1p", "cyprus_7_10", "cyprus_1p"]) or \
       any(k in f_title for k in ["1 взр", "1p", "1 взрослый", "эталон"]) or \
       "adults=1" in url or "person%5d=1" in url or "person=1" in url:
        return 1, 0

    if "adults=2" in url and "children=" not in url and "child=" not in url and "childage" not in url:
        if children > 0 and ("2+1" not in f_title and "1 реб" not in f_title and "+1" not in f_title and "2+1" not in f_id):
            return 2, 0

    return adults, children


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
    async def build_digest_payload(
        cls,
        db: AsyncSession,
        user: User,
    ) -> Dict[str, Any]:
        """Assembles live metrics from Neon DB into daily digest payload with strict deduplication and full metadata."""
        chat_id = user.telegram_chat_id
        if not chat_id:
            return {
                "success": False,
                "message": "У вас не указан Telegram Chat ID. Сохраните его в профиле перед отправкой дайджеста.",
            }

        max_offers = user.digest_max_offers or 5
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=48)
        seen_hotel_ids = set()

        # 1. Watchlist items
        watchlist_items = []
        if user.digest_include_watchlist and user.telegram_chat_id:
            try:
                from app.services.watchlist_service import WatchlistService
                wl_res = await WatchlistService.get_user_watchlist(db, user.telegram_chat_id)
                for item in wl_res.items[:max_offers]:
                    h_id = getattr(item, "hotel_id", "")
                    if h_id:
                        seen_hotel_ids.add(h_id)
                    watchlist_items.append({
                        "hotel_id": h_id,
                        "hotel_name": getattr(item, "hotel_name", "Отель"),
                        "country": getattr(item, "country", "") or "",
                        "stars": getattr(item, "stars", 4) or 4,
                        "ta_rating": getattr(item, "ta_rating", None),
                        "current_price_pln": float(item.latest_price_pln or 0),
                        "initial_price_pln": float(getattr(item, "initial_price", None) or 0) if getattr(item, "initial_price", None) else None,
                        "target_price_pln": float(item.target_price_pln) if item.target_price_pln else None,
                        "deal_score": getattr(item, "deal_score", 85) or 85,
                        "departure_date": str(getattr(item, "departure_date", "") or ""),
                        "duration_nights": int(getattr(item, "duration_nights", 7) or 7),
                        "airport_code": getattr(item, "airport", "") or "",
                        "adults": getattr(item, "adults", 2) or 2,
                        "children": getattr(item, "children", 0) or 0,
                        "drop_48h_pct": getattr(item, "drop_48h_pct", None),
                        "offer_url": getattr(item, "booking_url", None),
                        "filter_title": getattr(item, "filter_id", "") or "",
                    })
            except Exception as e:
                logger.warning(f"Error fetching watchlist for digest: {e}")

        # 2. Top drops in database (Deduplicated by hotel, min drop >= 150 zł, min pct >= 5%)
        top_drops = []
        if user.digest_include_top_drops:
            drops_query = text("""
                WITH ranked_snaps AS (
                    SELECT 
                        ps.cohort_id,
                        ps.total_price_pln,
                        ps.recorded_at,
                        ROW_NUMBER() OVER(PARTITION BY ps.cohort_id ORDER BY ps.recorded_at DESC) as rn
                    FROM price_snapshots ps
                    WHERE ps.recorded_at >= :cutoff_dt
                ),
                drops AS (
                    SELECT 
                        h.hotel_id,
                        h.display_name,
                        h.country,
                        h.region,
                        h.stars,
                        h.ta_rating,
                        curr.total_price_pln as curr_price,
                        prev.total_price_pln as prev_price,
                        (prev.total_price_pln - curr.total_price_pln) as drop_pln,
                        ((prev.total_price_pln - curr.total_price_pln) / prev.total_price_pln * 100.0) as drop_pct,
                        oc.checkin_date,
                        oc.duration_nights,
                        oc.airport_code,
                        oc.adults,
                        oc.children,
                        oc.filter_id,
                        oc.offer_url,
                        COALESCE(fm.title, oc.filter_id, '') as filter_title,
                        ROW_NUMBER() OVER(PARTITION BY oc.hotel_id ORDER BY ((prev.total_price_pln - curr.total_price_pln) / prev.total_price_pln) DESC) as hotel_rn
                    FROM ranked_snaps curr
                    JOIN ranked_snaps prev ON curr.cohort_id = prev.cohort_id AND prev.rn = 2
                    JOIN offer_cohorts oc ON curr.cohort_id = oc.cohort_id
                    JOIN hotels h ON oc.hotel_id = h.hotel_id
                    LEFT JOIN filter_monitors fm ON oc.filter_id = fm.id
                    WHERE curr.rn = 1 
                      AND prev.total_price_pln > curr.total_price_pln
                      AND ((prev.total_price_pln - curr.total_price_pln) / prev.total_price_pln) >= 0.05
                      AND (prev.total_price_pln - curr.total_price_pln) >= 150.0
                )
                SELECT 
                    hotel_id, display_name, country, region, stars, ta_rating,
                    curr_price, prev_price, drop_pln, drop_pct,
                    checkin_date, duration_nights, airport_code, adults, children,
                    filter_id, offer_url, filter_title
                FROM drops
                WHERE hotel_rn = 1
                ORDER BY drop_pct DESC
                LIMIT :limit
            """)
            try:
                drops_res = await db.execute(drops_query, {"cutoff_dt": cutoff_dt, "limit": max_offers * 2})
                for r in drops_res.fetchall():
                    h_id = r[0]
                    if h_id in seen_hotel_ids:
                        continue
                    seen_hotel_ids.add(h_id)
                    f_id = str(r[15] or "")
                    f_url = str(r[16] or "")
                    f_title = str(r[17] or "")
                    ad, ch = normalize_pax(int(r[13] or 2), int(r[14] or 0), filter_id=f_id, filter_title=f_title, offer_url=f_url)
                    top_drops.append({
                        "hotel_id": h_id,
                        "hotel_name": r[1],
                        "country": r[2] or "",
                        "region": r[3] or "",
                        "stars": int(r[4] or 4),
                        "ta_rating": float(r[5]) if r[5] else None,
                        "current_price_pln": float(r[6]),
                        "previous_price_pln": float(r[7]),
                        "drop_pln": float(r[8]),
                        "drop_pct": round(float(r[9]), 1),
                        "checkin_date": str(r[10]),
                        "duration_nights": int(r[11] or 7),
                        "airport_code": str(r[12] or ""),
                        "adults": ad,
                        "children": ch,
                        "filter_id": f_id,
                        "offer_url": f_url,
                        "filter_title": f_title,
                    })
                    if len(top_drops) >= max_offers:
                        break
            except Exception as e:
                logger.warning(f"Could not compute top drops for digest: {e}")

        # 3. Hot Deals (Distinct hotels across destinations with ta_rating >= 4 or stars >= 4)
        hot_deals = []
        if user.digest_include_hot_deals:
            hot_query = text("""
                WITH recent_offers AS (
                    SELECT 
                        h.hotel_id,
                        h.display_name,
                        h.country,
                        h.region,
                        h.stars,
                        h.ta_rating,
                        ps.total_price_pln,
                        oc.destination_code,
                        oc.checkin_date,
                        oc.duration_nights,
                        oc.airport_code,
                        oc.adults,
                        oc.children,
                        oc.filter_id,
                        oc.offer_url,
                        COALESCE(fm.title, oc.filter_id, '') as filter_title,
                        ROW_NUMBER() OVER(PARTITION BY oc.hotel_id ORDER BY ps.total_price_pln ASC) as hotel_rn
                    FROM price_snapshots ps
                    JOIN offer_cohorts oc ON ps.cohort_id = oc.cohort_id
                    JOIN hotels h ON oc.hotel_id = h.hotel_id
                    LEFT JOIN filter_monitors fm ON oc.filter_id = fm.id
                    WHERE ps.recorded_at >= :cutoff_dt
                      AND (h.stars >= 4 OR COALESCE(h.ta_rating, 0) >= 4.0)
                )
                SELECT 
                    hotel_id, display_name, country, region, stars, ta_rating,
                    total_price_pln, destination_code, checkin_date, duration_nights,
                    airport_code, adults, children, filter_id, offer_url, filter_title
                FROM recent_offers
                WHERE hotel_rn = 1
                ORDER BY destination_code ASC, total_price_pln ASC
                LIMIT :limit
            """)
            try:
                hot_res = await db.execute(hot_query, {"cutoff_dt": cutoff_dt, "limit": max_offers * 3})
                dest_counts = {}
                for r in hot_res.fetchall():
                    h_id = r[0]
                    dest = r[7] or "other"
                    if h_id in seen_hotel_ids:
                        continue
                    if dest_counts.get(dest, 0) >= 2:
                        continue
                    seen_hotel_ids.add(h_id)
                    dest_counts[dest] = dest_counts.get(dest, 0) + 1
                    
                    stars = int(r[4] or 4)
                    ta = float(r[5]) if r[5] else None
                    score = 92 if ta and ta >= 4.5 else (88 if stars >= 5 else 85)
                    f_id = str(r[13] or "")
                    f_url = str(r[14] or "")
                    f_title = str(r[15] or "")
                    ad, ch = normalize_pax(int(r[11] or 2), int(r[12] or 0), filter_id=f_id, filter_title=f_title, offer_url=f_url)
                    hot_deals.append({
                        "hotel_id": h_id,
                        "hotel_name": r[1],
                        "country": r[2] or "",
                        "region": r[3] or "",
                        "stars": stars,
                        "ta_rating": ta,
                        "price_pln": float(r[6]),
                        "deal_score": score,
                        "destination_code": dest,
                        "checkin_date": str(r[8]),
                        "duration_nights": int(r[9] or 7),
                        "airport_code": str(r[10] or ""),
                        "adults": ad,
                        "children": ch,
                        "filter_id": f_id,
                        "offer_url": f_url,
                        "filter_title": f_title,
                    })
                    if len(hot_deals) >= max_offers:
                        break
            except Exception as e:
                logger.warning(f"Could not compute hot deals for digest: {e}")

        # 4. Historic Lows (True all-time records in last 48h, min 2 historical snaps, distinct hotels)
        historic_lows = []
        if user.digest_include_historic_lows:
            low_query = text("""
                WITH cohort_min AS (
                    SELECT 
                        ps.cohort_id,
                        MIN(ps.total_price_pln) as min_price,
                        COUNT(ps.id) as snaps_count
                    FROM price_snapshots ps
                    GROUP BY ps.cohort_id
                    HAVING COUNT(ps.id) >= 2
                ),
                latest_snap AS (
                    SELECT 
                        ps.cohort_id,
                        ps.total_price_pln,
                        ROW_NUMBER() OVER(PARTITION BY ps.cohort_id ORDER BY ps.recorded_at DESC) as rn
                    FROM price_snapshots ps
                    WHERE ps.recorded_at >= :cutoff_dt
                ),
                historic_candidates AS (
                    SELECT 
                        h.hotel_id,
                        h.display_name,
                        h.country,
                        h.region,
                        h.stars,
                        h.ta_rating,
                        ls.total_price_pln,
                        oc.checkin_date,
                        oc.duration_nights,
                        oc.airport_code,
                        oc.adults,
                        oc.children,
                        oc.filter_id,
                        oc.offer_url,
                        COALESCE(fm.title, oc.filter_id, '') as filter_title,
                        ROW_NUMBER() OVER(PARTITION BY oc.hotel_id ORDER BY ls.total_price_pln ASC) as hotel_rn
                    FROM latest_snap ls
                    JOIN cohort_min cm ON ls.cohort_id = cm.cohort_id AND ls.total_price_pln <= cm.min_price
                    JOIN offer_cohorts oc ON ls.cohort_id = oc.cohort_id
                    JOIN hotels h ON oc.hotel_id = h.hotel_id
                    LEFT JOIN filter_monitors fm ON oc.filter_id = fm.id
                    WHERE ls.rn = 1
                )
                SELECT 
                    hotel_id, display_name, country, region, stars, ta_rating,
                    total_price_pln, checkin_date, duration_nights, airport_code,
                    adults, children, filter_id, offer_url, filter_title
                FROM historic_candidates
                WHERE hotel_rn = 1
                ORDER BY total_price_pln ASC
                LIMIT :limit
            """)
            try:
                low_res = await db.execute(low_query, {"cutoff_dt": cutoff_dt, "limit": max_offers * 2})
                for r in low_res.fetchall():
                    h_id = r[0]
                    if h_id in seen_hotel_ids:
                        continue
                    seen_hotel_ids.add(h_id)
                    f_id = str(r[12] or "")
                    f_url = str(r[13] or "")
                    f_title = str(r[14] or "")
                    ad, ch = normalize_pax(int(r[10] or 2), int(r[11] or 0), filter_id=f_id, filter_title=f_title, offer_url=f_url)
                    historic_lows.append({
                        "hotel_id": h_id,
                        "hotel_name": r[1],
                        "country": r[2] or "",
                        "region": r[3] or "",
                        "stars": int(r[4] or 4),
                        "ta_rating": float(r[5]) if r[5] else None,
                        "price_pln": float(r[6]),
                        "checkin_date": str(r[7]),
                        "duration_nights": int(r[8] or 7),
                        "airport_code": str(r[9] or ""),
                        "adults": ad,
                        "children": ch,
                        "filter_id": f_id,
                        "offer_url": f_url,
                        "filter_title": f_title,
                    })
                    if len(historic_lows) >= min(3, max_offers):
                        break
            except Exception as e:
                logger.warning(f"Could not compute historic lows for digest: {e}")

        # 5. Last Minute Flash Section (Urgent departures in the next 0..4 days, isolated from standard horizon)
        last_minute_deals = []
        try:
            today_d = datetime.now(timezone.utc).date()
            max_lm_d = today_d + timedelta(days=5)
            lm_query = text("""
                WITH urgent_candidates AS (
                    SELECT 
                        h.hotel_id,
                        h.display_name,
                        h.country,
                        h.region,
                        h.stars,
                        h.ta_rating,
                        ps.total_price_pln,
                        oc.destination_code,
                        oc.checkin_date,
                        oc.duration_nights,
                        oc.airport_code,
                        oc.adults,
                        oc.children,
                        oc.filter_id,
                        oc.offer_url,
                        COALESCE(fm.title, oc.filter_id, '') as filter_title,
                        ROW_NUMBER() OVER(PARTITION BY oc.hotel_id ORDER BY ps.total_price_pln ASC) as hotel_rn
                    FROM price_snapshots ps
                    JOIN offer_cohorts oc ON ps.cohort_id = oc.cohort_id
                    JOIN hotels h ON oc.hotel_id = h.hotel_id
                    LEFT JOIN filter_monitors fm ON oc.filter_id = fm.id
                    WHERE ps.recorded_at >= :cutoff_dt
                      AND oc.checkin_date >= :today_d
                      AND oc.checkin_date <= :max_lm_d
                      AND (h.stars >= 4 OR COALESCE(h.ta_rating, 0) >= 4.0)
                )
                SELECT 
                    hotel_id, display_name, country, region, stars, ta_rating,
                    total_price_pln, destination_code, checkin_date, duration_nights,
                    airport_code, adults, children, filter_id, offer_url, filter_title
                FROM urgent_candidates
                WHERE hotel_rn = 1
                ORDER BY destination_code ASC, total_price_pln ASC
                LIMIT :limit
            """)
            lm_res = await db.execute(lm_query, {
                "cutoff_dt": cutoff_dt,
                "today_d": today_d,
                "max_lm_d": max_lm_d,
                "limit": max_offers * 2
            })
            for r in lm_res.fetchall():
                h_id = r[0]
                dest = r[7] or "other"
                stars = int(r[4] or 4)
                ta = float(r[5]) if r[5] else None
                score = 95 if ta and ta >= 4.5 else (90 if stars >= 5 else 86)
                f_id = str(r[13] or "")
                f_url = str(r[14] or "")
                f_title = str(r[15] or "")
                ad, ch = normalize_pax(int(r[11] or 2), int(r[12] or 0), filter_id=f_id, filter_title=f_title, offer_url=f_url)
                last_minute_deals.append({
                    "hotel_id": h_id,
                    "hotel_name": r[1],
                    "country": r[2] or "",
                    "region": r[3] or "",
                    "stars": stars,
                    "ta_rating": ta,
                    "price_pln": float(r[6]),
                    "deal_score": score,
                    "destination_code": dest,
                    "checkin_date": str(r[8]),
                    "duration_nights": int(r[9] or 7),
                    "airport_code": str(r[10] or ""),
                    "adults": ad,
                    "children": ch,
                    "filter_id": f_id,
                    "offer_url": f_url,
                    "filter_title": f_title,
                })
                if len(last_minute_deals) >= max_offers:
                    break
        except Exception as e:
            logger.warning(f"Could not compute last-minute flash deals for digest: {e}")

        return {
            "success": True,
            "watchlist_items": watchlist_items,
            "top_drops": top_drops,
            "hot_deals": hot_deals,
            "historic_lows": historic_lows,
            "last_minute_deals": last_minute_deals,
            "max_offers": max_offers,
        }

    @classmethod
    async def send_test_daily_digest(
        cls,
        db: AsyncSession,
        user: User,
    ) -> Dict[str, Any]:
        """Delivers a test Daily Digest to user's Telegram."""
        chat_id = user.telegram_chat_id
        if not chat_id:
            return {
                "success": False,
                "message": "У вас не указан Telegram Chat ID. Сохраните его в профиле перед отправкой дайджеста.",
            }

        payload = await cls.build_digest_payload(db, user)
        if not payload.get("success", True):
            return payload

        return await TelegramService.send_daily_digest(
            chat_id=chat_id,
            user_name=user.full_name or user.email.split("@")[0],
            watchlist_items=payload["watchlist_items"],
            top_drops=payload["top_drops"],
            hot_deals=payload["hot_deals"],
            historic_lows=payload["historic_lows"],
            last_minute_deals=payload.get("last_minute_deals", []),
            max_offers=payload["max_offers"],
            is_test=True,
        )

    @classmethod
    async def dispatch_daily_digests(
        cls,
        db: AsyncSession,
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Dispatches morning daily digests to all active users with digest_enabled = True.
        Ensures each user receives at most one digest per calendar day (UTC/CET).
        """
        stmt = select(User).where(
            User.is_active == True,
            User.digest_enabled == True,
            User.telegram_chat_id != None,
            ~User.email.like("tester_%"),
        )
        res = await db.execute(stmt)
        users = res.scalars().all()
        results = []

        now_utc = datetime.now(timezone.utc)
        try:
            import zoneinfo
            tz_warsaw = zoneinfo.ZoneInfo("Europe/Warsaw")
        except Exception:
            tz_warsaw = timezone.utc

        now_warsaw = now_utc.astimezone(tz_warsaw)
        today_date = now_warsaw.date()
        warsaw_hour = now_warsaw.hour

        for user in users:
            # Check if already sent today (Warsaw calendar day)
            if user.last_digest_sent_at and not force:
                last_sent_date = user.last_digest_sent_at.astimezone(tz_warsaw).date()
                if last_sent_date == today_date:
                    logger.info(f"ℹ️ User {user.email} already received digest today ({today_date}). Skipping.")
                    continue

            # Check quiet hours if enabled (unless forced)
            if not force and user.quiet_hours_enabled:
                q_start = getattr(user, "quiet_hours_start", 23)
                q_end = getattr(user, "quiet_hours_end", 7)
                is_quiet = False
                if q_start > q_end:
                    is_quiet = warsaw_hour >= q_start or warsaw_hour < q_end
                else:
                    is_quiet = q_start <= warsaw_hour < q_end
                if is_quiet:
                    logger.info(f"⏭️ Skipping digest for {user.email}: quiet hours active ({q_start}:00-{q_end}:00). Will send on next daytime run.")
                    continue

            logger.info(f"📨 Dispatching Daily Digest to user {user.email} (Chat ID: {user.telegram_chat_id})...")
            payload = await cls.build_digest_payload(db, user)
            if not payload.get("success", True):
                results.append({"email": user.email, "success": False, "reason": payload.get("message")})
                continue

            resp = await TelegramService.send_daily_digest(
                chat_id=user.telegram_chat_id,
                user_name=user.full_name or user.email.split("@")[0],
                watchlist_items=payload["watchlist_items"],
                top_drops=payload["top_drops"],
                hot_deals=payload["hot_deals"],
                historic_lows=payload["historic_lows"],
                last_minute_deals=payload.get("last_minute_deals", []),
                max_offers=payload["max_offers"],
                is_test=False,
            )

            if resp.get("success", False) and not resp.get("simulated", False):
                user.last_digest_sent_at = now_utc
                await db.commit()
                results.append({"email": user.email, "success": True, "chat_id": user.telegram_chat_id})
                logger.info(f"✅ Daily digest successfully dispatched to {user.email}.")
            else:
                reason = resp.get("message") or resp.get("error") or "Unknown error"
                results.append({"email": user.email, "success": False, "error": reason})
                logger.warning(f"❌ Daily digest NOT delivered to {user.email}: {reason}")

        return results
