import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger("travel_monitor_2.timeline")

# Aliases between legacy shorthand and canonical folder/monitor IDs
ALIAS_MAP = {
    "turkey_7_10": "turkey_7_10_days",
    "turkey_9_11": "turkey_9_11_days",
    "turkey_13_16": "turkey_13_16_days",
    "egypt_autumn_7_10": "egypt_autumn_2026_7_10_days",
    "egypt_autumn_13_16": "egypt_autumn_2026_13_16_days",
    "egypt_ny_dec24_2026_7_10": "egypt_ny_dec24_2026_7_10_days",
    "egypt_ny_dec28_2026_7_10": "egypt_ny_dec28_2026_7_10_days",
    "greece_7_10": "greece_7_10_days",
    "greece_13_16": "greece_13_16_days",
    "filter_cyprus_7_10": "cyprus_7_10",
    "turkey_vacation_jul18_2026": "turkey_vacation_jul18",
}


def resolve_filter_id(filter_id: str) -> str:
    if not filter_id:
        return filter_id
    if filter_id in ALIAS_MAP:
        return ALIAS_MAP[filter_id]
    if not filter_id.endswith("_days") and f"{filter_id}_days" in ALIAS_MAP.values():
        return f"{filter_id}_days"
    return filter_id


class TimelineService:
    @classmethod
    async def get_top10_timeline(
        cls,
        db: AsyncSession,
        filter_id: str,
        range_param: str = "all",
        ceiling_pln: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Computes the Top-10 cheapest offers average timeline with exact v1 mathematical parity.
        For each hourly scrape run, finds minimum price per hotel, sorts ascending,
        takes Top-10 hotels, and computes avg, min, and max price corridor.
        """
        canonical_filter_id = resolve_filter_id(filter_id)

        # Build time constraint
        time_clause = ""
        params: Dict[str, Any] = {"fid": canonical_filter_id}

        if range_param == "7d":
            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            time_clause = "AND ps.recorded_at >= :cutoff"
            params["cutoff"] = cutoff
        elif range_param == "30d":
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            time_clause = "AND ps.recorded_at >= :cutoff"
            params["cutoff"] = cutoff

        ceiling_clause = ""
        if ceiling_pln and ceiling_pln > 0:
            ceiling_clause = "AND ps.total_price_pln <= :ceiling_pln"
            params["ceiling_pln"] = ceiling_pln

        is_pg = db.bind.dialect.name == "postgresql"
        bucket_expr = (
            "to_char(ps.recorded_at, 'YYYY-MM-DD\"T\"HH24:00:00\"Z\"')"
            if is_pg
            else "substr(ps.recorded_at, 1, 13) || ':00:00Z'"
        )

        # Query all snapshots for this filter grouped by hourly run bucket and hotel
        sql = f"""
            SELECT 
                {bucket_expr} as run_time,
                h.display_name as hotel_name,
                MIN(ps.total_price_pln) as min_hotel_price
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.cohort_hash = oc.cohort_hash
            JOIN hotels h ON oc.hotel_id = h.hotel_id
            WHERE (ps.filter_id = :fid OR oc.destination_code = :fid)
              {time_clause}
              {ceiling_clause}
            GROUP BY {bucket_expr}, h.hotel_id, h.display_name
            ORDER BY run_time ASC;
        """
        res = await db.execute(text(sql), params)
        rows = res.fetchall()

        if not rows and canonical_filter_id != filter_id:
            # Fallback to literal filter_id
            params["fid"] = filter_id
            res = await db.execute(text(sql), params)
            rows = res.fetchall()

        # Group rows by hourly run_time
        runs: Dict[str, List[Tuple[str, float]]] = {}
        for row in rows:
            r_time, h_name, p_val = row[0], row[1], float(row[2])
            if r_time not in runs:
                runs[r_time] = []
            runs[r_time].append((h_name, p_val))

        timeline_points = []
        for r_time, h_list in runs.items():
            if not h_list:
                continue
            # Sort hotels by price ascending, break ties deterministically by hotel name
            h_list.sort(key=lambda x: (x[1], x[0]))
            top10 = h_list[:10]
            prices = [item[1] for item in top10]
            avg_price = round(sum(prices) / len(prices), 1)
            min_price = prices[0]
            max_price = prices[-1]

            top10_hotels = [
                {"name": item[0], "price": item[1], "position": idx + 1}
                for idx, item in enumerate(top10)
            ]
            timeline_points.append({
                "time": r_time,
                "avg_price": avg_price,
                "min_price": min_price,
                "max_price": max_price,
                "top10_hotels": top10_hotels,
            })

        # Calculate statistics summary
        stats = None
        if timeline_points:
            avg_series = [pt["avg_price"] for pt in timeline_points]
            current_avg = avg_series[-1]
            first_avg = avg_series[0]
            min_avg = min(avg_series)
            max_avg = max(avg_series)
            diff = current_avg - first_avg
            pct_diff = round((diff / first_avg) * 100, 2) if first_avg else 0.0
            trend = "DOWN" if pct_diff < -1.0 else ("UP" if pct_diff > 1.0 else "STABLE")

            stats = {
                "current_avg_top10": current_avg,
                "historical_min_avg": min_avg,
                "historical_max_avg": max_avg,
                "overall_trend": trend,
                "last_updated": timeline_points[-1]["time"],
            }

        return {
            "filter_id": filter_id,
            "range": range_param,
            "points_count": len(timeline_points),
            "timeline": timeline_points,
            "stats": stats,
        }

