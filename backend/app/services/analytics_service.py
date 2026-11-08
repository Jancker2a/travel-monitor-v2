import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger("travel_monitor_2.analytics")


class AnalyticsService:

    @classmethod
    async def get_top_price_drops(
        cls, db: AsyncSession, limit: int = 12, min_drop_pln: float = 150.0
    ) -> List[Dict[str, Any]]:
        """Returns top tours with the sharpest price drops between their latest 2 snapshots."""
        query = text("""
            SELECT c.cohort_hash, h.hotel_id, h.display_name, h.country, h.region, h.stars,
                   h.main_image_url, c.duration_nights, c.checkin_date, c.airport_code,
                   s_prev.total_price_pln as prev_price,
                   s_curr.total_price_pln as curr_price,
                   (s_prev.total_price_pln - s_curr.total_price_pln) as drop_amount,
                   ((s_prev.total_price_pln - s_curr.total_price_pln) / s_prev.total_price_pln * 100) as drop_pct,
                   c.offer_url
            FROM offer_cohorts c
            JOIN hotels h ON c.hotel_id = h.hotel_id
            JOIN price_snapshots s_curr ON s_curr.id = (
                SELECT MAX(id) FROM price_snapshots WHERE cohort_hash = c.cohort_hash
            )
            JOIN price_snapshots s_prev ON s_prev.id = (
                SELECT MAX(id) FROM price_snapshots WHERE cohort_hash = c.cohort_hash AND id < s_curr.id
            )
            WHERE (s_prev.total_price_pln - s_curr.total_price_pln) >= :min_drop
            ORDER BY drop_amount DESC
            LIMIT :lim
        """)
        res = await db.execute(query, {"min_drop": min_drop_pln, "lim": limit})
        rows = res.mappings().all()

        results = []
        for r in rows:
            results.append({
                "cohort_hash": r["cohort_hash"],
                "hotel_id": r["hotel_id"],
                "hotel_name": r["display_name"],
                "country": r["country"],
                "region": r["region"] or "",
                "stars": r["stars"] or 4,
                "main_image_url": r["main_image_url"],
                "duration_nights": r["duration_nights"],
                "departure_date": str(r["checkin_date"]),
                "airport": r["airport_code"],
                "previous_price_pln": float(r["prev_price"]),
                "current_price_pln": float(r["curr_price"]),
                "drop_amount_pln": round(float(r["drop_amount"]), 2),
                "drop_pct": round(float(r["drop_pct"]), 1),
                "booking_url": r["offer_url"],
            })
        return results

    @classmethod
    async def get_top10_timeline(
        cls, db: AsyncSession, destination: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Returns time series of top 10 cheapest offers (avg, min, max) across historical scrape runs."""
        query = text("""
            WITH ranked AS (
                SELECT strftime('%Y-%m-%d %H\\:00', recorded_at) as snap_bucket,
                       total_price_pln,
                       ROW_NUMBER() OVER (PARTITION BY strftime('%Y-%m-%d %H\\:00', recorded_at) ORDER BY total_price_pln ASC) as rn
                FROM price_snapshots
            )
            SELECT snap_bucket,
                   ROUND(AVG(total_price_pln), 0) as avg_price,
                   ROUND(MIN(total_price_pln), 0) as min_price,
                   ROUND(MAX(total_price_pln), 0) as max_price
            FROM ranked
            WHERE rn <= 10
            GROUP BY snap_bucket
            ORDER BY snap_bucket ASC
        """)
        res = await db.execute(query)
        rows = res.mappings().all()

        results = []
        for r in rows:
            bucket = str(r["snap_bucket"])
            results.append({
                "date": bucket,
                "avg_price": float(r["avg_price"]),
                "min_price": float(r["min_price"]),
                "max_price": float(r["max_price"]),
            })
        return results

    @classmethod
    async def get_airport_comparison(
        cls, db: AsyncSession, destination: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Calculates average and minimum package price grouped by departure airport."""
        filter_clause = ""
        params: Dict[str, Any] = {}
        if destination:
            filter_clause = "WHERE LOWER(c.destination_code) LIKE :dest OR LOWER(h.country) LIKE :dest"
            params["dest"] = f"%{destination.lower()}%"

        query = text(f"""
            SELECT c.airport_code,
                   COUNT(DISTINCT c.hotel_id) as hotel_count,
                   ROUND(MIN(s.total_price_pln), 0) as min_price,
                   ROUND(AVG(s.total_price_pln), 0) as avg_price,
                   ROUND(AVG(s.price_per_night_per_pax), 0) as avg_night_pax
            FROM offer_cohorts c
            JOIN hotels h ON c.hotel_id = h.hotel_id
            JOIN price_snapshots s ON s.id = (
                SELECT MAX(id) FROM price_snapshots WHERE cohort_hash = c.cohort_hash
            )
            {filter_clause}
            GROUP BY c.airport_code
            HAVING COUNT(*) >= 5
            ORDER BY avg_price ASC
        """)
        res = await db.execute(query, params)
        rows = res.mappings().all()

        results = []
        for r in rows:
            results.append({
                "airport_code": r["airport_code"],
                "hotel_count": int(r["hotel_count"]),
                "min_price_pln": float(r["min_price"]),
                "avg_price_pln": float(r["avg_price"]),
                "avg_night_pax": float(r["avg_night_pax"]),
            })
        return results

    @classmethod
    async def get_top10_timeline(
        cls, db: AsyncSession, destination: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Returns time series of top 10 cheapest offers (avg, min, max) across historical scrape runs."""
        query = text("""
            WITH ranked AS (
                SELECT strftime('%Y-%m-%d %H\\:00', recorded_at) as snap_bucket,
                       total_price_pln,
                       ROW_NUMBER() OVER (PARTITION BY strftime('%Y-%m-%d %H\\:00', recorded_at) ORDER BY total_price_pln ASC) as rn
                FROM price_snapshots
            )
            SELECT snap_bucket,
                   ROUND(AVG(total_price_pln), 0) as avg_price,
                   ROUND(MIN(total_price_pln), 0) as min_price,
                   ROUND(MAX(total_price_pln), 0) as max_price
            FROM ranked
            WHERE rn <= 10
            GROUP BY snap_bucket
            ORDER BY snap_bucket ASC
        """)
        res = await db.execute(query)
        rows = res.mappings().all()

        results = []
        for r in rows:
            bucket = str(r["snap_bucket"])
            results.append({
                "date": bucket,
                "avg_price": float(r["avg_price"]),
                "min_price": float(r["min_price"]),
                "max_price": float(r["max_price"]),
            })
        return results

    @classmethod
    async def get_market_overview(cls, db: AsyncSession) -> Dict[str, Any]:
        """Returns high-level market metrics: active hotels, cohorts, total tracked points, median price."""
        query = text("""
            SELECT 
                (SELECT COUNT(*) FROM hotels) as total_hotels,
                (SELECT COUNT(*) FROM offer_cohorts) as total_cohorts,
                (SELECT COUNT(*) FROM price_snapshots) as total_snapshots,
                (SELECT ROUND(AVG(total_price_pln), 0) FROM price_snapshots WHERE id IN (SELECT MAX(id) FROM price_snapshots GROUP BY cohort_hash)) as avg_current_price,
                (SELECT ROUND(MIN(total_price_pln), 0) FROM price_snapshots WHERE id IN (SELECT MAX(id) FROM price_snapshots GROUP BY cohort_hash)) as min_current_price
        """)
        res = await db.execute(query)
        row = res.mappings().first()
        return dict(row) if row else {}

