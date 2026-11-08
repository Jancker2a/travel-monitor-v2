import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

import uuid
from app.config import settings
from app.database import engine, Base, get_db
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


@app.get("/api/v2/hotels/{hotel_id}/history", response_model=HotelPassportResponse)
async def get_hotel_history_passport(hotel_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieves complete Hotel Passport with all-time price history points and stats."""
    return await WatchlistService.get_hotel_passport(db, hotel_id)


# Mount built React SPA frontend if dist exists
dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if dist_dir.is_dir():
    from fastapi.staticfiles import StaticFiles
    logger.info(f"Mounting production frontend build from {dist_dir} to /")
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")

