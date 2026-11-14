import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

import uuid
from app.config import settings
from app.database import engine, Base, get_db, AsyncSessionLocal
from app.schemas.search import SearchRequest, SearchResponse
from app.schemas.watchlist import (
    WatchlistCreateRequest,
    WatchlistUpdateRequest,
    WatchlistItemResponse,
    WatchlistListResponse,
)
from app.schemas.hotel import HotelPassportResponse
from app.services.search_service import SearchService
from app.services.watchlist_service import WatchlistService
from app.services.scheduler import scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("travel_monitor_2")


async def _async_background_db_maintenance():
    """Runs non-blocking migrations/backfills in the background to avoid stalling uvicorn startup."""
    try:
        if engine.dialect.name == "postgresql":
            async with engine.begin() as conn:
                has_cohort_nulls = (await conn.execute(text(
                    "SELECT 1 FROM offer_cohorts WHERE filter_id IS NULL OR filter_id = '' LIMIT 1;"
                ))).scalar()
                if has_cohort_nulls:
                    await conn.execute(text("""
                        UPDATE offer_cohorts 
                        SET filter_id = destination_code 
                        WHERE (filter_id IS NULL OR filter_id = '');
                    """))
                has_nulls = (await conn.execute(text(
                    "SELECT 1 FROM price_snapshots WHERE filter_id IS NULL OR filter_id = '' LIMIT 1;"
                ))).scalar()
                if has_nulls:
                    logger.info("Backfilling filter_id for legacy price_snapshots in background...")
                    await conn.execute(text("""
                        UPDATE price_snapshots ps 
                        SET filter_id = oc.destination_code 
                        FROM offer_cohorts oc 
                        WHERE ps.cohort_id = oc.cohort_id 
                          AND (ps.filter_id IS NULL OR ps.filter_id = '');
                    """))
    except Exception as mig_err:
        logger.warning(f"Note on background column backfill: {mig_err}")

    # Enforce canonical geo consistency across all hotels (works for PostgreSQL & SQLite)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("""
                UPDATE hotels 
                SET country = 'Египет' 
                WHERE LOWER(region) IN ('сафага', 'хургада', 'марса-алам', 'макади бэй', 'шарм-эль-шейх', 'сома бэй', 'эль-гуна', 'дахаб', 'таба') 
                  AND (country IS NULL OR country != 'Египет');
            """))
            await conn.execute(text("""
                UPDATE hotels 
                SET region = 'Хургада', country = 'Египет' 
                WHERE (LOWER(display_name) LIKE '%arena beach%' OR hotel_id = 'arena-beach-resort-spa')
                  AND (region != 'Хургада' OR country != 'Египет');
            """))
            await conn.execute(text("""
                UPDATE hotels 
                SET region = 'Сафага', country = 'Египет' 
                WHERE (LOWER(display_name) LIKE '%shams safaga%' OR hotel_id = 'shams-safaga')
                  AND (region != 'Сафага' OR country != 'Египет');
            """))
            # Synchronize offer_cohorts destination_code with canonical hotel country
            await conn.execute(text("""
                UPDATE offer_cohorts
                SET destination_code = 'egypt'
                FROM hotels
                WHERE offer_cohorts.hotel_id = hotels.hotel_id
                  AND hotels.country = 'Египет'
                  AND offer_cohorts.destination_code != 'egypt';
            """))
            await conn.execute(text("""
                UPDATE offer_cohorts
                SET destination_code = 'greece'
                FROM hotels
                WHERE offer_cohorts.hotel_id = hotels.hotel_id
                  AND hotels.country = 'Греция'
                  AND offer_cohorts.destination_code != 'greece';
            """))
            await conn.execute(text("""
                UPDATE offer_cohorts
                SET destination_code = 'cyprus'
                FROM hotels
                WHERE offer_cohorts.hotel_id = hotels.hotel_id
                  AND hotels.country = 'Кипр'
                  AND offer_cohorts.destination_code != 'cyprus';
            """))
            await conn.execute(text("""
                UPDATE offer_cohorts
                SET destination_code = 'turkey'
                FROM hotels
                WHERE offer_cohorts.hotel_id = hotels.hotel_id
                  AND hotels.country = 'Турция'
                  AND offer_cohorts.destination_code != 'turkey';
            """))
            # Enforce strict party integrity on canonical 1-adult and solo filters
            await conn.execute(text("""
                UPDATE offer_cohorts
                SET adults = 1, children = 0
                WHERE filter_id IN ('egypt_sharm_dec20_28_1p', 'egypt_sharm_dec20_29_1p', 'filter_egypt_sharm_dec20_28_1p', 'filter_egypt_sharm_dec20_29_1p', 'cyprus_7_10', 'filter_cyprus_7_10')
                  AND (adults != 1 OR children != 0);
            """))
            # Ensure owner jancker2a@gmail.com is strictly ADMIN and remove test dummy accounts
            await conn.execute(text("""
                UPDATE users 
                SET role = 'ADMIN' 
                WHERE LOWER(email) = 'jancker2a@gmail.com';
                DELETE FROM users 
                WHERE email LIKE '%@travelmonitor.com' 
                   OR email LIKE '%@testmail.com' 
                   OR email LIKE '%@test.com'
                   OR email LIKE '%@example.com';
            """))
            logger.info("✅ Canonical geo consistency, cohort party integrity & admin ownership verified.")
    except Exception as geo_err:
        logger.warning(f"Note on background geo sanitization: {geo_err}")

    # Prewarm in-memory caches for high-traffic endpoints so first requests are instantaneous
    logger.info("Prewarming in-memory caches for high-traffic endpoints...")
    async with AsyncSessionLocal() as db:
        try:
            from app.services.analytics_service import AnalyticsService
            from app.services.catalog_service import CatalogService
            from app.services.oracle_service import OracleService
            from app.services.timeline_service import TimelineService
            await AnalyticsService.get_top_price_drops(db, limit=10)
            await AnalyticsService.get_offers_count_timeline(db)
            await AnalyticsService.get_airport_comparison(db, "turkey")
            await AnalyticsService.get_market_overview(db)
            await TimelineService.get_top10_timeline(db, "turkey_7_10")
            await CatalogService.get_filter_hotels(db, "turkey_7_10")
            await OracleService.get_filter_oracle(db, "turkey_7_10")
            await TimelineService.get_top10_timeline(db, "egypt_sharm_dec20_29_1p")
            await CatalogService.get_filter_hotels(db, "egypt_sharm_dec20_29_1p")
            await OracleService.get_filter_oracle(db, "egypt_sharm_dec20_29_1p")
            logger.info("✅ Cache prewarming completed successfully.")
        except Exception as e:
            logger.warning(f"Note on cache prewarming: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database tables for Travel Monitor 2.0...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Auto-migrate columns for Postgres / existing databases
            for tbl in ["offer_cohorts", "price_snapshots"]:
                try:
                    await conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS filter_id VARCHAR;"))
                except Exception:
                    pass
            try:
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_snapshot_filter_time ON price_snapshots(filter_id, recorded_at);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_snapshot_cohort_time ON price_snapshots(cohort_id, recorded_at);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_price_snapshots_rec_at ON price_snapshots(recorded_at DESC);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_cohort_filter_hotel ON offer_cohorts(filter_id, hotel_id);"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_cohort_filter_id ON offer_cohorts(filter_id);"))
            except Exception:
                pass
        logger.info("Database schema initialized successfully.")
    except Exception as ddl_err:
        logger.error(f"Non-fatal error initializing database tables: {ddl_err}")

    # Seed canonical v1 filter monitors
    try:
        async with AsyncSessionLocal() as db:
            from app.services.filter_monitor_service import FilterMonitorService
            await FilterMonitorService.init_default_monitors(db)
    except Exception as seed_err:
        logger.warning(f"Note on seeding default monitors: {seed_err}")

    # Launch background DB backfill without delaying container healthchecks
    import asyncio
    asyncio.create_task(_async_background_db_maintenance())

    # Start background scheduler only if explicitly enabled (e.g. standalone worker)
    if settings.ENABLE_BACKGROUND_SCHEDULER:
        logger.info("Starting background scheduler...")
        await scheduler.start()

    yield

    # Stop background scheduler if running
    if settings.ENABLE_BACKGROUND_SCHEDULER:
        await scheduler.stop()
    logger.info("Shutting down database connection pool...")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    description="Next-generation intelligent travel price monitor & meta-search platform",
    lifespan=lifespan,
)

from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb = traceback.format_exc()
    logger.error(f"500 ERROR on {request.url}: {exc}\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "type": type(exc).__name__, "traceback": tb.splitlines()[-10:]},
    )

# Enable CORS for Next.js / SvelteKit / mobile frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount feature routers
from app.routers import auth, dashboard_subscriptions, user_monitors
app.include_router(auth.router)
app.include_router(dashboard_subscriptions.router)
app.include_router(user_monitors.router)




@app.get("/healthz")
async def healthcheck(db: AsyncSession = Depends(get_db)):
    """Healthcheck probe for Kubernetes, Fly.io, or Render."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "service": settings.APP_NAME, "version": "2.0.0"}
    except Exception as e:
        logger.error(f"Healthcheck failed: {e}")
        raise HTTPException(status_code=503, detail="Database connectivity failure")


