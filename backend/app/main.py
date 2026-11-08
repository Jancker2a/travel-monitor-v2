import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base, get_db
from app.schemas.search import SearchRequest, SearchResponse
from app.services.query_builder import UniversalQueryBuilder

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
    yield
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
    """Universal search across all destinations, dates, and pax combinations."""
    # Generate provider URL
    flypl_url = UniversalQueryBuilder.build_flypl_url(req)
    logger.info(f"Generated universal search query: {flypl_url}")
    
    # Placeholder response demonstrating the schema contract
    return SearchResponse(
        search_id="demo_search_001",
        cached=False,
        total_found=0,
        results=[],
    )

