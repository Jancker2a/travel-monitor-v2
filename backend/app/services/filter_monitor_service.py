"""
Filter Monitoring Engine for Travel Monitor 2.0.
Maintains canonical v1 filters, runs hourly automated scrapes,
tracks price drops, and allows users to register custom monitor presets.
"""
import asyncio
import logging
from datetime import datetime, timezone, date, timedelta
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import AsyncSessionLocal
from app.models.filter_monitor import FilterMonitor
from app.models.cohort import OfferCohort
from app.models.hotel import Hotel
from app.models.price_snapshot import PriceSnapshot
from app.services.live_scraper import LiveScraperService
from app.schemas.search import SearchRequest, SearchDates, SearchDuration, SearchTravelers
from app.services.canonical_monitors_data import CANONICAL_MONITORS
from app.services.site_rebuilder import SiteRebuilderService

logger = logging.getLogger("travel_monitor_2.monitors")


class FilterMonitorService:
    @classmethod
    async def init_default_monitors(cls, db: AsyncSession):
        """Ensures all canonical v1 monitors exist in database."""
        for item in CANONICAL_MONITORS:
            stmt = select(FilterMonitor).where(FilterMonitor.id == item["id"])
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if not existing:
                m = FilterMonitor(
                    id=item["id"],
                    group_id=item["group_id"],
                    title=item["title"],
                    subtitle=item["subtitle"],
                    destination=item["destination"],
                    target_url=item["target_url"],
                    is_active=True,
                    is_hourly=True,
                    created_by="system",
                )
                db.add(m)
            else:
                existing.group_id = item["group_id"]
                existing.title = item["title"]
                existing.subtitle = item["subtitle"]
                existing.destination = item["destination"]
                existing.target_url = item["target_url"]
                existing.is_active = True
                existing.is_hourly = True
        await db.commit()
        logger.info(f"Initialized {len(CANONICAL_MONITORS)} canonical v1 filter monitors.")

    @classmethod
    async def get_all_monitors(cls, db: AsyncSession) -> List[Dict[str, Any]]:
        """Returns all configured monitors grouped by category with live status."""
        stmt = select(FilterMonitor).order_by(FilterMonitor.group_id.asc(), FilterMonitor.created_at.asc())
        res = await db.execute(stmt)
        monitors = res.scalars().all()
        return [
            {
                "id": m.id,
                "group_id": m.group_id,
                "title": m.title,
                "subtitle": m.subtitle,
                "destination": m.destination,
                "target_url": m.target_url,
                "is_active": m.is_active,
                "is_hourly": m.is_hourly,
                "last_scraped_at": m.last_scraped_at.isoformat() if m.last_scraped_at else None,
                "last_offers_count": m.last_offers_count,
                "last_min_price_pln": m.last_min_price_pln,
                "last_status": m.last_status,
                "created_by": m.created_by,
            }
            for m in monitors
        ]

    @classmethod
    async def run_single_monitor(cls, db: AsyncSession, monitor_id: str) -> Dict[str, Any]:
        """Scrapes live Fly.pl offers for one specific monitor, upserts DB and records snapshots."""
        stmt = select(FilterMonitor).where(FilterMonitor.id == monitor_id)
        res = await db.execute(stmt)
        monitor = res.scalar_one_or_none()
        if not monitor:
            raise ValueError(f"Monitor '{monitor_id}' not found")

        monitor.last_status = "RUNNING"
        await db.commit()

        try:
            logger.info(f"🛰️ [Hourly Scrape] Running monitor '{monitor.title}' ({monitor.id})...")
            # 1. First attempt: Direct JSON API (multi-page, deep coverage up to 150 offers)
            raw_offers = await LiveScraperService.fetch_offers_via_api(monitor.target_url, max_offers=150)

            # 2. Second attempt: HTML parsing fallback if API returned 0
            if not raw_offers:
                html = await LiveScraperService.fetch_page_html(monitor.target_url)
                raw_offers = LiveScraperService.parse_offers_html(html or "", max_offers=150)

            if not raw_offers:
                logger.warning(f"No offers found for monitor {monitor.id}")
                monitor.last_status = "NO_OFFERS"
                monitor.last_scraped_at = datetime.now(timezone.utc)
                await db.commit()
                return {"monitor_id": monitor.id, "status": "NO_OFFERS", "offers_found": 0}

            # Resolve filter specification for adults, children, duration
            from app.services.canonical_filters import resolve_filter_spec
            spec = resolve_filter_spec(monitor.id) or {}
            adults_cnt = spec.get("adults", 2)
            children_cnt = spec.get("children", 1)
            dur_min = spec.get("duration_min", 7)
            dur_max = spec.get("duration_max", 16)
            airports_lst = spec.get("airports") or ["WAW"]

            dummy_req = SearchRequest(
                destination=monitor.destination,
                filter_id=monitor.id,
                dates=SearchDates(
                    start_date_min=date.today(),
                    start_date_max=date.today() + timedelta(days=180),
                ),
                duration=SearchDuration(min_nights=dur_min, max_nights=dur_max),
                travelers=SearchTravelers(adults=adults_cnt, children=children_cnt),
                airports=airports_lst,
            )

            saved_items = await LiveScraperService.process_and_persist_offers(db, dummy_req, raw_offers)
            prices = [item.current_offer.total_price_pln for item in saved_items if item.current_offer.total_price_pln > 0]

            monitor.last_status = "SUCCESS"
            monitor.last_scraped_at = datetime.now(timezone.utc)
            monitor.last_offers_count = len(saved_items)
            monitor.last_min_price_pln = min(prices) if prices else None
            await db.commit()

            # Synchronize HTML dashboard, Plotly charts, and hotel series
            try:
                SiteRebuilderService.record_monitor_scrape_run(monitor.id, raw_offers, monitor.last_scraped_at)
            except Exception as re_err:
                logger.warning(f"Could not update site artifacts for monitor {monitor.id}: {re_err}")

            logger.info(f"✅ Monitor '{monitor.id}' completed: {len(saved_items)} offers saved (min: {monitor.last_min_price_pln} zł)")
            return {
                "monitor_id": monitor.id,
                "status": "SUCCESS",
                "offers_found": len(saved_items),
                "min_price_pln": monitor.last_min_price_pln,
                "scraped_at": monitor.last_scraped_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error scraping monitor {monitor.id}: {e}")
            try:
                await db.rollback()
                monitor.last_status = "ERROR"
                await db.commit()
            except Exception:
                pass
            return {"monitor_id": monitor.id, "status": "ERROR", "error": str(e)}

    @classmethod
    async def run_all_hourly_monitors(cls):
        """Pass executed by background scheduler every hour for all active filters."""
        logger.info("⏰ Starting Hourly Filters Monitoring Pass across all active filters...")
        async with AsyncSessionLocal() as db:
            await cls.init_default_monitors(db)
            stmt = select(FilterMonitor.id).where(FilterMonitor.is_active == True, FilterMonitor.is_hourly == True)
            res = await db.execute(stmt)
            monitor_ids = res.scalars().all()

        results = []
        for m_id in monitor_ids:
            try:
                async with AsyncSessionLocal() as single_db:
                    r = await cls.run_single_monitor(single_db, m_id)
                    results.append(r)
            except Exception as loop_err:
                logger.error(f"Failed monitor pass for {m_id}: {loop_err}")
                results.append({"monitor_id": m_id, "status": "ERROR", "error": str(loop_err)})
            await asyncio.sleep(1.5)  # Gentle polite delay between filters

        logger.info(f"🏁 Hourly Monitoring Pass completed for {len(results)} filters.")
        return results

    @classmethod
    async def create_custom_monitor(
        cls, db: AsyncSession, monitor_id: str, title: str, subtitle: str, destination: str, target_url: str, user_id: str = "user"
    ) -> FilterMonitor:
        """Enables users to register their own custom filter for 24/7 hourly monitoring."""
        m = FilterMonitor(
            id=monitor_id,
            group_id="custom",
            title=title,
            subtitle=subtitle,
            destination=destination,
            target_url=target_url,
            is_active=True,
            is_hourly=True,
            created_by=user_id,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)
        logger.info(f"User '{user_id}' registered new custom monitor: {m.title} ({m.id})")
        return m