@app.post("/api/v2/search", response_model=SearchResponse)
async def universal_search(req: SearchRequest, db: AsyncSession = Depends(get_db)):
    """Universal search across all destinations, dates, and pax combinations
    powered by Dual-Engine architecture (DB cache + on-demand live scraper).
    """
    return await SearchService.search(db, req)


@app.post("/api/v2/watchlist", response_model=WatchlistItemResponse)
async def create_or_update_watchlist(
    req: WatchlistCreateRequest, db: AsyncSession = Depends(get_db)
):
    """Subscribes user to price drops on a specific tour cohort."""
    return await WatchlistService.add_to_watchlist(db, req)


@app.get("/api/v2/watchlist/{user_chat_id}", response_model=WatchlistListResponse)
async def get_user_watchlist(user_chat_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieves all active alerts for a user/chat ID."""
    return await WatchlistService.get_user_watchlist(db, user_chat_id)


@app.delete("/api/v2/watchlist/{watch_id}")
async def delete_watchlist_item(watch_id: str, db: AsyncSession = Depends(get_db)):
    """Unsubscribes / removes a tour cohort from user watchlist."""
    deleted = await WatchlistService.delete_watchlist_item(db, watch_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return {"status": "ok", "deleted_watch_id": watch_id}


@app.patch("/api/v2/watchlist/{watch_id}", response_model=WatchlistItemResponse)
async def update_watchlist_item(
    watch_id: str,
    req: WatchlistUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Updates target price and notification threshold settings for a watched hotel."""
    return await WatchlistService.update_watchlist_item(db, watch_id, req)


@app.post("/api/v2/watchlist/trigger-check")
async def trigger_watchlist_check():
    """Manual / webhook trigger for the background alert worker."""
    alerts_count = await scheduler.run_check_cycle()
    return {"status": "ok", "alerts_dispatched": alerts_count}


from app.services.analytics_service import AnalyticsService


@app.get("/api/v2/hotels/{hotel_id}/history", response_model=HotelPassportResponse)
async def get_hotel_history_passport(
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
    db: AsyncSession = Depends(get_db)
):
    """Retrieves complete Hotel Passport with all-time price history points and stats, dynamically synthesizing profiles for newly discovered hotels."""
    return await WatchlistService.get_hotel_passport(
        db,
        hotel_id,
        filter_id=filter_id,
        name=name,
        stars=stars,
        country=country,
        region=region,
        current_price=current_price,
        ta_rating=ta_rating,
        main_image_url=main_image_url,
        adults=adults,
        children=children,
        duration_nights=duration_nights,
    )


@app.get("/api/v2/hotels/{hotel_id}/normalized-history")
async def get_hotel_normalized_history(
    hotel_id: str,
    filter_id: Optional[str] = None,
    name: Optional[str] = None,
    stars: Optional[int] = None,
    country: Optional[str] = None,
    region: Optional[str] = None,
    current_price: Optional[float] = None,
    ta_rating: Optional[float] = None,
    main_image_url: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Retrieves normalized time series (1 adult, 8 nights benchmark) from dedicated normalized database, synthesizing on-the-fly for new hotels."""
    from app.models.normalized_snapshot import NormalizedPriceSnapshot
    from app.models.hotel import Hotel

    # Fetch hotel
    h_stmt = select(Hotel).where(Hotel.hotel_id == hotel_id)
    h_res = await db.execute(h_stmt)
    hotel = h_res.scalar_one_or_none()
    if not hotel:
        passport = await WatchlistService.get_hotel_passport(
            db,
            hotel_id,
            filter_id=filter_id,
            name=name,
            stars=stars,
            country=country,
            region=region,
            current_price=current_price,
            ta_rating=ta_rating,
            main_image_url=main_image_url,
        )
        pts = [
            {
                "recorded_at": pt.recorded_at.isoformat() if hasattr(pt.recorded_at, "isoformat") else str(pt.recorded_at),
                "normalized_price_1p_8n": pt.normalized_price_1p_8n,
                "pure_hotel_night_rate": pt.pure_hotel_night_rate,
                "flight_estimate_seat": 1400.0,
                "source_type": "on_the_fly",
                "is_crawler": False,
            }
            for pt in (passport.history_points or [])
        ]
        return {
            "hotel_id": hotel_id,
            "count": len(pts),
            "points": pts,
        }

    # Resolve related hotel aliases to aggregate complete historical benchmark
    related_ids = await WatchlistService._find_related_hotel_ids(db, hotel)

    # Fetch normalized snapshots
    stmt = (
        select(NormalizedPriceSnapshot)
        .where(NormalizedPriceSnapshot.hotel_id.in_(related_ids))
        .order_by(NormalizedPriceSnapshot.recorded_at.asc())
    )
    res = await db.execute(stmt)
    snapshots = res.scalars().all()

    points = [
        {
            "recorded_at": s.recorded_at.isoformat() if s.recorded_at else "",
            "normalized_price_1p_8n": s.normalized_price_1p_8n,
            "pure_hotel_night_rate": s.pure_hotel_night_rate,
            "flight_estimate_seat": s.flight_estimate_seat,
            "source_type": s.source_type,
            "is_crawler": s.is_crawler_standard,
        }
        for s in snapshots
    ]

    if not points:
        # Fallback: Dynamically decompose hotel's actual PriceSnapshots into normalized 1p/8n benchmark
        try:
            passport = await WatchlistService.get_hotel_passport(db, hotel.hotel_id, filter_id=filter_id)
            dest_keyword = (hotel.country or "turkey").lower()
            from app.services.cost_decomposer import CostDecomposer

            decomp_points = []
            flight_seat_bench = CostDecomposer.get_flight_benchmark(dest_keyword)
            single_factor = 1.18 if "turkey" in dest_keyword else 1.20

            for pt in (passport.history_points or []):
                if not pt.recorded_at or pt.total_price_pln <= 0:
                    continue

                if pt.normalized_price_1p_8n and pt.normalized_price_1p_8n > 1000:
                    norm_price = pt.normalized_price_1p_8n
                    pure_rate = pt.pure_hotel_night_rate or 0.0
                    seat_cost = flight_seat_bench
                else:
                    pt_ad = pt.adults if pt.adults is not None else 2
                    pt_ch = pt.children if pt.children is not None else 0
                    pt_dur = pt.duration_nights or 7
                    decomp = CostDecomposer.decompose(
                        total_price_pln=pt.total_price_pln,
                        duration_nights=pt_dur,
                        adults=pt_ad,
                        children=pt_ch,
                        destination=dest_keyword,
                    )
                    pure_rate = decomp["pure_hotel_night_per_adult"]
                    # Sanity floor: 4★/5★ AI hotel night per adult cannot be < 50 PLN
                    if pure_rate < 50.0:
                        pure_rate = max(50.0, (pt.total_price_pln * 0.40) / (pt_dur * max(1, pt_ad + pt_ch * 0.2)))
                    seat_cost = decomp["flight_seat_cost"]
                    norm_price = round(seat_cost + (8.0 * pure_rate * single_factor), 1)

                rec_str = pt.recorded_at.isoformat() if hasattr(pt.recorded_at, "isoformat") else str(pt.recorded_at)
                decomp_points.append({
                    "recorded_at": rec_str,
                    "normalized_price_1p_8n": norm_price,
                    "pure_hotel_night_rate": round(pure_rate, 1),
                    "flight_estimate_seat": round(seat_cost, 1),
                    "source_type": "decomposed_passport_snapshot",
                    "is_crawler": False,
                })
            points = decomp_points
        except Exception as e:
            logger.error(f"Error decomposing normalized history for {hotel_id}: {e}")
            points = []

    prices = [p["normalized_price_1p_8n"] for p in points if p["normalized_price_1p_8n"] > 0]
    import statistics
    current_norm = prices[-1] if prices else 0.0
    latest_pure = points[-1]["pure_hotel_night_rate"] if points else 0.0
    stats = {
        "current_normalized_pln": round(current_norm, 0),
        "pure_hotel_night_rate": round(latest_pure, 0),
        "min_normalized_pln": round(min(prices), 0) if prices else 0.0,
        "median_normalized_pln": round(statistics.median(prices), 0) if prices else 0.0,
        "max_normalized_pln": round(max(prices), 0) if prices else 0.0,
        "total_snapshots": len(points),
    }

    return {
        "hotel_id": hotel.hotel_id,
        "hotel_name": hotel.display_name,
        "country": hotel.country,
        "benchmark_label": "Эталонная цена: 1 человек • 8 ночей",
        "benchmark_explanation": (
            "Нормализованный индекс исключает искажения разных дат и количества людей. "
            "Вычисляется как: Фиксированный чартерный перелёт + (8 ночей × Чистая посуточная ставка отеля × Single Factor)."
        ),
        "stats": stats,
        "points": points,
        "history": points,
    }


@app.get("/api/v2/analytics/top-drops")
async def get_top_drops(db: AsyncSession = Depends(get_db), limit: int = 12):
    """Returns tours with the biggest price drops across the market."""
    return await AnalyticsService.get_top_price_drops(db, limit=limit)


@app.get("/api/v2/analytics/airports")
async def get_airports_comparison(db: AsyncSession = Depends(get_db), destination: str = None):
    """Compares average and minimum tour prices by departure airport."""
    return await AnalyticsService.get_airport_comparison(db, destination=destination)


@app.get("/api/v2/analytics/top10-timeline")
async def get_top10_timeline(filter_id: Optional[str] = None, destination: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Time-series of top 10 cheapest offers (avg, min, max) across historical scrape runs."""
    return await AnalyticsService.get_top10_timeline(db, filter_id=filter_id, destination=destination)


@app.get("/api/v2/analytics/offers-count-timeline")
async def get_offers_count_timeline(db: AsyncSession = Depends(get_db)):
    """Daily offers count timeline for market depth chart."""
    return await AnalyticsService.get_offers_count_timeline(db)


@app.get("/api/v2/analytics/early-booking")
async def get_early_booking(db: AsyncSession = Depends(get_db)):
    """Early Booking Advantage Score (EBAS), trajectory, and survival curves."""
    return await AnalyticsService.get_early_booking_analytics(db)


@app.get("/api/v2/analytics/overview")
async def get_market_overview(db: AsyncSession = Depends(get_db)):
    """High-level platform market counters (total hotels, cohorts, snapshots)."""
    return await AnalyticsService.get_market_overview(db)


from app.services.filter_monitor_service import FilterMonitorService
from app.services.arbitrage_service import ArbitrageService
from app.schemas.timeline import TimelineResponse
from app.services.timeline_service import TimelineService
from app.schemas.catalog import HotelCatalogResponse
from app.services.catalog_service import CatalogService
from app.services.oracle_service import OracleService


@app.get("/api/v2/filters/{filter_id}/top10-timeline", response_model=TimelineResponse)
async def get_filter_top10_timeline(
    filter_id: str,
    range: str = "all",
    ceiling_pln: Optional[float] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Computes real-time Top-10 cheapest offers timeline directly from historical database.
    Replaces static generated HTML Plotly charts with high-performance JSON API.
    """
    return await TimelineService.get_top10_timeline(
        db, filter_id=filter_id, range_param=range, ceiling_pln=ceiling_pln
    )


@app.get("/api/v2/filters/{filter_id}/oracle")
async def get_filter_market_oracle(filter_id: str, db: AsyncSession = Depends(get_db)):
    """
    AI Market Intelligence & Flight Dynamics Oracle:
    Computes market phase, charter dynamics, floor saturation, and strategic buying advice.
    """
    return await OracleService.get_filter_oracle(db, filter_id=filter_id)


@app.get("/api/v2/filters/{filter_id}/departures")
async def get_filter_departures(filter_id: str):
    """
    Active upcoming departure radar and historical late-buy cases for the active filter.
    """
    return AnalyticsService.get_filter_departures(filter_id)


@app.get("/api/v2/filters/{filter_id}/hotels", response_model=HotelCatalogResponse)
async def get_filter_hotels_catalog(
    filter_id: str,
    sort_by: str = "price",
    order: str = "asc",
    stars: Optional[int] = None,
    search: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns live hotel catalog cards for a filter with Deal Score, 24h & 7d price dynamics,
    TripAdvisor ratings, and smart badges (e.g. Historic Minimum, Price Drop).
    Replaces static hotel table and grid views.
    """
    return await CatalogService.get_filter_hotels(
        db,
        filter_id=filter_id,
        sort_by=sort_by,
        order=order,
        stars=stars,
        search_query=search,
        min_price=min_price,
        max_price=max_price,
    )


@app.get("/api/v2/monitors")
async def list_monitors(db: AsyncSession = Depends(get_db)):
    """Returns all 24/7 filter monitors with live status, offer counts, and last scrape time."""
    return await FilterMonitorService.get_all_monitors(db)


@app.post("/api/v2/monitors/{monitor_id}/run-now")
async def run_single_monitor_now(monitor_id: str, db: AsyncSession = Depends(get_db)):
    """Manually triggers an immediate scrape for a given filter monitor."""
    return await FilterMonitorService.run_single_monitor(db, monitor_id)


@app.post("/api/v2/monitors/run-all-now")
async def run_all_monitors_now(db: AsyncSession = Depends(get_db)):
    """Triggers an immediate hourly pass across all 22 active canonical monitors."""
    return await FilterMonitorService.run_all_hourly_monitors()


@app.post("/api/v2/monitors/rebuild-dashboards")
async def rebuild_dashboards_on_server(db: AsyncSession = Depends(get_db)):
    """Rebuilds HTML dashboards, hotel series, and catalog on the server from DB snapshots."""
    from app.services.site_rebuilder import SiteRebuilderService
    return await SiteRebuilderService.rebuild_all(db)


@app.post("/api/v2/monitors")
async def create_custom_monitor(data: dict, db: AsyncSession = Depends(get_db)):
    """Registers a new user-defined filter for hourly monitoring."""
    m = await FilterMonitorService.create_custom_monitor(
        db,
        monitor_id=data.get("id") or f"custom_{uuid.uuid4().hex[:8]}",
        title=data["title"],
        subtitle=data.get("subtitle", "Пользовательский фильтр"),
        destination=data.get("destination", "turkey"),
        target_url=data["target_url"],
        user_id=data.get("user_id", "user_demo_01"),
    )
    return {"status": "ok", "monitor_id": m.id, "title": m.title}


@app.get("/api/v2/arbitrage")
async def get_arbitrage_deals(
    db: AsyncSession = Depends(get_db),
    min_savings: float = 300.0,
    filter_id: Optional[str] = None,
    country: Optional[str] = None,
):
    """Compares German departures (Berlin BER) against Polish airports to find cross-border arbitrage."""
    return await ArbitrageService.get_arbitrage_deals(
        db,
        min_savings_pln=min_savings,
        filter_id=filter_id,
        country=country,
    )


# Mount static site (V1 dashboard & landing) and React SPA frontend
site_dir = Path(__file__).resolve().parents[2] / "site"
dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"

from fastapi.staticfiles import StaticFiles

if dist_dir.is_dir():
    logger.info(f"Mounting production React SPA from {dist_dir} to /app and /spa")
    app.mount("/app", StaticFiles(directory=str(dist_dir), html=True), name="frontend_app")
    app.mount("/spa", StaticFiles(directory=str(dist_dir), html=True), name="frontend_spa")

if site_dir.is_dir():
    logger.info(f"Mounting production static site from {site_dir} to /")
    app.mount("/", StaticFiles(directory=str(site_dir), html=True), name="site")
elif dist_dir.is_dir():
    logger.info(f"Mounting production frontend build from {dist_dir} to /")
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")



