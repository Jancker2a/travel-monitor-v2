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

logger = logging.getLogger("travel_monitor_2.monitors")

CANONICAL_MONITORS = [
    {
        "id": "turkey_7_10",
        "group_id": "turkey",
        "title": "Турция • 7–10 дней",
        "subtitle": "WAW/RDO • 2+1 • сбор 4–20k PLN • показ ≤10k",
        "destination": "turkey",
        "target_url": (
            "https://fly.pl/szukaj-wycieczek/?destinationLocation=39:&departureLocation=Warszawa,Warszawa+-+Radom"
            "&startDateMin=31-05-2027&startDateMax=23-06-2027&returnDate=30-06-2027&adults=2&children=10-12-2020"
            "&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=20000&order=price"
        ),
    },
    {
        "id": "turkey_9_11",
        "group_id": "turkey",
        "title": "Турция • 9–11 дней",
        "subtitle": "WAW/WMI/RDO • 2+1 • сбор 4.6–20k PLN • Все Включено",
        "destination": "turkey",
        "target_url": (
            "https://fly.pl/szukaj-wycieczek/?destinationLocation=39:&departureLocation=Warszawa,Warszawa+-+Radom,Warszawa+-+Modlin"
            "&startDateMin=31-05-2027&startDateMax=23-06-2027&returnDate=30-06-2027&adults=2&children=10-12-2020"
            "&offerTypes=accommodation_flight&categoryRating=50&durationFrom=9&durationTo=11&priceFrom=4600&priceTo=20000&order=price"
        ),
    },
    {
        "id": "turkey_13_16",
        "group_id": "turkey",
        "title": "Турция • 13–16 дней",
        "subtitle": "WAW/RDO • 2+1 • длительный отдых • 4–20k PLN",
        "destination": "turkey",
        "target_url": (
            "https://fly.pl/szukaj-wycieczek/?destinationLocation=39:&departureLocation=Warszawa,Warszawa+-+Radom"
            "&startDateMin=31-05-2027&startDateMax=23-06-2027&returnDate=30-06-2027&adults=2&children=10-12-2020"
            "&offerTypes=accommodation_flight&categoryRating=50&durationFrom=13&durationTo=16&priceFrom=4000&priceTo=20000&order=price"
        ),
    },
    {
        "id": "egypt_autumn_7_10",
        "group_id": "egypt",
        "title": "Египет • осень • 7–10 дней",
        "subtitle": "WAW/WMI/RDO • 2+1 • сбор 4–20k PLN • Красное море",
        "destination": "egypt",
        "target_url": (
            "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa,Warszawa+-+Radom,Warszawa+-+Modlin"
            "&startDateMin=10-10-2026&startDateMax=05-11-2026&returnDate=15-11-2026&adults=2&children=10-12-2020"
            "&offerTypes=accommodation_flight&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=20000&order=price"
        ),
    },
    {
        "id": "egypt_autumn_13_16",
        "group_id": "egypt",
        "title": "Египет • осень • 13–16 дней",
        "subtitle": "WAW/WMI/RDO • 2+1 • длительный отдых 13–16 дн.",
        "destination": "egypt",
        "target_url": (
            "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa,Warszawa+-+Radom,Warszawa+-+Modlin"
            "&startDateMin=10-10-2026&startDateMax=05-11-2026&returnDate=20-11-2026&adults=2&children=10-12-2020"
            "&offerTypes=accommodation_flight&durationFrom=13&durationTo=16&priceFrom=4000&priceTo=20000&order=price"
        ),
    },
    {
        "id": "greece_7_10",
        "group_id": "greece",
        "title": "Греция • 7–10 дней",
        "subtitle": "Любой аэропорт • Крит / Родос • 4–20k PLN",
        "destination": "greece",
        "target_url": (
            "https://fly.pl/szukaj-wycieczek/?destinationLocation=14:&departureLocation="
            "&startDateMin=01-06-2027&startDateMax=25-06-2027&returnDate=05-07-2027&adults=2&children=10-12-2020"
            "&offerTypes=accommodation_flight&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=20000&order=price"
        ),
    },
    {
        "id": "eb_turkey_jul27_7_10",
        "group_id": "early_booking",
        "title": "Раннее бронирование 2027 • Турция (Июль)",
        "subtitle": "Летний пик 2027 • 7–10 дн. • фиксация скидок раннего старта",
        "destination": "turkey",
        "target_url": (
            "https://fly.pl/szukaj-wycieczek/?destinationLocation=39:&departureLocation=Warszawa"
            "&startDateMin=01-07-2027&startDateMax=20-07-2027&returnDate=30-07-2027&adults=2&children=10-12-2020"
            "&offerTypes=accommodation_flight&durationFrom=7&durationTo=10&order=price"
        ),
    },
    {
        "id": "eb_egypt_aug27_7_10",
        "group_id": "early_booking",
        "title": "Раннее бронирование 2027 • Египет (Август)",
        "subtitle": "Август 2027 • 7–10 дн. • Шарм / Хургада",
        "destination": "egypt",
        "target_url": (
            "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa"
            "&startDateMin=01-08-2027&startDateMax=20-08-2027&returnDate=30-08-2027&adults=2&children=10-12-2020"
            "&offerTypes=accommodation_flight&durationFrom=7&durationTo=10&order=price"
        ),
    },
    {
        "id": "arbitrage_turkey_ber",
        "group_id": "arbitrage",
        "title": "Немецкий арбитраж • Турция (Берлин BER vs Польша)",
        "subtitle": "Вылеты из Берлина • сравнение с польскими чартерами • экономия до -35%",
        "destination": "turkey",
        "target_url": (
            "https://fly.pl/szukaj-wycieczek/?destinationLocation=39:&departureLocation=Berlin"
            "&startDateMin=31-05-2027&startDateMax=23-06-2027&returnDate=30-06-2027&adults=2&children=10-12-2020"
            "&offerTypes=accommodation_flight&durationFrom=7&durationTo=10&order=price"
        ),
    },
    {
        "id": "arbitrage_egypt_ber",
        "group_id": "arbitrage",
        "title": "Немецкий арбитраж • Египет (Берлин BER vs Польша)",
        "subtitle": "Вылеты из Берлина в Египет • немецкие туроператоры TUI/FTI/Alltours",
        "destination": "egypt",
        "target_url": (
            "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Berlin"
            "&startDateMin=10-10-2026&startDateMax=05-11-2026&returnDate=15-11-2026&adults=2&children=10-12-2020"
            "&offerTypes=accommodation_flight&durationFrom=7&durationTo=10&order=price"
        ),
    },
]


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
            # 1. First attempt: Direct JSON API (fast, robust, no JavaScript renderer required)
            raw_offers = await LiveScraperService.fetch_offers_via_api(monitor.target_url)

            # 2. Second attempt: HTML parsing fallback if API returned 0
            if not raw_offers:
                html = await LiveScraperService.fetch_page_html(monitor.target_url)
                raw_offers = LiveScraperService.parse_offers_html(html or "")

            if not raw_offers:
                logger.warning(f"No offers found for monitor {monitor.id}")
                monitor.last_status = "NO_OFFERS"
                monitor.last_scraped_at = datetime.now(timezone.utc)
                await db.commit()
                return {"monitor_id": monitor.id, "status": "NO_OFFERS", "offers_found": 0}

            # Fabricate minimal SearchRequest to feed process_and_persist_offers
            dummy_req = SearchRequest(
                destination=monitor.destination,
                filter_id=monitor.id,
                dates=SearchDates(
                    start_date_min=date.today(),
                    start_date_max=date.today() + timedelta(days=180),
                ),
                duration=SearchDuration(min_nights=7, max_nights=16),
                travelers=SearchTravelers(adults=2, children=1),
                airports=["WAW"],
            )

            saved_items = await LiveScraperService.process_and_persist_offers(db, dummy_req, raw_offers)
            prices = [item.current_offer.total_price_pln for item in saved_items if item.current_offer.total_price_pln > 0]

            monitor.last_status = "SUCCESS"
            monitor.last_scraped_at = datetime.now(timezone.utc)
            monitor.last_offers_count = len(saved_items)
            monitor.last_min_price_pln = min(prices) if prices else None
            await db.commit()

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
            monitor.last_status = "ERROR"
            await db.commit()
            return {"monitor_id": monitor.id, "status": "ERROR", "error": str(e)}

    @classmethod
    async def run_all_hourly_monitors(cls):
        """Pass executed by background scheduler every hour for all active filters."""
        logger.info("⏰ Starting Hourly Filters Monitoring Pass across all active filters...")
        async with AsyncSessionLocal() as db:
            stmt = select(FilterMonitor).where(FilterMonitor.is_active == True, FilterMonitor.is_hourly == True)
            res = await db.execute(stmt)
            monitors = res.scalars().all()

            results = []
            for m in monitors:
                r = await cls.run_single_monitor(db, m.id)
                results.append(r)
                await asyncio.sleep(2.0)  # Gentle polite delay between filters

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

