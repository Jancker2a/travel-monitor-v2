import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger("travel_monitor_2.timeline")

_TIMELINE_CACHE: Dict[Tuple[str, str, Optional[float]], Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 1800  # 30 minutes in-memory cache

# Aliases between legacy shorthand and canonical folder/monitor IDs
ALIAS_MAP = {
    "turkey_7_10": "turkey_7_10_days",
    "turkey_9_11": "turkey_9_11_days",
    "turkey_13_16": "turkey_13_16_days",
    "egypt_7_10": "7_10_days",
    "egypt_7_10_days": "7_10_days",
    "filter_egypt_7_10": "7_10_days",
    "filter_egypt_7_10_days": "7_10_days",
    "egypt_13_16": "13_16_days",
    "egypt_13_16_days": "13_16_days",
    "filter_egypt_13_16": "13_16_days",
    "filter_egypt_13_16_days": "13_16_days",
    "filter_7_10_days": "7_10_days",
    "filter_13_16_days": "13_16_days",
    "egypt_autumn_7_10": "egypt_autumn_2026_7_10_days",
    "egypt_autumn_13_16": "egypt_autumn_2026_13_16_days",
    "egypt_autumn_2026_7_10": "egypt_autumn_2026_7_10_days",
    "egypt_autumn_2026_13_16": "egypt_autumn_2026_13_16_days",
    "egypt_ny_dec24_2026_7_10": "egypt_ny_dec24_2026_7_10_days",
    "egypt_ny_dec28_2026_7_10": "egypt_ny_dec28_2026_7_10_days",
    "greece_7_10": "greece_7_10_days",
    "greece_13_16": "greece_13_16_days",
    "filter_cyprus_7_10": "cyprus_7_10",
    "turkey_vacation_jul18_2026": "turkey_vacation_jul18",
}

# Strict historical cutoffs for retired/archived seasonal filters to prevent
# live scrapers or accidental late runs from corrupting historical series.
ARCHIVED_FILTER_CUTOFFS: Dict[str, str] = {
    "egypt_autumn_2026_13_16_days": "2026-10-18T23:59:59Z",
    "filter_egypt_autumn_2026_13_16_days": "2026-10-18T23:59:59Z",
    "egypt_autumn_13_16": "2026-10-18T23:59:59Z",
    "filter_egypt_autumn_13_16": "2026-10-18T23:59:59Z",
    "egypt_autumn_2026_7_10_days": "2026-10-19T23:59:59Z",
    "filter_egypt_autumn_2026_7_10_days": "2026-10-19T23:59:59Z",
    "egypt_autumn_7_10": "2026-10-19T23:59:59Z",
    "filter_egypt_autumn_7_10": "2026-10-19T23:59:59Z",
    "turkey_vacation_jul18_2026": "2026-07-25T23:59:59Z",
    "turkey_vacation_jul18": "2026-07-25T23:59:59Z",
    "filter_turkey_vacation_jul18_2026": "2026-07-25T23:59:59Z",
}


def resolve_filter_id(filter_id: str) -> str:
    if not filter_id:
        return ""
    clean = filter_id.lower().strip()
    if clean.startswith("filter_"):
        clean = clean[7:]
    if clean in ALIAS_MAP:
        clean = ALIAS_MAP[clean]
    if clean.startswith("filter_"):
        clean = clean[7:]
    if not clean.endswith("_days") and f"{clean}_days" in ALIAS_MAP.values():
        clean = f"{clean}_days"
    return clean


def get_all_filter_id_variants(filter_id: str) -> List[str]:
    if not filter_id:
        return []
    variants = set()
    raw = filter_id.strip()
    variants.add(raw)
    if raw.startswith("filter_"):
        variants.add(raw[7:])
    else:
        variants.add(f"filter_{raw}")

    canonical = resolve_filter_id(raw)
    variants.add(canonical)
    if canonical.startswith("filter_"):
        variants.add(canonical[7:])
    else:
        variants.add(f"filter_{canonical}")

    for k, v in ALIAS_MAP.items():
        if raw in (k, v) or canonical in (k, v):
            variants.add(k)
            variants.add(v)
            variants.add(f"filter_{k}")
            variants.add(f"filter_{v}")

    return list(variants)


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
        canonical_fid = resolve_filter_id(filter_id)
        cache_key = (canonical_fid, range_param, ceiling_pln)
        now_ts = time.time()
        if cache_key in _TIMELINE_CACHE:
            c_time, c_data = _TIMELINE_CACHE[cache_key]
            if now_ts - c_time < _CACHE_TTL_SECONDS:
                return c_data

        fids = get_all_filter_id_variants(filter_id)

        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False

        # Build time constraint
        time_clause = ""
        params: Dict[str, Any] = {"fids": fids}

        if range_param == "7d":
            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=7)
            time_clause = "AND ps.recorded_at >= :cutoff"
            params["cutoff"] = cutoff_dt if is_pg else cutoff_dt.isoformat()
        elif range_param == "30d":
            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=30)
            time_clause = "AND ps.recorded_at >= :cutoff"
            params["cutoff"] = cutoff_dt if is_pg else cutoff_dt.isoformat()

        ceiling_clause = ""
        if ceiling_pln and ceiling_pln > 0:
            ceiling_clause = "AND ps.total_price_pln <= :ceiling_pln"
            params["ceiling_pln"] = ceiling_pln

        archive_clause = ""
        archive_cutoff = None
        for v in [filter_id, canonical_fid] + fids:
            if v in ARCHIVED_FILTER_CUTOFFS:
                archive_cutoff = ARCHIVED_FILTER_CUTOFFS[v]
                break
        if archive_cutoff:
            cutoff_dt = datetime.fromisoformat(archive_cutoff.replace("Z", "+00:00"))
            archive_clause = "AND ps.recorded_at <= :archive_cutoff"
            params["archive_cutoff"] = cutoff_dt if is_pg else archive_cutoff

        bucket_expr = (
            "to_char(ps.recorded_at, 'YYYY-MM-DD\"T\"HH24:00:00\"Z\"')"
            if is_pg
            else "substr(ps.recorded_at, 1, 13) || ':00:00Z'"
        )

        join_col = "cohort_id"
        if not is_pg:
            try:
                pragma_res = await db.execute(text("PRAGMA table_info(price_snapshots)"))
                pragma_cols = {r[1] for r in pragma_res.fetchall()}
                if "cohort_hash" in pragma_cols:
                    join_col = "cohort_hash"
            except Exception:
                pass

        filter_expr = "ps.filter_id = ANY(:fids)" if is_pg else "ps.filter_id IN :fids"

        # Query Top-10 cheapest hotels per hourly run using CTE for high performance
        sql = f"""
            WITH hotel_runs AS (
                SELECT 
                    {bucket_expr} as run_time,
                    oc.hotel_id,
                    MIN(ps.total_price_pln) as min_hotel_price
                FROM price_snapshots ps
                JOIN offer_cohorts oc ON ps.{join_col} = oc.{join_col}
                WHERE {filter_expr}
                  {time_clause}
                  {ceiling_clause}
                  {archive_clause}
                GROUP BY {bucket_expr}, oc.hotel_id
            ),
            ranked AS (
                SELECT 
                    run_time,
                    hotel_id,
                    min_hotel_price,
                    ROW_NUMBER() OVER (PARTITION BY run_time ORDER BY min_hotel_price ASC) as rn
                FROM hotel_runs
            )
            SELECT 
                r.run_time,
                h.display_name as hotel_name,
                r.min_hotel_price,
                r.rn
            FROM ranked r
            JOIN hotels h ON r.hotel_id = h.hotel_id
            WHERE r.rn <= 10
            ORDER BY r.run_time ASC, r.rn ASC;
        """
        stmt = text(sql)
        if not is_pg:
            from sqlalchemy import bindparam
            stmt = stmt.bindparams(bindparam("fids", expanding=True))

        res = await db.execute(stmt, params)
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
            # Skip incomplete scrape runs that have fewer than 3 hotels when substantial history exists,
            # preventing distorted spikes in the Top-10 average curve.
            if len(h_list) < 3 and len(runs) >= 5:
                continue
            top10 = h_list[:10]
            prices = [item[1] for item in top10]
            avg_price = round(sum(prices) / len(prices), 1)
            min_price = prices[0]
            max_price = prices[-1]

            top10_hotels = [
                {"name": item[0], "price": item[1], "position": idx + 1}
                for idx, item in enumerate(top10[:3])
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

        res = {
            "filter_id": filter_id,
            "range": range_param,
            "points_count": len(timeline_points),
            "timeline": timeline_points,
            "stats": stats,
        }
        _TIMELINE_CACHE[cache_key] = (now_ts, res)
        return res

