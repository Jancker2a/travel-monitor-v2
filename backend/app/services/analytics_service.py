import logging
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone, date
import statistics
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, bindparam

logger = logging.getLogger("travel_monitor_2.analytics")

_TOP_DROPS_CACHE: Dict[Tuple[int, float], Tuple[float, List[Dict[str, Any]]]] = {}
_AIRPORT_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
_TOP10_ANALYTICS_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
_OFFERS_COUNT_CACHE: Optional[Tuple[float, List[Dict[str, Any]]]] = None
_MARKET_OVERVIEW_CACHE: Optional[Tuple[float, Dict[str, Any]]] = None
_EB_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_FILTER_ANALYTICS_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_FILTER_DEPARTURES_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_SEASONALITY_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_ANALYTICS_CACHE_TTL = 300.0  # 5 minutes cache


class AnalyticsService:

    @classmethod
    async def get_top_price_drops(
        cls, db: AsyncSession, limit: int = 12, min_drop_pln: float = 150.0
    ) -> List[Dict[str, Any]]:
        """Returns top tours with the sharpest price drops between their latest 2 snapshots."""
        cache_key = (limit, min_drop_pln)
        now_ts = time.time()
        if cache_key in _TOP_DROPS_CACHE:
            c_time, c_data = _TOP_DROPS_CACHE[cache_key]
            if now_ts - c_time < _ANALYTICS_CACHE_TTL:
                return c_data

        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False
        cutoff_expr = "NOW() - INTERVAL '48 hours'" if is_pg else "datetime('now', '-48 hours')"

        query = text(f"""
            WITH recent_snaps AS (
                SELECT ps.cohort_id, ps.total_price_pln, ps.recorded_at,
                       ROW_NUMBER() OVER (PARTITION BY ps.cohort_id ORDER BY ps.recorded_at DESC) as rn
                FROM price_snapshots ps
                WHERE ps.recorded_at >= {cutoff_expr}
            ),
            latest_two AS (
                SELECT 
                    c1.cohort_id,
                    c1.total_price_pln as curr_price,
                    c2.total_price_pln as prev_price,
                    (c2.total_price_pln - c1.total_price_pln) as drop_amount,
                    ((c2.total_price_pln - c1.total_price_pln) / c2.total_price_pln * 100) as drop_pct
                FROM recent_snaps c1
                JOIN recent_snaps c2 ON c1.cohort_id = c2.cohort_id AND c2.rn = 2
                WHERE c1.rn = 1 AND (c2.total_price_pln - c1.total_price_pln) >= :min_drop
            )
            SELECT lt.*, c.cohort_hash, c.duration_nights, c.checkin_date, c.airport_code, c.offer_url,
                   h.hotel_id, h.display_name, h.country, h.region, h.stars, h.main_image_url
            FROM latest_two lt
            JOIN offer_cohorts c ON lt.cohort_id = c.cohort_id
            JOIN hotels h ON c.hotel_id = h.hotel_id
            ORDER BY lt.drop_amount DESC
            LIMIT :lim;
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
        _TOP_DROPS_CACHE[cache_key] = (now_ts, results)
        return results

    @classmethod
    async def get_top10_timeline(
        cls, db: AsyncSession, filter_id: Optional[str] = None, destination: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Returns time series of top 10 cheapest offers (avg, min, max) strictly scoped to the active filter/cohorts."""
        from app.services.canonical_filters import resolve_filter_spec
        from sqlalchemy import bindparam

        cache_key = f"{filter_id or ''}_{destination or ''}"
        now_ts = time.time()
        if cache_key in _TOP10_ANALYTICS_CACHE:
            c_time, c_data = _TOP10_ANALYTICS_CACHE[cache_key]
            if now_ts - c_time < _ANALYTICS_CACHE_TTL:
                return c_data

        spec = resolve_filter_spec(filter_id)
        is_user_mon = bool(filter_id and (filter_id.startswith("monitor_") or filter_id.startswith("user_")))
        if spec:
            dest_codes = list(spec["destination_codes"])
        elif is_user_mon:
            dest_codes = []
        elif destination:
            dest_lower = destination.lower()
            if "турц" in dest_lower or "turkey" in dest_lower:
                dest_codes = ["filter_turkey_7_10_days", "filter_7_10_days"]
            elif "егип" in dest_lower or "egypt" in dest_lower:
                dest_codes = ["filter_eb_egypt_oct27_7_10", "filter_eb_egypt_jul27_7_10", "filter_egypt_autumn_2026_7_10_days"]
            elif "грец" in dest_lower or "greece" in dest_lower:
                dest_codes = ["filter_greece_7_10_days", "filter_eb_greece_jul27_7_10"]
            elif "кипр" in dest_lower or "cyprus" in dest_lower:
                dest_codes = ["filter_cyprus_7_10"]
            else:
                dest_codes = ["filter_turkey_7_10_days", "filter_7_10_days"]
        else:
            dest_codes = ["filter_turkey_7_10_days", "filter_7_10_days"]

        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False
        date_expr = "TO_CHAR(s.recorded_at, 'YYYY-MM-DD HH24:00')" if is_pg else "strftime('%Y-%m-%d %H:00', s.recorded_at)"

        if is_user_mon:
            query = text(f"""
                WITH hotel_hourly_min AS (
                    SELECT 
                        {date_expr} as snap_bucket,
                        c.hotel_id,
                        MIN(s.total_price_pln) as hotel_min_price
                    FROM price_snapshots s
                    JOIN offer_cohorts c ON s.cohort_id = c.cohort_id
                    WHERE s.filter_id = :fid
                    GROUP BY {date_expr}, c.hotel_id
                ),
                ranked_top10 AS (
                    SELECT 
                        snap_bucket,
                        hotel_min_price,
                        ROW_NUMBER() OVER (PARTITION BY snap_bucket ORDER BY hotel_min_price ASC) as rn
                    FROM hotel_hourly_min
                )
                SELECT 
                    snap_bucket,
                    AVG(hotel_min_price) as avg_price,
                    MIN(hotel_min_price) as min_price,
                    MAX(hotel_min_price) as max_price
                FROM ranked_top10
                WHERE rn <= 10
                GROUP BY snap_bucket
                ORDER BY snap_bucket ASC
            """)
            res = await db.execute(query, {"fid": filter_id})
        else:
            query = text(f"""
                WITH hotel_hourly_min AS (
                    SELECT 
                        {date_expr} as snap_bucket,
                        c.hotel_id,
                        MIN(s.total_price_pln) as hotel_min_price
                    FROM price_snapshots s
                    JOIN offer_cohorts c ON s.cohort_id = c.cohort_id
                    WHERE c.destination_code IN :dest_codes
                    GROUP BY {date_expr}, c.hotel_id
                ),
                ranked_top10 AS (
                    SELECT 
                        snap_bucket,
                        hotel_min_price,
                        ROW_NUMBER() OVER (PARTITION BY snap_bucket ORDER BY hotel_min_price ASC) as rn
                    FROM hotel_hourly_min
                )
                SELECT 
                    snap_bucket,
                    AVG(hotel_min_price) as avg_price,
                    MIN(hotel_min_price) as min_price,
                    MAX(hotel_min_price) as max_price
                FROM ranked_top10
                WHERE rn <= 10
                GROUP BY snap_bucket
                ORDER BY snap_bucket ASC
            """).bindparams(bindparam("dest_codes", expanding=True))
            res = await db.execute(query, {"dest_codes": dest_codes})
        rows = res.mappings().all()

        results = []
        for r in rows:
            bucket = str(r["snap_bucket"])
            results.append({
                "date": bucket,
                "avg_price": round(float(r["avg_price"]), 0) if r["avg_price"] is not None else 0.0,
                "min_price": round(float(r["min_price"]), 0) if r["min_price"] is not None else 0.0,
                "max_price": round(float(r["max_price"]), 0) if r["max_price"] is not None else 0.0,
            })
        _TOP10_ANALYTICS_CACHE[cache_key] = (now_ts, results)
        return results

    @classmethod
    async def get_airport_comparison(
        cls, db: AsyncSession, destination: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Calculates average and minimum package price grouped by departure airport using indexed filter queries."""
        dest_clean = (destination or "all").lower().strip()
        cache_key = dest_clean
        now_ts = time.time()
        if cache_key in _AIRPORT_CACHE:
            c_time, c_data = _AIRPORT_CACHE[cache_key]
            if now_ts - c_time < _ANALYTICS_CACHE_TTL:
                return c_data

        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False
        cutoff_expr = "NOW() - INTERVAL '48 hours'" if is_pg else "datetime('now', '-48 hours')"
        join_col = "cohort_id"

        from app.services.timeline_service import get_all_filter_id_variants
        fids = get_all_filter_id_variants(dest_clean) if destination else []

        if fids:
            f_clause = "s.filter_id = ANY(:fids)" if is_pg else "s.filter_id IN :fids"
            query = text(f"""
                SELECT c.airport_code,
                       COUNT(DISTINCT c.hotel_id) as hotel_count,
                       MIN(s.total_price_pln) as min_price,
                       AVG(s.total_price_pln) as avg_price,
                       AVG(s.price_per_night_per_pax) as avg_night_pax
                FROM price_snapshots s
                JOIN offer_cohorts c ON s.{join_col} = c.{join_col}
                WHERE {f_clause}
                  AND s.recorded_at >= {cutoff_expr}
                GROUP BY c.airport_code
                HAVING COUNT(*) >= 3
                ORDER BY avg_price ASC
            """)
            if not is_pg:
                query = query.bindparams(bindparam("fids", expanding=True))
            res = await db.execute(query, {"fids": fids})
        else:
            filter_clause = ""
            params: Dict[str, Any] = {}
            if destination:
                filter_clause = "AND (LOWER(c.destination_code) LIKE :dest OR LOWER(h.country) LIKE :dest)"
                params["dest"] = f"%{destination.lower()}%"
            query = text(f"""
                SELECT c.airport_code,
                       COUNT(DISTINCT c.hotel_id) as hotel_count,
                       MIN(s.total_price_pln) as min_price,
                       AVG(s.total_price_pln) as avg_price,
                       AVG(s.price_per_night_per_pax) as avg_night_pax
                FROM price_snapshots s
                JOIN offer_cohorts c ON s.{join_col} = c.{join_col}
                JOIN hotels h ON c.hotel_id = h.hotel_id
                WHERE s.recorded_at >= {cutoff_expr}
                {filter_clause}
                GROUP BY c.airport_code
                HAVING COUNT(*) >= 3
                ORDER BY avg_price ASC
            """)
            res = await db.execute(query, params)

        rows = res.mappings().all()

        from app.services.normalization import normalize_airport_code
        grouped_airports: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            code = normalize_airport_code(r["airport_code"])
            h_cnt = int(r["hotel_count"] or 0)
            min_p = float(r["min_price"]) if r["min_price"] is not None else 0.0
            avg_p = float(r["avg_price"]) if r["avg_price"] is not None else 0.0
            avg_np = float(r["avg_night_pax"]) if r["avg_night_pax"] is not None else 0.0
            if code not in grouped_airports:
                grouped_airports[code] = {
                    "airport_code": code,
                    "hotel_count": h_cnt,
                    "min_price_pln": min_p,
                    "weighted_avg_sum": avg_p * max(1, h_cnt),
                    "weighted_np_sum": avg_np * max(1, h_cnt),
                    "weight": max(1, h_cnt),
                }
            else:
                g = grouped_airports[code]
                g["hotel_count"] += h_cnt
                if min_p > 0 and (g["min_price_pln"] <= 0 or min_p < g["min_price_pln"]):
                    g["min_price_pln"] = min_p
                w = max(1, h_cnt)
                g["weighted_avg_sum"] += avg_p * w
                g["weighted_np_sum"] += avg_np * w
                g["weight"] += w

        results = []
        for g in grouped_airports.values():
            w = max(1, g["weight"])
            results.append({
                "airport_code": g["airport_code"],
                "hotel_count": g["hotel_count"],
                "min_price_pln": round(g["min_price_pln"], 0),
                "avg_price_pln": round(g["weighted_avg_sum"] / w, 0),
                "avg_night_pax": round(g["weighted_np_sum"] / w, 0),
            })
        results.sort(key=lambda x: x["avg_price_pln"])
        _AIRPORT_CACHE[cache_key] = (now_ts, results)
        return results

    @classmethod
    async def get_offers_count_timeline(cls, db: AsyncSession) -> List[Dict[str, Any]]:
        """Returns daily count of unique tracked offers for the offers count timeline."""
        global _OFFERS_COUNT_CACHE
        now_ts = time.time()
        if _OFFERS_COUNT_CACHE is not None:
            c_time, c_data = _OFFERS_COUNT_CACHE
            if now_ts - c_time < 600.0:
                return c_data

        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False
        day_expr = "TO_CHAR(recorded_at, 'YYYY-MM-DD')" if is_pg else "strftime('%Y-%m-%d', recorded_at)"
        cutoff_expr = "NOW() - INTERVAL '60 days'" if is_pg else "datetime('now', '-60 days')"

        query = text(f"""
            SELECT {day_expr} as day, COUNT(DISTINCT cohort_id) as count
            FROM price_snapshots
            WHERE recorded_at >= {cutoff_expr}
            GROUP BY {day_expr}
            ORDER BY day ASC
        """)
        res = await db.execute(query)
        rows = res.mappings().all()
        results = [{"day": str(r["day"]), "count": int(r["count"])} for r in rows]
        _OFFERS_COUNT_CACHE = (now_ts, results)
        return results

    @staticmethod
    def _parse_dt(val: Any) -> Optional[datetime]:
        if not val:
            return None
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        try:
            s = str(val).replace("Z", "+00:00").replace(" ", "T")
            if "+" not in s and "-" not in s[10:]:
                s += "+00:00"
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _parse_date(val: Any) -> Optional[date]:
        if not val:
            return None
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        try:
            return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
        except Exception:
            return None

    @classmethod
    async def get_early_booking_analytics(
        cls, db: AsyncSession, filter_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculates real DB-backed Early Booking Advantage Score (EBAS), price trajectory & cohort survival."""
        cache_key = filter_id or "__all__"
        now_ts = time.time()
        if cache_key in _EB_CACHE:
            c_time, c_data = _EB_CACHE[cache_key]
            if now_ts - c_time < _ANALYTICS_CACHE_TTL:
                return c_data

        from app.services.timeline_service import resolve_filter_id, get_all_filter_id_variants

        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False
        join_col = "cohort_id"
        fids = get_all_filter_id_variants(resolve_filter_id(filter_id)) if filter_id else []

        where_filter = ("WHERE (" + ("ps.filter_id = ANY(:fids)" if is_pg else "ps.filter_id IN :fids") + ") ") if fids else ""
        sql = f"""
            SELECT oc.{join_col} as cid,
                   oc.checkin_date,
                   ps.recorded_at,
                   ps.total_price_pln
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.{join_col} = oc.{join_col}
            {where_filter}
            {"AND" if where_filter else "WHERE"} oc.checkin_date IS NOT NULL
              AND ps.total_price_pln > 0
            ORDER BY ps.recorded_at DESC
            LIMIT 40000
        """
        stmt = text(sql)
        params: Dict[str, Any] = {}
        if fids:
            params["fids"] = fids
            if not is_pg:
                stmt = stmt.bindparams(bindparam("fids", expanding=True))

        res = await db.execute(stmt, params)
        rows = res.fetchall()

        bucket_order = [
            "Early Bird (>120d)",
            "First Minute (60-120d)",
            "Mid (30-60d)",
            "Late (14-30d)",
            "Last Minute (7-14d)",
            "Panic Dump (≤7d)",
        ]
        bucket_prices: Dict[str, List[float]] = {b: [] for b in bucket_order}
        cohort_min_lead: Dict[str, int] = {}
        cohort_max_lead: Dict[str, int] = {}
        cohort_checkin: Dict[str, date] = {}
        cohort_first_last: Dict[str, Tuple[datetime, float, datetime, float]] = {}
        ref_date: Optional[date] = None

        for cid, c_date_raw, rec_raw, price_raw in rows:
            dt = cls._parse_dt(rec_raw)
            cd = cls._parse_date(c_date_raw)
            p = float(price_raw or 0.0)
            if not dt or not cd or p <= 0:
                continue
            if ref_date is None or dt.date() > ref_date:
                ref_date = dt.date()
            lead = (cd - dt.date()).days
            if lead < 0 or lead > 400:
                continue
            key = str(cid)
            cohort_checkin[key] = cd
            if key not in cohort_min_lead or lead < cohort_min_lead[key]:
                cohort_min_lead[key] = lead
            if key not in cohort_max_lead or lead > cohort_max_lead[key]:
                cohort_max_lead[key] = lead

            prev = cohort_first_last.get(key)
            if not prev:
                cohort_first_last[key] = (dt, p, dt, p)
            else:
                f_dt, f_p, l_dt, l_p = prev
                if dt < f_dt:
                    f_dt, f_p = dt, p
                if dt > l_dt:
                    l_dt, l_p = dt, p
                cohort_first_last[key] = (f_dt, f_p, l_dt, l_p)

            if lead > 120:
                bucket_prices["Early Bird (>120d)"].append(p)
            elif lead >= 60:
                bucket_prices["First Minute (60-120d)"].append(p)
            elif lead >= 30:
                bucket_prices["Mid (30-60d)"].append(p)
            elif lead >= 14:
                bucket_prices["Late (14-30d)"].append(p)
            elif lead >= 7:
                bucket_prices["Last Minute (7-14d)"].append(p)
            else:
                bucket_prices["Panic Dump (≤7d)"].append(p)

        total_cohorts = len(cohort_first_last)
        if total_cohorts < 5:
            out = {
                "has_data": False,
                "filter_id": filter_id,
                "summary": {
                    "ebas_score": 50.0,
                    "verdict": "INSUFFICIENT_DATA",
                    "title": "Недостаточно длинной истории для расчёта EBAS",
                    "description": f"По этому фильтру зафиксировано {total_cohorts} когорт. Для расчёта ценовой траектории от раннего бронирования к вылету требуется история по разным горизонтам дат.",
                    "total_cohorts": total_cohorts,
                    "lm_delta_pct": 0.0,
                    "sold_out_risk_pct": 0.0,
                },
                "trajectory": {"x": [], "y": []},
                "survival": {"x": [], "y": []},
            }
            _EB_CACHE[cache_key] = (now_ts, out)
            return out

        non_empty_buckets = [b for b in bucket_order if len(bucket_prices[b]) >= 3]
        traj_x: List[str] = []
        traj_y: List[float] = []
        base_med = None
        if non_empty_buckets:
            base_med = statistics.median(bucket_prices[non_empty_buckets[0]])
            for b in non_empty_buckets:
                med_b = statistics.median(bucket_prices[b])
                delta_b = round(((med_b - base_med) / base_med) * 100.0, 1) if base_med > 0 else 0.0
                traj_x.append(b)
                traj_y.append(delta_b)

        # Compare Last Minute (<=14d) vs Early (>60d)
        early_pool = bucket_prices["Early Bird (>120d)"] + bucket_prices["First Minute (60-120d)"]
        lm_pool = bucket_prices["Last Minute (7-14d)"] + bucket_prices["Panic Dump (≤7d)"]
        if len(early_pool) >= 5 and len(lm_pool) >= 5:
            early_med = statistics.median(early_pool)
            lm_med = statistics.median(lm_pool)
            lm_delta_pct = round(((lm_med - early_med) / early_med) * 100.0, 1) if early_med > 0 else 0.0
        elif len(traj_y) >= 2:
            lm_delta_pct = round(traj_y[-1] - traj_y[0], 1)
        else:
            lm_delta_pct = 0.0

        # Real survival curve: ONLY count cohorts whose departure date has ALREADY reached <= th days from ref_date
        today_ref = ref_date or date.today()
        thresholds = [160, 140, 120, 100, 80, 60, 40, 25, 20, 10, 0]
        surv_x: List[int] = []
        surv_y: List[float] = []
        for th in thresholds:
            eligible = [
                k for k, mx in cohort_max_lead.items()
                if mx >= th and k in cohort_checkin and (cohort_checkin[k] - today_ref).days <= th
            ]
            if len(eligible) >= 5:
                survived = [k for k in eligible if cohort_min_lead[k] <= th]
                surv_x.append(th)
                surv_y.append(round((len(survived) / len(eligible)) * 100.0, 1))

        # Estimate sold-out risk ONLY among mature cohorts whose departure has ALREADY reached <= 14 days
        mid_eligible = [
            k for k, mx in cohort_max_lead.items()
            if mx >= 30 and k in cohort_checkin and (cohort_checkin[k] - today_ref).days <= 14
        ]
        has_mature_soldout = len(mid_eligible) >= 5
        if has_mature_soldout:
            vanished = [k for k in mid_eligible if cohort_min_lead[k] > 14]
            sold_out_risk_pct = round((len(vanished) / len(mid_eligible)) * 100.0, 1)
        else:
            sold_out_risk_pct = 0.0

        has_mature_eb = len(traj_x) >= 2 and (has_mature_soldout or len(surv_x) >= 2)
        if not has_mature_eb:
            ebas_score = 50.0
            verdict = "INSUFFICIENT_MATURE_HORIZON"
            title = "Идёт накопление кривой раннего бронирования"
            description = (
                f"Вылеты ещё далеко (когорт: {total_cohorts}). Для расчёта разницы между ранним стартом и "
                "горящим окном требуются завершённые циклы дат вылета."
            )
        else:
            ebas_score = round(max(15.0, min(95.0, 50.0 + lm_delta_pct * 1.4 + sold_out_risk_pct * 0.3)), 1)
            if ebas_score >= 65.0:
                verdict = "EARLY_BOOKING_HIGHLY_FAVORABLE"
                title = "По данным когорт выгоднее фиксировать заранее"
                description = (
                    f"На выборке из {total_cohorts} когорт цены ближе к вылету в среднем на "
                    f"{lm_delta_pct:+.1f}% относительно раннего старта, а ~{sold_out_risk_pct:.0f}% предложений исчезают до горящего окна."
                )
            elif ebas_score <= 42.0:
                verdict = "WAIT_FOR_LAST_MINUTE"
                title = "По истории чаще срабатывает ожидание скидок"
                description = (
                    f"На выборке из {total_cohorts} когорт поздние предложения в среднем "
                    f"{lm_delta_pct:+.1f}% к ранним тарифам. Жёсткой гонки за остатками не видно."
                )
            else:
                verdict = "BALANCED_MARKET"
                title = "Сбалансированный рынок без перекоса в пользу EB"
                description = (
                    f"Анализ {total_cohorts} когорт показывает умеренную разницу ({lm_delta_pct:+.1f}%) между ранним бронированием и близким вылетом."
                )

        out = {
            "has_data": has_mature_eb,
            "filter_id": filter_id,
            "summary": {
                "ebas_score": ebas_score,
                "verdict": verdict,
                "title": title,
                "description": description,
                "total_cohorts": total_cohorts,
                "lm_delta_pct": lm_delta_pct,
                "sold_out_risk_pct": sold_out_risk_pct,
            },
            "trajectory": {"x": traj_x, "y": traj_y},
            "survival": {"x": surv_x, "y": surv_y},
        }
        _EB_CACHE[cache_key] = (now_ts, out)
        return out

    @classmethod
    async def get_filter_analytics(
        cls, db: AsyncSession, filter_id: str
    ) -> Dict[str, Any]:
        """Computes live DB-driven overview, departure calendar, 24h-72h price moves, and timing stats for a filter."""
        from app.services.timeline_service import resolve_filter_id, get_all_filter_id_variants
        from app.services.canonical_filters import resolve_filter_spec, classify_filter_type

        canonical_fid = resolve_filter_id(filter_id)
        now_ts = time.time()
        if canonical_fid in _FILTER_ANALYTICS_CACHE:
            c_time, c_data = _FILTER_ANALYTICS_CACHE[canonical_fid]
            if now_ts - c_time < _ANALYTICS_CACHE_TTL:
                return c_data

        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False
        join_col = "cohort_id"
        fids = get_all_filter_id_variants(filter_id)
        filter_expr = "ps.filter_id = ANY(:fids)" if is_pg else "ps.filter_id IN :fids"

        stmt_max = text(f"SELECT MAX(ps.recorded_at) FROM price_snapshots ps WHERE {filter_expr}")
        if not is_pg:
            stmt_max = stmt_max.bindparams(bindparam("fids", expanding=True))
        max_ts = (await db.execute(stmt_max, {"fids": fids})).scalar()

        spec = resolve_filter_spec(filter_id) or resolve_filter_spec(canonical_fid)
        if not max_ts:
            ftype = classify_filter_type(canonical_fid, title=(spec or {}).get("title"))
            return {
                "filter_id": filter_id,
                "filter_type": ftype,
                "overview": {
                    "total_hotels": 0,
                    "total_cohorts": 0,
                    "total_snapshots": 0,
                    "avg_price": 0,
                    "median_price": 0,
                    "min_price": 0,
                    "sold_out_7d_lost_count": 0,
                    "last_updated_at": None,
                },
                "calendar_dates": [],
                "price_changes": {"drops": [], "hikes": [], "history": []},
                "timing_stats": {"best_window": "—", "best_window_share_pct": 0.0, "total_drops_analyzed": 0, "by_hour": [], "by_weekday": []},
            }

        max_dt = cls._parse_dt(max_ts) or datetime.now(timezone.utc)
        cutoff_30d = (max_dt - timedelta(days=30)) if is_pg else (max_dt - timedelta(days=30)).isoformat()

        # Total counts across entire filter history
        cnt_sql = f"""
            SELECT COUNT(DISTINCT oc.hotel_id) as h_cnt,
                   COUNT(DISTINCT ps.{join_col}) as c_cnt,
                   COUNT(*) as s_cnt
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.{join_col} = oc.{join_col}
            WHERE {filter_expr}
        """
        stmt_cnt = text(cnt_sql)
        if not is_pg:
            stmt_cnt = stmt_cnt.bindparams(bindparam("fids", expanding=True))
        cnt_row = (await db.execute(stmt_cnt, {"fids": fids})).fetchone()

        # Fetch last 30d snapshots for calendar, 48h moves, timing stats, sold-out lost count
        snap_sql = f"""
            SELECT oc.hotel_id,
                   h.display_name,
                   oc.{join_col} as cid,
                   oc.checkin_date,
                   oc.airport_code,
                   ps.total_price_pln,
                   ps.recorded_at
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.{join_col} = oc.{join_col}
            JOIN hotels h ON oc.hotel_id = h.hotel_id
            WHERE {filter_expr}
              AND ps.recorded_at >= :cutoff_30d
            ORDER BY ps.recorded_at ASC
        """
        stmt_snaps = text(snap_sql)
        if not is_pg:
            stmt_snaps = stmt_snaps.bindparams(bindparam("fids", expanding=True))
        snap_rows = (await db.execute(stmt_snaps, {"fids": fids, "cutoff_30d": cutoff_30d})).fetchall()

        cutoff_24h = max_dt - timedelta(hours=24)
        cutoff_7d = max_dt - timedelta(days=7)
        cutoff_48h = max_dt - timedelta(hours=48)

        today_d = date.today()
        latest_hotel_offers: Dict[str, Dict[str, Any]] = {}
        hotel_names: Dict[str, str] = {}
        hotel_pts: Dict[str, List[Tuple[datetime, float, Optional[date], str]]] = {}
        cohort_pts: Dict[str, List[Tuple[datetime, float]]] = {}
        calendar_buckets: Dict[str, List[Tuple[str, float]]] = {}
        seen_recent_hotels: set = set()
        seen_7d_hotels: set = set()

        for hid, hname, cid, cdate_raw, air, price_raw, rec_raw in snap_rows:
            dt = cls._parse_dt(rec_raw)
            p = float(price_raw or 0.0)
            if not dt or p <= 0:
                continue
            cd = cls._parse_date(cdate_raw)
            hotel_names[hid] = hname
            hotel_pts.setdefault(hid, []).append((dt, p, cd, air or ""))
            cohort_pts.setdefault(str(cid), []).append((dt, p))

            if dt >= cutoff_7d:
                seen_7d_hotels.add(hid)
            if dt >= cutoff_48h:
                seen_recent_hotels.add(hid)
            if dt >= cutoff_24h:
                if cd:
                    d_str = cd.isoformat()
                    calendar_buckets.setdefault(d_str, []).append((hid, p))
                prev_latest = latest_hotel_offers.get(hid)
                if not prev_latest or dt > prev_latest["dt"] or (dt == prev_latest["dt"] and p < prev_latest["price"]):
                    latest_hotel_offers[hid] = {"dt": dt, "price": p, "checkin": cd, "airport": air or ""}

        # Overview stats from latest slice
        active_prices = [v["price"] for v in latest_hotel_offers.values()]
        checkins_all = [v["checkin"] for v in latest_hotel_offers.values() if v["checkin"]]
        filter_type = classify_filter_type(
            canonical_fid, title=(spec or {}).get("title"), checkin_dates=checkins_all
        )

        # Departure Calendar sorted chronologically
        calendar_dates = []
        for d_str in sorted(calendar_buckets.keys()):
            cd = cls._parse_date(d_str)
            if cd and cd < today_d - timedelta(days=1):
                continue
            entries = calendar_buckets[d_str]
            min_by_hotel: Dict[str, float] = {}
            for hid, p in entries:
                if hid not in min_by_hotel or p < min_by_hotel[hid]:
                    min_by_hotel[hid] = p
            p_vals = list(min_by_hotel.values())
            if not p_vals:
                continue
            calendar_dates.append({
                "date": d_str,
                "days_to_dep": (cd - today_d).days if cd else 0,
                "hotels_count": len(min_by_hotel),
                "min_price": round(min(p_vals), 0),
                "median_price": round(statistics.median(p_vals), 0),
            })

        # Price changes (latest price vs ~24-72h ago)
        drops: List[Dict[str, Any]] = []
        hikes: List[Dict[str, Any]] = []
        history_moves: List[Dict[str, Any]] = []
        for hid, latest in latest_hotel_offers.items():
            pts = hotel_pts.get(hid, [])
            if len(pts) < 2:
                continue
            target_prev = latest["dt"] - timedelta(hours=48)
            prev_cands = [pt for pt in pts if 12 <= (latest["dt"] - pt[0]).total_seconds() / 3600.0 <= 84]
            if not prev_cands:
                # Fallback to previous distinct scrape (> 2h older)
                prev_cands = [pt for pt in pts if (latest["dt"] - pt[0]).total_seconds() >= 7200]
            if not prev_cands:
                continue
            prev_cands.sort(key=lambda pt: abs((pt[0] - target_prev).total_seconds()))
            prev_pt = prev_cands[0]
            prev_p = prev_pt[1]
            curr_p = latest["price"]
            delta_pln = round(curr_p - prev_p, 0)
            delta_pct = round(((curr_p - prev_p) / prev_p) * 100.0, 1) if prev_p > 0 else 0.0
            if abs(delta_pln) < 40:
                continue
            move_item = {
                "hotel_id": hid,
                "hotel_name": hotel_names.get(hid, hid),
                "prev_price": round(prev_p, 0),
                "curr_price": round(curr_p, 0),
                "delta_pln": delta_pln,
                "delta_pct": delta_pct,
                "airport_code": latest["airport"],
                "checkin_date": latest["checkin"].isoformat() if latest["checkin"] else None,
                "recorded_at": latest["dt"].isoformat(),
            }
            history_moves.append(move_item)
            if delta_pln < 0:
                drops.append(move_item)
            else:
                hikes.append(move_item)

        drops.sort(key=lambda x: x["delta_pln"])
        hikes.sort(key=lambda x: x["delta_pln"], reverse=True)
        history_moves.sort(key=lambda x: abs(x["delta_pln"]), reverse=True)

        # Timing stats: real hour/weekday distribution of price drops across cohorts
        hour_windows = {"00:00-06:00": 0, "06:00-12:00": 0, "12:00-18:00": 0, "18:00-24:00": 0}
        weekday_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        weekday_counts = {w: 0 for w in weekday_names}
        total_drops_analyzed = 0
        drop_pcts: List[float] = []
        for _, pts in cohort_pts.items():
            for i in range(1, len(pts)):
                prev_dt, prev_p = pts[i - 1]
                cur_dt, cur_p = pts[i]
                if cur_p < prev_p - 30:
                    total_drops_analyzed += 1
                    if prev_p > 0:
                        drop_pcts.append(((cur_p - prev_p) / prev_p) * 100.0)
                    hr = cur_dt.hour
                    if hr < 6:
                        hour_windows["00:00-06:00"] += 1
                    elif hr < 12:
                        hour_windows["06:00-12:00"] += 1
                    elif hr < 18:
                        hour_windows["12:00-18:00"] += 1
                    else:
                        hour_windows["18:00-24:00"] += 1
                    weekday_counts[weekday_names[cur_dt.weekday()]] += 1

        best_win = max(hour_windows.items(), key=lambda kv: kv[1])[0] if total_drops_analyzed > 0 else "—"
        best_share = round((hour_windows.get(best_win, 0) / total_drops_analyzed) * 100.0, 1) if total_drops_analyzed > 0 else 0.0
        avg_drop_pct = round(statistics.mean(drop_pcts), 1) if drop_pcts else 0.0

        result = {
            "filter_id": filter_id,
            "filter_type": filter_type,
            "overview": {
                "total_hotels": len(latest_hotel_offers) or int(cnt_row[0] if cnt_row else 0),
                "total_cohorts": int(cnt_row[1] if cnt_row else 0),
                "total_snapshots": int(cnt_row[2] if cnt_row else 0),
                "avg_price": round(statistics.mean(active_prices), 0) if active_prices else 0,
                "median_price": round(statistics.median(active_prices), 0) if active_prices else 0,
                "min_price": round(min(active_prices), 0) if active_prices else 0,
                "sold_out_7d_lost_count": len(seen_7d_hotels - seen_recent_hotels),
                "last_updated_at": max_dt.isoformat(),
            },
            "calendar_dates": calendar_dates,
            "price_changes": {
                "drops": drops[:10],
                "hikes": hikes[:10],
                "history": history_moves[:12],
            },
            "timing_stats": {
                "best_window": best_win,
                "best_window_share_pct": best_share,
                "avg_drop_pct": avg_drop_pct,
                "total_drops_analyzed": total_drops_analyzed,
                "by_hour": [{"window": k, "drops": v} for k, v in hour_windows.items()],
                "by_weekday": [{"day": k, "drops": weekday_counts[k]} for k in weekday_names],
            },
        }
        _FILTER_ANALYTICS_CACHE[canonical_fid] = (now_ts, result)
        return result

    @classmethod
    async def get_market_overview(cls, db: AsyncSession) -> Dict[str, Any]:
        """Returns high-level market metrics: active hotels, cohorts, total tracked points, median price."""
        global _MARKET_OVERVIEW_CACHE
        now_ts = time.time()
        if _MARKET_OVERVIEW_CACHE is not None:
            c_time, c_data = _MARKET_OVERVIEW_CACHE
            if now_ts - c_time < 1800.0:  # 30 minutes cache
                return c_data

        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False
        cutoff_expr = "NOW() - INTERVAL '24 hours'" if is_pg else "datetime('now', '-24 hours')"

        query = text(f"""
            SELECT 
                (SELECT COUNT(*) FROM hotels) as total_hotels,
                (SELECT COUNT(*) FROM offer_cohorts) as total_cohorts,
                (SELECT COUNT(*) FROM price_snapshots) as total_snapshots,
                (SELECT ROUND(CAST(AVG(total_price_pln) AS NUMERIC), 0) FROM price_snapshots WHERE recorded_at >= {cutoff_expr}) as avg_current_price,
                (SELECT ROUND(CAST(MIN(total_price_pln) AS NUMERIC), 0) FROM price_snapshots WHERE recorded_at >= {cutoff_expr}) as min_current_price
        """)
        res = await db.execute(query)
        row = res.mappings().first()
        results = dict(row) if row else {}
        _MARKET_OVERVIEW_CACHE = (now_ts, results)
        return results

    @classmethod
    async def get_filter_departures(
        cls, db: AsyncSession, filter_id: str
    ) -> Dict[str, Any]:
        """Computes live upcoming departure schedule and real same-destination late-drop evidence from DB."""
        from app.services.timeline_service import resolve_filter_id, get_all_filter_id_variants
        from app.services.canonical_filters import resolve_filter_spec

        canonical_fid = resolve_filter_id(filter_id)
        now_ts = time.time()
        if canonical_fid in _FILTER_DEPARTURES_CACHE:
            c_time, c_data = _FILTER_DEPARTURES_CACHE[canonical_fid]
            if now_ts - c_time < _ANALYTICS_CACHE_TTL:
                return c_data

        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False
        join_col = "cohort_id"
        fids = get_all_filter_id_variants(filter_id)
        filter_expr = "ps.filter_id = ANY(:fids)" if is_pg else "ps.filter_id IN :fids"

        stmt_max = text(f"SELECT MAX(ps.recorded_at) FROM price_snapshots ps WHERE {filter_expr}")
        if not is_pg:
            stmt_max = stmt_max.bindparams(bindparam("fids", expanding=True))
        max_ts = (await db.execute(stmt_max, {"fids": fids})).scalar()

        active_departures: List[Dict[str, Any]] = []
        if max_ts:
            max_dt = cls._parse_dt(max_ts) or datetime.now(timezone.utc)
            cutoff_48h = (max_dt - timedelta(hours=48)) if is_pg else (max_dt - timedelta(hours=48)).isoformat()
            dep_sql = f"""
                SELECT oc.checkin_date,
                       oc.hotel_id,
                       oc.airport_code,
                       ps.total_price_pln
                FROM price_snapshots ps
                JOIN offer_cohorts oc ON ps.{join_col} = oc.{join_col}
                WHERE {filter_expr}
                  AND ps.recorded_at >= :cutoff_48h
                  AND oc.checkin_date IS NOT NULL
                  AND ps.total_price_pln > 0
            """
            stmt_dep = text(dep_sql)
            if not is_pg:
                stmt_dep = stmt_dep.bindparams(bindparam("fids", expanding=True))
            dep_rows = (await db.execute(stmt_dep, {"fids": fids, "cutoff_48h": cutoff_48h})).fetchall()

            today_d = date.today()
            by_date: Dict[str, Dict[str, Any]] = {}
            for cd_raw, hid, air, p_raw in dep_rows:
                cd = cls._parse_date(cd_raw)
                p = float(p_raw or 0.0)
                if not cd or p <= 0 or cd < today_d - timedelta(days=1):
                    continue
                d_str = cd.isoformat()
                entry = by_date.setdefault(d_str, {"hotels": {}, "airports": {}})
                if hid not in entry["hotels"] or p < entry["hotels"][hid]:
                    entry["hotels"][hid] = p
                if air:
                    entry["airports"][air] = entry["airports"].get(air, 0) + 1

            for d_str in sorted(by_date.keys()):
                cd = cls._parse_date(d_str)
                days_to_dep = (cd - today_d).days if cd else 0
                prices = list(by_date[d_str]["hotels"].values())
                top_airports = [
                    k for k, _ in sorted(by_date[d_str]["airports"].items(), key=lambda kv: kv[1], reverse=True)[:4]
                ]
                active_departures.append({
                    "date": d_str,
                    "days_to_dep": days_to_dep,
                    "hotels_count": len(prices),
                    "min_price": round(min(prices), 0),
                    "median_price": round(statistics.median(prices), 0),
                    "airports": top_airports,
                    "is_hot_window": 0 <= days_to_dep <= 4,
                })

        # Same-destination & same-party historical real last-minute drops from DB
        spec = resolve_filter_spec(filter_id) or resolve_filter_spec(canonical_fid)
        target_country = (spec or {}).get("country") or ""
        target_ad = int((spec or {}).get("adults", 2))
        target_ch = int((spec or {}).get("children", 1 if target_ad == 2 else 0))

        hot_history: List[Dict[str, Any]] = []
        if target_country:
            hb_sql = f"""
                SELECT h.display_name,
                       oc.checkin_date,
                       MIN(ps.total_price_pln) as min_p,
                       AVG(ps.total_price_pln) as avg_p,
                       MAX(ps.total_price_pln) as max_p,
                       COUNT(*) as cnt
                FROM price_snapshots ps
                JOIN offer_cohorts oc ON ps.{join_col} = oc.{join_col}
                JOIN hotels h ON oc.hotel_id = h.hotel_id
                WHERE LOWER(h.country) LIKE :ctry
                  AND oc.adults = :ad
                  AND oc.children = :ch
                  AND oc.checkin_date IS NOT NULL
                GROUP BY h.display_name, oc.checkin_date
                HAVING COUNT(*) >= 3
                ORDER BY oc.checkin_date DESC
                LIMIT 200
            """
            hb_rows = (
                await db.execute(
                    text(hb_sql),
                    {"ctry": f"%{target_country.lower()}%", "ad": target_ad, "ch": target_ch},
                )
            ).fetchall()
            for hname, cd_raw, min_p, avg_p, max_p, _ in hb_rows:
                mp = float(min_p or 0)
                ap = float(avg_p or 0)
                if mp <= 0 or ap <= 0:
                    continue
                drop_pct = round(((mp - ap) / ap) * 100.0, 1)
                if drop_pct <= -10.0:
                    cd = cls._parse_date(cd_raw)
                    hot_history.append({
                        "hotel_name": hname,
                        "checkin_date": cd.isoformat() if cd else str(cd_raw),
                        "min_price_pln": round(mp, 0),
                        "avg_price_pln": round(ap, 0),
                        "drop_pct": drop_pct,
                    })
                if len(hot_history) >= 6:
                    break

        hot_days_cnt = sum(1 for d in active_departures if d["is_hot_window"])
        out = {
            "filter_id": filter_id,
            "active_departures": active_departures,
            "hot_history": hot_history,
            "stats": {
                "upcoming_dates_count": len(active_departures),
                "hot_window_dates_count": hot_days_cnt,
                "nearest_date": active_departures[0]["date"] if active_departures else None,
            },
        }
        _FILTER_DEPARTURES_CACHE[canonical_fid] = (now_ts, out)
        return out

    @classmethod
    async def get_seasonality_outlook(
        cls,
        db: AsyncSession,
        destination: Optional[str] = None,
        adults: int = 2,
        children: int = 1,
        filter_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Future Hunter Intelligence: Computes monthly price seasonality, honest price anchors
        (seasonal norm, -15% good deal, historical snipe minimum), drop probability, and
        sold-out risk strictly matched to party composition (adults + children).
        """
        from app.services.timeline_service import resolve_filter_id
        from app.services.canonical_filters import resolve_filter_spec
        from app.services.search_intelligence import get_destination_season_info

        spec = resolve_filter_spec(filter_id) if filter_id else None
        if not spec and filter_id:
            spec = resolve_filter_spec(resolve_filter_id(filter_id))

        target_country = (spec or {}).get("country") or destination or ""
        t_adults = int((spec or {}).get("adults", adults))
        t_children = int((spec or {}).get("children", children))
        dur_min = int((spec or {}).get("duration_min", 6))
        dur_max = int((spec or {}).get("duration_max", 11))
        dur_lo = max(1, dur_min - 1)
        dur_hi = dur_max + 2

        norm_dest = target_country.strip().lower()
        dest_aliases = {norm_dest} if norm_dest else set()
        if any(k in norm_dest for k in ("турц", "turk")):
            dest_aliases.update(["турция", "turkey"])
        elif any(k in norm_dest for k in ("егип", "egypt")):
            dest_aliases.update(["египет", "egypt"])
        elif any(k in norm_dest for k in ("грец", "gree")):
            dest_aliases.update(["греция", "greece"])
        elif any(k in norm_dest for k in ("кипр", "cypr")):
            dest_aliases.update(["кипр", "cyprus"])

        cache_key = f"{filter_id or ''}_{norm_dest}_{t_adults}_{t_children}_{dur_lo}_{dur_hi}"
        now_ts = time.time()
        if cache_key in _SEASONALITY_CACHE:
            c_time, c_data = _SEASONALITY_CACHE[cache_key]
            if now_ts - c_time < _ANALYTICS_CACHE_TTL:
                return c_data

        params: Dict[str, Any] = {
            "ad": t_adults,
            "ch": t_children,
            "dl": dur_lo,
            "dh": dur_hi,
        }
        dest_clause = ""
        if dest_aliases:
            d_ph = " OR ".join(f"LOWER(h.country) LIKE :d{i} OR LOWER(oc.destination_code) LIKE :d{i}" for i in range(len(dest_aliases)))
            dest_clause = f"AND ({d_ph})"
            for i, d_val in enumerate(sorted(dest_aliases)):
                params[f"d{i}"] = f"%{d_val}%"

        sql = f"""
            SELECT oc.cohort_id,
                   oc.hotel_id,
                   oc.checkin_date,
                   ps.recorded_at,
                   ps.total_price_pln
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.cohort_id = oc.cohort_id
            JOIN hotels h ON oc.hotel_id = h.hotel_id
            WHERE oc.adults = :ad
              AND oc.children = :ch
              AND oc.duration_nights BETWEEN :dl AND :dh
              AND oc.checkin_date IS NOT NULL
              AND ps.total_price_pln > 0
              {dest_clause}
            ORDER BY ps.recorded_at DESC
            LIMIT 50000
        """
        rows = (await db.execute(text(sql), params)).fetchall()

        MONTH_LABELS = {
            "01": "Январь", "02": "Февраль", "03": "Март", "04": "Апрель",
            "05": "Май", "06": "Июнь", "07": "Июль", "08": "Август",
            "09": "Сентябрь", "10": "Октябрь", "11": "Ноябрь", "12": "Декабрь",
        }

        all_prices: List[float] = []
        month_data: Dict[str, Dict[str, Any]] = {}
        cohort_stats: Dict[str, Dict[str, Any]] = {}
        ref_date: Optional[date] = None

        for cid, hid, cd_raw, rec_raw, p_raw in rows:
            dt = cls._parse_dt(rec_raw)
            cd = cls._parse_date(cd_raw)
            p = float(p_raw or 0.0)
            if not dt or not cd or p <= 0:
                continue
            if ref_date is None or dt.date() > ref_date:
                ref_date = dt.date()
            lead = (cd - dt.date()).days
            if lead < 0 or lead > 400:
                continue
            all_prices.append(p)

            m_key = cd.strftime("%Y-%m")
            m_entry = month_data.setdefault(
                m_key, {"prices": [], "lm_prices": [], "hotels": set(), "cohorts": set(), "sample_date": cd}
            )
            m_entry["prices"].append(p)
            m_entry["hotels"].add(hid)
            m_entry["cohorts"].add(str(cid))
            if lead <= 5:
                m_entry["lm_prices"].append(p)

            c_key = str(cid)
            c_entry = cohort_stats.setdefault(
                c_key, {"cd": cd, "min_lead": lead, "max_lead": lead, "prices": []}
            )
            c_entry["min_lead"] = min(c_entry["min_lead"], lead)
            c_entry["max_lead"] = max(c_entry["max_lead"], lead)
            c_entry["prices"].append(p)

        today_ref = ref_date or date.today()
        party_label = (
            "1 взр"
            if (t_adults == 1 and t_children == 0)
            else ("2 взр" if t_children == 0 else f"{t_adults} взр + {t_children} реб")
        )

        if len(all_prices) < 5:
            out = {
                "has_data": False,
                "destination": target_country or "all",
                "party_label": party_label,
                "anchors": {
                    "seasonal_median_pln": 0,
                    "good_deal_target_pln": 0,
                    "snipe_record_pln": 0,
                },
                "hunt_odds": {
                    "dump_probability_pct": 0.0,
                    "sold_out_scarcity_pct": 0.0,
                    "strategy_verdict": "INSUFFICIENT_DATA",
                    "headline": "Пока недостаточно данных для прогноза сезонности",
                    "advice": "По мере накопления замеров для этого состава туристов здесь появится прогноз по месяцам.",
                },
                "months": [],
            }
            return out

        sorted_all = sorted(all_prices)
        seasonal_median = round(statistics.median(sorted_all), 0)
        good_deal_target = round(seasonal_median * 0.85, 0)
        p5_idx = max(0, int(len(sorted_all) * 0.05))
        snipe_record = round(sorted_all[p5_idx], 0)

        # Evaluate mature cohorts that have already crossed the last-minute threshold (<= 3 days to departure)
        # so future departures 8-14 days away are NEVER miscounted as "vanished before D-7".
        mature_cohorts = [
            c for c in cohort_stats.values()
            if c["max_lead"] >= 14 and (c["cd"] - today_ref).days <= 3
        ]
        if len(mature_cohorts) >= 5:
            vanished_cnt = sum(1 for c in mature_cohorts if c["min_lead"] > 7)
            sold_out_pct = round((vanished_cnt / len(mature_cohorts)) * 100.0, 1)
            dropped_cnt = sum(
                1 for c in mature_cohorts
                if len(c["prices"]) >= 2 and min(c["prices"]) <= statistics.median(c["prices"]) * 0.88
            )
            dump_prob_pct = round((dropped_cnt / len(mature_cohorts)) * 100.0, 1)
        else:
            # Cross-sectional proxy from low-priced LM vs seasonal norm when mature history is young
            lm_all = [p for m in month_data.values() for p in m["lm_prices"]]
            if len(lm_all) >= 10:
                dump_prob_pct = round(sum(1 for p in lm_all if p <= seasonal_median * 0.85) / len(lm_all) * 100.0, 1)
            else:
                dump_prob_pct = 0.0
            sold_out_pct = 0.0

        # Build sorted monthly outlook (keep recent/future months)
        cutoff_month = (today_ref - timedelta(days=35)).strftime("%Y-%m")
        months_list: List[Dict[str, Any]] = []
        for m_key in sorted(month_data.keys()):
            if m_key < cutoff_month:
                continue
            md = month_data[m_key]
            ps_m = sorted(md["prices"])
            if len(ps_m) < 3:
                continue
            m_med = round(statistics.median(ps_m), 0)
            m_min = round(ps_m[0], 0)
            m_p10 = round(ps_m[max(0, int(len(ps_m) * 0.1))], 0)
            lm_cnt = len(md["lm_prices"])
            hot_share = (
                round(sum(1 for p in md["lm_prices"] if p <= m_med * 0.88) / lm_cnt * 100.0, 1)
                if lm_cnt >= 3
                else None
            )
            yr, mm = m_key.split("-")
            s_info = get_destination_season_info(target_country or "turkey", md["sample_date"])
            months_list.append({
                "month": m_key,
                "label": f"{MONTH_LABELS.get(mm, mm)} {yr}",
                "min_price": m_min,
                "p10_price": m_p10,
                "median_price": m_med,
                "hotels_count": len(md["hotels"]),
                "cohorts_count": len(md["cohorts"]),
                "hot_share_pct": hot_share,
                "season_tier": s_info.get("season", "standard"),
                "season_label": s_info.get("label", ""),
                "is_cheaper_month": m_med <= seasonal_median * 0.93,
            })

        cheapest_m = min(months_list, key=lambda x: x["median_price"]) if months_list else None
        if sold_out_pct >= 55.0:
            verdict = "EARLY_BOOKING_SAFER"
            headline = f"Для {party_label} высокий риск Sold-Out ({sold_out_pct:.0f}%)"
            advice = (
                f"В этом направлении ({target_country or 'курорт'}) {sold_out_pct:.0f}% вариантов для состава {party_label} "
                f"исчезают до последней недели. Лучше поставить алерт заранее на целевую цену ≤ {int(good_deal_target):,} zł и не тянуть до D-2."
            )
        elif dump_prob_pct >= 28.0:
            verdict = "WAIT_FOR_DROP"
            headline = f"Хорошие шансы поймать сброс (~{dump_prob_pct:.0f}% кейсов)"
            advice = (
                f"Наблюдается заметная доля сбросов ≥ −12% ({dump_prob_pct:.0f}%). "
                f"Соберите шорт-лист в Watchlist и ждите целевой цены ≤ {int(good_deal_target):,} zł (рекордное дно около {int(snipe_record):,} zł)."
            )
        else:
            verdict = "BALANCED_HUNT"
            headline = "Умеренная динамика — ловите конкретные отели по целевой цене"
            advice = (
                f"Норма рынка для {party_label} — ~{int(seasonal_median):,} zł. Удачной сделкой считается уровень ≤ {int(good_deal_target):,} zł"
                + (f", а самым доступным месяцем выходит {cheapest_m['label']} (~{int(cheapest_m['median_price']):,} zł)." if cheapest_m else ".")
            )

        out = {
            "has_data": True,
            "destination": target_country or "all",
            "party_label": party_label,
            "anchors": {
                "seasonal_median_pln": seasonal_median,
                "good_deal_target_pln": good_deal_target,
                "snipe_record_pln": snipe_record,
            },
            "hunt_odds": {
                "dump_probability_pct": dump_prob_pct,
                "sold_out_scarcity_pct": sold_out_pct,
                "strategy_verdict": verdict,
                "headline": headline,
                "advice": advice,
                "cheapest_month": cheapest_m["month"] if cheapest_m else None,
                "cheapest_month_label": cheapest_m["label"] if cheapest_m else None,
            },
            "months": months_list,
        }
        _SEASONALITY_CACHE[cache_key] = (now_ts, out)
        return out

