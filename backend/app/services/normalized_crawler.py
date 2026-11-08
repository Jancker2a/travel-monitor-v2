"""
Normalized Crawler Engine for Travel Monitor 2.0.
Performs background scraping of standard benchmark offers:
1 adult, 8 nights, departure date = today + 20 days across primary destinations.
Stores records in `normalized_price_snapshots` without cluttering user UI or raw cohorts.
"""
import asyncio
import logging
import urllib.parse
from datetime import date, timedelta, datetime, timezone
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.hotel import Hotel
from app.models.normalized_snapshot import NormalizedPriceSnapshot

logger = logging.getLogger("travel_monitor_2.normalized_crawler")

CRAWLER_DESTINATIONS = [
    {"name": "Турция", "code": "39", "flight_benchmark": 1200.0},
    {"name": "Египет", "code": "11", "flight_benchmark": 1250.0},
    {"name": "Греция", "code": "14", "flight_benchmark": 1300.0},
    {"name": "Испания", "code": "18", "flight_benchmark": 1350.0},
    {"name": "Кипр", "code": "10", "flight_benchmark": 1300.0},
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}


def slugify(text: str) -> str:
    import re
    text = str(text or "").lower().strip()
    text = re.sub(r"[^\w\d]+", "-", text)
    return text.strip("-") or "hotel"


class NormalizedCrawlerService:
    @classmethod
    async def run_crawler_cycle(cls, max_offers_per_dest: int = 50) -> Dict[str, Any]:
        """Runs 1 crawling pass across all primary destinations."""
        today = date.today()
        start_min = today + timedelta(days=20)
        start_max = today + timedelta(days=25)

        logger.info(
            f"🚀 [Normalized Crawler] Starting standard benchmark pass (1 pax, 8 nights, dates: {start_min} - {start_max})..."
        )

        total_collected = 0
        dest_stats = {}

        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=15.0, follow_redirects=True) as client:
            async with AsyncSessionLocal() as session:
                for dest in CRAWLER_DESTINATIONS:
                    dest_collected = await cls._crawl_destination(
                        client=client,
                        session=session,
                        dest=dest,
                        start_min=start_min,
                        start_max=start_max,
                        limit=max_offers_per_dest,
                    )
                    total_collected += dest_collected
                    dest_stats[dest["name"]] = dest_collected
                    await asyncio.sleep(1.0)  # Gentle polite delay between destinations

                await session.commit()

        logger.info(
            f"✅ [Normalized Crawler] Pass completed: {total_collected} benchmark snapshots ingested ({dest_stats})"
        )
        return {
            "total_collected": total_collected,
            "destination_breakdown": dest_stats,
            "benchmark_cohort": "1 adult, 8 nights, today+20d",
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    async def _crawl_destination(
        cls,
        client: httpx.AsyncClient,
        session: AsyncSession,
        dest: Dict[str, Any],
        start_min: date,
        start_max: date,
        limit: int,
    ) -> int:
        params = {
            "adults": 1,
            "destinationLocation[0]": dest["code"],
            "departureLocation[0]": "Warszawa",
            "durationFrom": 8,
            "durationTo": 8,
            "offerTypes[0]": "accommodation_flight",
            "startDate[min]": start_min.isoformat(),
            "startDate[max]": start_max.isoformat(),
            "pager[group]": "objects",
            "pager[orderBy][0][direction]": "asc",
            "pager[orderBy][0][field]": "price",
            "pager[page]": 1,
            "pager[size]": limit,
            "priceType": "total",
            "totalPrice": 1,
        }
        query_str = urllib.parse.urlencode(params)
        api_url = f"https://fly.pl/api/fqs/v1/offers/search?{query_str}"

        try:
            resp = await client.get(api_url)
            if resp.status_code != 200:
                logger.warning(f"Fly.pl crawler HTTP {resp.status_code} for {dest['name']}")
                return 0

            data = resp.json()
            offers = data.get("data", {}).get("offers", [])
            if not offers:
                return 0

            now = datetime.now(timezone.utc)
            flight_f = dest["flight_benchmark"]
            saved = 0

            for o in offers:
                hotel_name = o.get("name") or o.get("hotelName")
                if not hotel_name:
                    continue

                total_pln = float(o.get("total") or o.get("price") or 0)
                if total_pln <= 0:
                    continue

                hotel_id = slugify(hotel_name)

                # 1. Ensure hotel exists in catalog
                stmt = select(Hotel).where(Hotel.hotel_id == hotel_id)
                res = await session.execute(stmt)
                hotel_obj = res.scalar_one_or_none()
                if not hotel_obj:
                    hotel_obj = Hotel(
                        hotel_id=hotel_id,
                        display_name=hotel_name,
                        country=dest["name"],
                        stars=o.get("categoryRating", 40) // 10 if o.get("categoryRating") else 4,
                        main_image_url=o.get("thumbnailUrl") or "",
                    )
                    session.add(hotel_obj)
                    await session.flush()

                # 2. Compute pure hotel daily rate (H) for 8 nights
                hotel_total = max(10.0, total_pln - flight_f)
                pure_hotel_night = round(hotel_total / 8.0, 2)

                # 3. Create normalized snapshot
                norm_snap = NormalizedPriceSnapshot(
                    hotel_id=hotel_id,
                    destination_code=dest["name"].lower(),
                    recorded_at=now,
                    normalized_price_1p_8n=round(total_pln, 2),
                    pure_hotel_night_rate=pure_hotel_night,
                    flight_estimate_seat=flight_f,
                    source_type="crawler_1p_8n",
                    source_cohort_hash=None,
                    is_crawler_standard=True,
                )
                session.add(norm_snap)
                saved += 1

            return saved

        except Exception as e:
            logger.error(f"Error crawling destination {dest['name']}: {e}")
            return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(NormalizedCrawlerService.run_crawler_cycle(max_offers_per_dest=10))
