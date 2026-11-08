import uuid
import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc

from app.models.hotel import Hotel
from app.models.cohort import OfferCohort
from app.models.price_snapshot import PriceSnapshot
from app.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchHotelItem,
    OfferSummary,
    HotelIntelligence,
)
from app.services.live_scraper import LiveScraperService
from app.services.query_builder import UniversalQueryBuilder

logger = logging.getLogger("travel_monitor_2.search")


class SearchService:
    """Orchestrates the Dual-Engine Architecture:
    1. Instant DB Cache & Historical Intelligence lookup (<20ms).
    2. Seamless Live Scraper gateway when fresh data is needed.
    """

    @classmethod
    async def search(cls, db: AsyncSession, req: SearchRequest) -> SearchResponse:
        search_id = f"srch_{uuid.uuid4().hex[:10]}"
        
        # 1. DB Cache Lookup
        if not req.force_live_refresh:
            cached_items = await cls._lookup_cached_cohorts(db, req)
            if cached_items:
                logger.info(f"Search {search_id}: cache HIT ({len(cached_items)} hotels found)")
                return SearchResponse(
                    search_id=search_id,
                    cached=True,
                    total_found=len(cached_items),
                    results=cached_items,
                )

        # 2. Live Scraper Fallback / Refresh
        logger.info(f"Search {search_id}: cache MISS or refresh requested -> triggering live scraper")
        flypl_url = UniversalQueryBuilder.build_flypl_url(req)
        
        html = await LiveScraperService.fetch_page_html(flypl_url)
        raw_offers = LiveScraperService.parse_offers_html(html or "")
        
        if raw_offers:
            live_items = await LiveScraperService.process_and_persist_offers(db, req, raw_offers)
            return SearchResponse(
                search_id=search_id,
                cached=False,
                total_found=len(live_items),
                results=live_items,
            )

        # 3. Fallback: return best available cached records if live scraping was empty
        fallback_items = await cls._lookup_cached_cohorts(db, req)
        return SearchResponse(
            search_id=search_id,
            cached=True if fallback_items else False,
            total_found=len(fallback_items),
            results=fallback_items,
        )

    @classmethod
    async def _lookup_cached_cohorts(
        cls, db: AsyncSession, req: SearchRequest, limit: int = 50
    ) -> List[SearchHotelItem]:
        dest_keyword = req.destination.lower()
        country_name = (
            "Египет" if "egypt" in dest_keyword
            else "Турция" if "turkey" in dest_keyword
            else "Греция" if "greece" in dest_keyword
            else "Кипр" if "cyprus" in dest_keyword
            else "Испания" if "spain" in dest_keyword
            else req.destination.capitalize()
        )

        # Query cohorts matching criteria
        conditions = [
            OfferCohort.duration_nights.between(req.duration.min_nights, req.duration.max_nights),
            or_(
                OfferCohort.destination_code.ilike(f"%{dest_keyword}%"),
                Hotel.country == country_name,
            ),
        ]

        # Flexible date range filter
        if req.dates.start_date_min and req.dates.start_date_max:
            conditions.append(
                OfferCohort.checkin_date.between(
                    req.dates.start_date_min.isoformat(),
                    req.dates.start_date_max.isoformat(),
                )
            )

        stmt = (
            select(OfferCohort, Hotel)
            .join(Hotel, OfferCohort.hotel_id == Hotel.hotel_id)
            .where(and_(*conditions))
            .limit(limit)
        )
        result = await db.execute(stmt)
        cohort_rows = result.all()

        if not cohort_rows:
            # Broaden filter slightly to return matching destination & duration if dates are outside sample range
            broad_stmt = (
                select(OfferCohort, Hotel)
                .join(Hotel, OfferCohort.hotel_id == Hotel.hotel_id)
                .where(
                    and_(
                        OfferCohort.duration_nights.between(req.duration.min_nights, req.duration.max_nights),
                        or_(
                            OfferCohort.destination_code.ilike(f"%{dest_keyword}%"),
                            Hotel.country == country_name,
                        ),
                    )
                )
                .limit(limit)
            )
            cohort_rows = (await db.execute(broad_stmt)).all()

        items: List[SearchHotelItem] = []
        for cohort, hotel in cohort_rows:
            # Fetch latest price snapshot for this cohort
            snap_stmt = (
                select(PriceSnapshot)
                .where(PriceSnapshot.cohort_hash == cohort.cohort_hash)
                .order_by(PriceSnapshot.recorded_at.desc())
                .limit(20)
            )
            snaps = (await db.execute(snap_stmt)).scalars().all()
            if not snaps:
                continue

            latest_snap = snaps[0]
            price_history = [s.total_price_pln for s in snaps]
            sparkline = list(reversed(price_history))
            hist_min = min(price_history)
            hist_median = sorted(price_history)[len(price_history) // 2]
            curr_price = latest_snap.total_price_pln

            # Intelligence logic
            price_diff_ratio = (curr_price - hist_median) / hist_median if hist_median > 0 else 0.0

            if curr_price <= hist_min and len(price_history) >= 3:
                deal_score = 95
                deal_badge = "SUPER_DEAL"
                verdict = "BUY NOW"
                recom = f"Абсолютный исторический минимум! Скидка от медианы: {abs(price_diff_ratio) * 100:.1f}%"
            elif price_diff_ratio <= -0.08:
                deal_score = 82
                deal_badge = "GOOD_DEAL"
                verdict = "BUY NOW"
                recom = f"Отличная цена, ниже типичного уровня на {abs(price_diff_ratio) * 100:.0f}%."
            elif price_diff_ratio <= 0.05:
                deal_score = 65
                deal_badge = "FAIR_PRICE"
                verdict = "WAIT"
                recom = "Стандартная рыночная цена. Возможны колебания."
            else:
                deal_score = 40
                deal_badge = "OVERPRICED"
                verdict = "OVERPRICED"
                recom = f"Цена завышена на {price_diff_ratio * 100:.0f}% относительно обычного тарифа."

            intelligence = HotelIntelligence(
                deal_score=deal_score,
                deal_badge=deal_badge,
                hopper_verdict=verdict,
                hopper_confidence=0.88 if len(price_history) >= 5 else 0.65,
                recommendation=recom,
                drop_48h_pct=round(-price_diff_ratio * 100, 1) if price_diff_ratio < 0 else 0.0,
                historic_min_pln=hist_min,
                typical_median_pln=hist_median,
                german_arbitrage_diff_pln=None,
            )

            checkin_d = (
                datetime.strptime(cohort.checkin_date, "%Y-%m-%d").date()
                if isinstance(cohort.checkin_date, str) and "-" in cohort.checkin_date
                else datetime.utcnow().date()
            )

            current_offer = OfferSummary(
                cohort_hash=cohort.cohort_hash,
                total_price_pln=curr_price,
                price_per_night_pax=round(latest_snap.price_per_night_per_pax, 2),
                departure_date=checkin_d,
                duration_nights=cohort.duration_nights,
                airport=cohort.airport_code,
                operator=cohort.operator or "Touroperator",
                booking_url=cohort.offer_url,
            )

            item = SearchHotelItem(
                hotel_id=hotel.hotel_id,
                hotel_name=hotel.display_name,
                stars=hotel.stars or 4,
                region=hotel.region or "",
                country=hotel.country,
                main_image_url=hotel.main_image_url,
                current_offer=current_offer,
                intelligence=intelligence,
                history_sparkline=sparkline,
            )
            items.append(item)

        # Sort by total price ascending
        items.sort(key=lambda x: x.current_offer.total_price_pln)
        return items

