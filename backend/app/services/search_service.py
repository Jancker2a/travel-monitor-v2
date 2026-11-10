import uuid
import logging
from typing import List, Optional, Dict
from datetime import datetime, date
from collections import defaultdict
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
from app.services.cost_decomposer import CostDecomposer
from app.services.canonical_filters import resolve_filter_spec

logger = logging.getLogger("travel_monitor_2.search")


class SearchService:
    """Orchestrates the Dual-Engine Architecture:
    1. Instant DB Cache & Historical Intelligence lookup (<20ms).
    2. Seamless Live Scraper gateway when fresh data is needed.
    """

    @classmethod
    async def search(cls, db: AsyncSession, req: SearchRequest) -> SearchResponse:
        search_id = f"srch_{uuid.uuid4().hex[:10]}"
        is_interactive = not bool(req.filter_id)

        # 1. Dashboard filter cache lookup (ONLY for preset filter tabs, never for interactive search)
        if not is_interactive and not req.force_live_refresh:
            cached_items = await cls._lookup_cached_cohorts(db, req)
            if cached_items:
                logger.info(f"Search {search_id}: cache HIT ({len(cached_items)} unique hotels found)")
                return SearchResponse(
                    search_id=search_id,
                    cached=True,
                    total_found=len(cached_items),
                    results=cached_items,
                )

        # 2. Interactive Search & Force Live Refresh: ALWAYS query fresh results directly from Fly.pl JSON API
        logger.info(f"Search {search_id}: running LIVE scraper query against Fly.pl")
        flypl_url = UniversalQueryBuilder.build_flypl_url(req)

        raw_offers = await LiveScraperService.fetch_offers_via_api(flypl_url, max_offers=60)
        if not raw_offers:
            html = await LiveScraperService.fetch_page_html(flypl_url)
            raw_offers = LiveScraperService.parse_offers_html(html or "")

        if raw_offers:
            live_items = await LiveScraperService.process_and_persist_offers(db, req, raw_offers)
            # Deduplicate by hotel_id
            best_by_hotel: Dict[str, SearchHotelItem] = {}
            for item in live_items:
                hid = item.hotel_id
                if (
                    hid not in best_by_hotel
                    or item.current_offer.total_price_pln < best_by_hotel[hid].current_offer.total_price_pln
                ):
                    best_by_hotel[hid] = item
            deduped = sorted(list(best_by_hotel.values()), key=lambda x: x.current_offer.total_price_pln)
            return SearchResponse(
                search_id=search_id,
                cached=False,
                total_found=len(deduped),
                results=deduped,
            )

        # For interactive search, if Fly.pl returned 0 offers, do NOT mix in unrelated dashboard offers
        if is_interactive:
            logger.info(f"Search {search_id}: Live search returned 0 offers for {flypl_url}")
            return SearchResponse(
                search_id=search_id,
                cached=False,
                total_found=0,
                results=[],
            )

        # 3. Fallback for dashboard filters only
        fallback_items = await cls._lookup_cached_cohorts(db, req)
        return SearchResponse(
            search_id=search_id,
            cached=True if fallback_items else False,
            total_found=len(fallback_items),
            results=fallback_items,
        )

    @classmethod
    async def _lookup_cached_cohorts(
        cls, db: AsyncSession, req: SearchRequest, limit: int = 500
    ) -> List[SearchHotelItem]:
        dest_keyword = req.destination.lower() if req.destination else ""
        country_name = (
            "Египет" if "egypt" in dest_keyword
            else "Турция" if "turkey" in dest_keyword
            else "Греция" if "greece" in dest_keyword
            else "Кипр" if "cyprus" in dest_keyword
            else "Испания" if "spain" in dest_keyword
            else req.destination.capitalize() if req.destination else ""
        )

        conditions = []

        # 1. Target canonical filter if specified
        spec = resolve_filter_spec(req.filter_id)
        if spec:
            conditions.append(OfferCohort.destination_code.in_(spec["destination_codes"]))
            conditions.append(OfferCohort.adults == spec["adults"])
            conditions.append(OfferCohort.children == spec["children"])
            if spec.get("airports"):
                airport_conds = [OfferCohort.airport_code.ilike(f"%{a}%") for a in spec["airports"]]
                conditions.append(or_(*airport_conds))
        else:
            # Custom / interactive search mode
            if req.duration and req.duration.min_nights:
                conditions.append(
                    OfferCohort.duration_nights.between(req.duration.min_nights, req.duration.max_nights)
                )
            if req.travelers:
                conditions.append(OfferCohort.adults == req.travelers.adults)
                conditions.append(OfferCohort.children == req.travelers.children)
            if dest_keyword:
                conditions.append(
                    or_(
                        OfferCohort.destination_code.ilike(f"%{dest_keyword}%"),
                        Hotel.country == country_name,
                    )
                )
            if req.airports:
                airport_conds = []
                for a in req.airports:
                    a_lower = a.lower()
                    if a_lower in ["waw", "wmi", "rdo", "warszawa", "warsaw"]:
                        airport_conds.extend([
                            OfferCohort.airport_code.ilike("%warszawa%"),
                            OfferCohort.airport_code.ilike("%radom%"),
                            OfferCohort.airport_code.ilike("%modlin%"),
                            OfferCohort.airport_code.ilike("%okęcie%"),
                        ])
                    else:
                        airport_conds.append(OfferCohort.airport_code.ilike(f"%{a}%"))
                if airport_conds:
                    conditions.append(or_(*airport_conds))

        stmt = (
            select(OfferCohort, Hotel)
            .join(Hotel, OfferCohort.hotel_id == Hotel.hotel_id)
        )
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        cohort_rows = result.all()

        if not cohort_rows and not spec and dest_keyword:
            # Only broad fallback for free-text search when no canonical spec is matched
            broad_stmt = (
                select(OfferCohort, Hotel)
                .join(Hotel, OfferCohort.hotel_id == Hotel.hotel_id)
                .where(
                    and_(
                        OfferCohort.adults == (req.travelers.adults if req.travelers else 2),
                        OfferCohort.children == (req.travelers.children if req.travelers else 0),
                        or_(
                            OfferCohort.destination_code.ilike(f"%{dest_keyword}%"),
                            Hotel.country == country_name,
                        ),
                    )
                )
                .limit(limit)
            )
            cohort_rows = (await db.execute(broad_stmt)).all()

        if not cohort_rows:
            return []

        # Batched retrieval of price snapshots to eliminate N+1 latency
        cohort_ids = [c.cohort_id for c, _ in cohort_rows]
        snaps_by_cohort = defaultdict(list)
        snap_stmt = (
            select(PriceSnapshot)
            .where(PriceSnapshot.cohort_id.in_(cohort_ids))
            .order_by(PriceSnapshot.recorded_at.desc())
        )
        all_snaps = (await db.execute(snap_stmt)).scalars().all()
        for s in all_snaps:
            if len(snaps_by_cohort[s.cohort_id]) < 20:
                snaps_by_cohort[s.cohort_id].append(s)

        items: List[SearchHotelItem] = []
        for cohort, hotel in cohort_rows:
            snaps = snaps_by_cohort.get(cohort.cohort_id, [])
            if not snaps:
                continue

            latest_snap = snaps[0]
            price_history = [s.total_price_pln for s in snaps]
            sparkline = list(reversed(price_history))
            hist_min = min(price_history)
            hist_median = sorted(price_history)[len(price_history) // 2]
            curr_price = latest_snap.total_price_pln

            # Intelligence logic via canonical V1 deal score engine
            price_diff_ratio = (curr_price - hist_median) / hist_median if hist_median > 0 else 0.0

            deal_score = 65
            deal_badge = "FAIR_PRICE"
            verdict = "WAIT"
            recom = "Стандартная рыночная цена. Возможны колебания."

            if snaps:
                import pandas as pd
                from app.services.hotel_deal_score import compute_hotel_deal_metrics

                df_hist = pd.DataFrame([
                    {"scraped_at": s.recorded_at, "price": s.total_price_pln}
                    for s in snaps
                ])
                deal_metrics = compute_hotel_deal_metrics(
                    df_hist,
                    latest_price=curr_price,
                    time_col="scraped_at",
                    price_col="price",
                    ta_rating=hotel.ta_rating or 4.5,
                    ta_review_count=hotel.ta_reviews or 0,
                )
                deal_score = int(deal_metrics.get("deal_score", 65))
                if deal_score >= 85:
                    deal_badge = "SUPER_DEAL"
                    verdict = "BUY NOW"
                    recom = f"Абсолютно выгодное предложение! Deal Score: {deal_score}/100"
                elif deal_score >= 80:
                    deal_badge = "GOOD_DEAL"
                    verdict = "BUY NOW"
                    recom = f"Отличная цена, ниже типичного уровня. Deal Score: {deal_score}/100"
                elif deal_score < 45:
                    deal_badge = "OVERPRICED"
                    verdict = "OVERPRICED"
                    recom = f"Цена завышена относительно истории. Deal Score: {deal_score}/100"
                else:
                    deal_badge = "FAIR_PRICE"
                    verdict = "WAIT"
                    recom = "Стандартная рыночная цена. Возможны колебания."

            intelligence = HotelIntelligence(
                deal_score=deal_score,
                deal_badge=deal_badge,
                hopper_verdict=verdict,
                hopper_confidence=0.88 if len(price_history) >= 5 else 0.65,
                recommendation=recom,
                drop_48h_pct=round(price_diff_ratio * 100, 1),
                historic_min_pln=hist_min,
                typical_median_pln=hist_median,
                german_arbitrage_diff_pln=None,
            )

            checkin_d = (
                cohort.checkin_date
                if isinstance(cohort.checkin_date, date)
                else datetime.strptime(str(cohort.checkin_date)[:10], "%Y-%m-%d").date()
                if cohort.checkin_date
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

            # Decompose cost and derive normalized 1 pax / 8 nights benchmark
            decomp = CostDecomposer.decompose(
                total_price_pln=curr_price,
                duration_nights=cohort.duration_nights,
                adults=cohort.adults,
                children=cohort.children,
                destination=dest_keyword,
            )
            pure_night = round(decomp["pure_hotel_night_per_adult"], 1)
            norm_bench = round(
                decomp["flight_seat_cost"]
                + (8.0 * pure_night * (1.18 if "turkey" in dest_keyword else 1.20)),
                0,
            )

            item = SearchHotelItem(
                hotel_id=hotel.hotel_id,
                hotel_name=hotel.display_name,
                stars=hotel.stars or 4,
                region=hotel.region or "",
                country=hotel.country,
                main_image_url=hotel.main_image_url,
                ta_rating=hotel.ta_rating,
                ta_reviews=hotel.ta_reviews,
                specs=hotel.specs,
                current_offer=current_offer,
                intelligence=intelligence,
                history_sparkline=sparkline,
                normalized_benchmark_1p_8n=norm_bench,
                pure_hotel_night_pln=pure_night,
            )
            items.append(item)

        # Group by hotel_id so each hotel appears ONCE with its lowest price offer
        best_by_hotel: Dict[str, SearchHotelItem] = {}
        for item in items:
            hid = item.hotel_id
            if hid not in best_by_hotel or item.current_offer.total_price_pln < best_by_hotel[hid].current_offer.total_price_pln:
                best_by_hotel[hid] = item

        unique_hotels = list(best_by_hotel.values())
        unique_hotels.sort(key=lambda x: x.current_offer.total_price_pln)
        return unique_hotels
