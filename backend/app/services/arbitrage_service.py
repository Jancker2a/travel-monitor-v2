"""
Cross-border German Arbitrage Service for Travel Monitor 2.0.
Ported from v1 cross_border_arbitrage.py:
Compares departures from Berlin (BER) against Polish hubs (WAW, KTW, WRO, POZ)
to find price discrepancies and identify massive savings via German operators.
"""
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models.cohort import OfferCohort
from app.models.price_snapshot import PriceSnapshot
from app.models.hotel import Hotel

logger = logging.getLogger("travel_monitor_2.arbitrage")


class ArbitrageService:
    @classmethod
    async def get_arbitrage_deals(
        cls, db: AsyncSession, min_savings_pln: float = 300.0, limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Finds identical hotels and date windows where Berlin departures are significantly cheaper."""
        # 1. Fetch latest price per cohort
        subq = (
            select(
                PriceSnapshot.cohort_hash,
                PriceSnapshot.total_price_pln,
                func.row_number().over(
                    partition_by=PriceSnapshot.cohort_hash,
                    order_by=PriceSnapshot.recorded_at.desc(),
                ).label("rn"),
            )
            .subquery()
        )

        stmt = (
            select(
                OfferCohort.hotel_id,
                Hotel.display_name,
                Hotel.country,
                Hotel.stars,
                Hotel.main_image_url,
                OfferCohort.airport_code,
                OfferCohort.checkin_date,
                OfferCohort.duration_nights,
                OfferCohort.operator,
                subq.c.total_price_pln,
            )
            .join(Hotel, OfferCohort.hotel_id == Hotel.hotel_id)
            .join(subq, and_(OfferCohort.cohort_hash == subq.c.cohort_hash, subq.c.rn == 1))
        )
        res = await db.execute(stmt)
        rows = res.all()

        # Group by (hotel_id, checkin_date, duration_nights)
        grouped: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            hotel_id, name, country, stars, img, airport, checkin, nights, operator, price = r
            if not checkin or price <= 0:
                continue

            airport_clean = str(airport or "").upper()
            is_berlin = "BER" in airport_clean or "BERLIN" in airport_clean

            key = f"{hotel_id}_{checkin}_{nights}"
            if key not in grouped:
                grouped[key] = {
                    "hotel_id": hotel_id,
                    "hotel_name": name,
                    "country": country,
                    "stars": stars or 4,
                    "main_image_url": img,
                    "checkin_date": checkin,
                    "duration_nights": nights,
                    "berlin_offers": [],
                    "polish_offers": [],
                }

            entry = {"airport": airport, "price_pln": price, "operator": operator}
            if is_berlin:
                grouped[key]["berlin_offers"].append(entry)
            else:
                grouped[key]["polish_offers"].append(entry)

        deals: List[Dict[str, Any]] = []
        for key, g in grouped.items():
            if not g["berlin_offers"] or not g["polish_offers"]:
                continue

            cheapest_ber = min(g["berlin_offers"], key=lambda x: x["price_pln"])
            cheapest_pl = min(g["polish_offers"], key=lambda x: x["price_pln"])

            p_ber = cheapest_ber["price_pln"]
            p_pl = cheapest_pl["price_pln"]

            diff_pln = p_pl - p_ber
            if diff_pln >= min_savings_pln:
                savings_pct = (diff_pln / p_pl) * 100.0
                deals.append({
                    "hotel_id": g["hotel_id"],
                    "hotel_name": g["hotel_name"],
                    "country": g["country"],
                    "stars": g["stars"],
                    "main_image_url": g["main_image_url"],
                    "checkin_date": g["checkin_date"],
                    "duration_nights": g["duration_nights"],
                    "berlin_airport": cheapest_ber["airport"],
                    "berlin_price_pln": p_ber,
                    "berlin_operator": cheapest_ber["operator"],
                    "polish_airport": cheapest_pl["airport"],
                    "polish_price_pln": p_pl,
                    "polish_operator": cheapest_pl["operator"],
                    "savings_pln": round(diff_pln, 0),
                    "savings_pct": round(savings_pct, 1),
                    "verdict": f"Выгода: -{round(diff_pln):,} zł (-{savings_pct:.0f}%)",
                })

        deals.sort(key=lambda x: x["savings_pln"], reverse=True)
        return deals[:limit]
