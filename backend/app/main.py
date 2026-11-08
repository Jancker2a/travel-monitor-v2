import logging
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database tables for Travel Monitor 2.0...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialized successfully.")

    # Seed canonical v1 filter monitors
    async with AsyncSessionLocal() as db:
        from app.services.filter_monitor_service import FilterMonitorService
        await FilterMonitorService.init_default_monitors(db)

    # Start background scheduler
    await scheduler.start()

    yield

    # Stop background scheduler
    await scheduler.stop()
    logger.info("Shutting down database connection pool...")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    description="Next-generation intelligent travel price monitor & meta-search platform",
    lifespan=lifespan,
)

# Enable CORS for Next.js / SvelteKit / mobile frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/api/v2/watchlist/trigger-check")
async def trigger_watchlist_check():
    """Manual / webhook trigger for the background alert worker."""
    alerts_count = await scheduler.run_check_cycle()
    return {"status": "ok", "alerts_dispatched": alerts_count}


from app.services.analytics_service import AnalyticsService


@app.get("/api/v2/hotels/{hotel_id}/history", response_model=HotelPassportResponse)
async def get_hotel_history_passport(hotel_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieves complete Hotel Passport with all-time price history points and stats (Raw exact cohorts)."""
    return await WatchlistService.get_hotel_passport(db, hotel_id)


@app.get("/api/v2/hotels/{hotel_id}/normalized-history")
async def get_hotel_normalized_history(hotel_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieves normalized time series (1 adult, 8 nights benchmark) from dedicated normalized database."""
    from app.models.normalized_snapshot import NormalizedPriceSnapshot
    from app.models.hotel import Hotel

    # Fetch hotel
    h_stmt = select(Hotel).where(Hotel.hotel_id == hotel_id)
    h_res = await db.execute(h_stmt)
    hotel = h_res.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    # Fetch normalized snapshots
    stmt = (
        select(NormalizedPriceSnapshot)
        .where(NormalizedPriceSnapshot.hotel_id == hotel_id)
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

    prices = [p["normalized_price_1p_8n"] for p in points if p["normalized_price_1p_8n"] > 0]
    import statistics
    stats = {
        "min_normalized_pln": min(prices) if prices else 0.0,
        "median_normalized_pln": statistics.median(prices) if prices else 0.0,
        "max_normalized_pln": max(prices) if prices else 0.0,
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


@app.get("/api/v2/analytics/overview")
async def get_market_overview(db: AsyncSession = Depends(get_db)):
    """High-level platform market counters (total hotels, cohorts, snapshots)."""
    return await AnalyticsService.get_market_overview(db)


from app.services.filter_monitor_service import FilterMonitorService
from app.services.arbitrage_service import ArbitrageService


@app.get("/api/v2/monitors")
async def list_monitors(db: AsyncSession = Depends(get_db)):
    """Returns all 24/7 filter monitors with live status, offer counts, and last scrape time."""
    return await FilterMonitorService.get_all_monitors(db)


@app.post("/api/v2/monitors/{monitor_id}/run-now")
async def run_single_monitor_now(monitor_id: str, db: AsyncSession = Depends(get_db)):
    """Manually triggers an immediate scrape for a given filter monitor."""
    return await FilterMonitorService.run_single_monitor(db, monitor_id)


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
async def get_arbitrage_deals(db: AsyncSession = Depends(get_db), min_savings: float = 300.0):
    """Compares German departures (Berlin BER) against Polish airports to find cross-border arbitrage."""
    return await ArbitrageService.get_arbitrage_deals(db, min_savings_pln=min_savings)


# Mount built React SPA frontend if dist exists
dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if dist_dir.is_dir():
    from fastapi.staticfiles import StaticFiles
    logger.info(f"Mounting production frontend build from {dist_dir} to /")
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")

