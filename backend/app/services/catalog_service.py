import logging
import re
import statistics
import time
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta, timezone
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

logger = logging.getLogger("travel_monitor_2.catalog")

from app.services.timeline_service import resolve_filter_id, get_all_filter_id_variants
from app.services.canonical_filters import (
    get_filter_display_ceiling,
    resolve_filter_spec,
    classify_filter_type,
)
from app.services.hotel_deal_score import compute_hotel_deal_metrics, compute_unified_deal_assessment
from app.services.normalization import normalize_airport_code, normalize_board_basis
from app.services.search_intelligence import get_destination_season_info
from app.services.hotel_knowledge_service import HotelKnowledgeService

_CATALOG_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]], Any]] = {}
_CACHE_TTL_SECONDS = 900  # 15 minutes in-memory cache


def _clamp(v: float, lo: float, hi: float) -> float:
    try:
        val = float(v)
        return max(lo, min(hi, val))
    except (TypeError, ValueError):
        return lo


class CatalogService:
    @classmethod
    async def get_filter_hotels(
        cls,
        db: AsyncSession,
        filter_id: str,
        sort_by: str = "price",
        order: str = "asc",
        stars: Optional[int] = None,
        search_query: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves live catalog cards for a filter with Deal Score, 24h/7d price changes,
        TripAdvisor ratings, and badges calculated directly against historical database.
        """
        canonical_fid = resolve_filter_id(filter_id)

        # Check in-memory cache
        now_ts = time.time()
        cards: Optional[List[Dict[str, Any]]] = None
        max_ts_val = None
        if canonical_fid in _CATALOG_CACHE:
            c_time, c_cards, c_max_ts = _CATALOG_CACHE[canonical_fid]
            if now_ts - c_time < _CACHE_TTL_SECONDS:
                cards = c_cards
                max_ts_val = c_max_ts

        if cards is None:
            cards, max_ts_val = await cls._compute_catalog_cards(db, filter_id, canonical_fid)
            _CATALOG_CACHE[canonical_fid] = (now_ts, cards, max_ts_val)

        # 5. Apply filters
        # Enforce canonical display ceiling if max_price was not explicitly specified
        effective_max_price = max_price
        if effective_max_price is None:
            effective_max_price = get_filter_display_ceiling(filter_id) or get_filter_display_ceiling(canonical_fid)
        elif effective_max_price <= 0:
            effective_max_price = None  # Explicit override to show all

        filtered_cards = list(cards)
        if stars:
            filtered_cards = [c for c in filtered_cards if c["stars"] == stars]
        if search_query:
            sq = search_query.strip().lower()
            filtered_cards = [c for c in filtered_cards if sq in c["display_name"].lower()]
        if min_price is not None:
            filtered_cards = [c for c in filtered_cards if c["current_min_price"] >= min_price]
        if effective_max_price is not None:
            filtered_cards = [c for c in filtered_cards if c["current_min_price"] <= effective_max_price]

        # 6. Sorting
        reverse_order = order.lower() == "desc"
        if sort_by == "deal_score":
            filtered_cards.sort(key=lambda x: x["deal_score"], reverse=reverse_order)
        elif sort_by == "ta_rating":
            filtered_cards.sort(key=lambda x: (x["ta_rating"] or 0, x["ta_reviews"]), reverse=reverse_order)
        elif sort_by in ("discount_48h", "delta48"):
            filtered_cards.sort(key=lambda x: x.get("change_48h_pct", 0.0), reverse=reverse_order)
        elif sort_by == "delta_avg":
            filtered_cards.sort(key=lambda x: x.get("delta_vs_typical_pct", 0.0), reverse=reverse_order)
        elif sort_by == "discount_24h":
            filtered_cards.sort(key=lambda x: x["change_24h_pct"], reverse=reverse_order)
        else:  # default "price"
            filtered_cards.sort(key=lambda x: x["current_min_price"], reverse=reverse_order)

        max_ts_str = (
            max_ts_val.isoformat()
            if hasattr(max_ts_val, "isoformat")
            else str(max_ts_val)
            if max_ts_val
            else None
        )
        spec = resolve_filter_spec(filter_id) or resolve_filter_spec(canonical_fid)
        checkin_list = [c.get("cheapest_checkin_date") for c in cards if c.get("cheapest_checkin_date")]
        filter_type = classify_filter_type(canonical_fid, title=(spec or {}).get("title"), checkin_dates=checkin_list)

        return {
            "filter_id": filter_id,
            "filter_type": filter_type,
            "total_hotels": len(filtered_cards),
            "hotels": filtered_cards,
            "last_updated_at": max_ts_str,
        }

    @classmethod
    async def _compute_catalog_cards(
        cls,
        db: AsyncSession,
        filter_id: str,
        canonical_fid: str,
    ) -> Tuple[List[Dict[str, Any]], Any]:
        fids = get_all_filter_id_variants(filter_id)
        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False
        filter_expr = "ps.filter_id = ANY(:fids)" if is_pg else "ps.filter_id IN :fids"
        oc_filter_expr = "oc.filter_id = ANY(:fids)" if is_pg else "oc.filter_id IN :fids"
        join_col = "cohort_id"

        from app.services.timeline_service import ARCHIVED_FILTER_CUTOFFS

        archive_clause = ""
        archive_cutoff = None
        for v in [filter_id, canonical_fid] + fids:
            if v in ARCHIVED_FILTER_CUTOFFS:
                archive_cutoff = ARCHIVED_FILTER_CUTOFFS[v]
                break

        params: Dict[str, Any] = {"fids": fids}
        if archive_cutoff:
            cutoff_dt = datetime.fromisoformat(archive_cutoff.replace("Z", "+00:00"))
            archive_clause = "AND ps.recorded_at <= :archive_cutoff"
            params["archive_cutoff"] = cutoff_dt if is_pg else archive_cutoff

        # 1. Find the latest recorded scrape time for this filter using fast index scan
        stmt = text(f"SELECT ps.recorded_at FROM price_snapshots ps WHERE {filter_expr} {archive_clause} ORDER BY ps.recorded_at DESC LIMIT 1")
        if not is_pg:
            from sqlalchemy import bindparam
            stmt = stmt.bindparams(bindparam("fids", expanding=True))
        time_res = await db.execute(stmt, params)
        max_ts = time_res.scalar()

        if not max_ts:
            return [], None

        if isinstance(max_ts, str):
            ts_str = max_ts.replace("Z", "+00:00").replace(" ", "T")
            if "+" not in ts_str and not ts_str.endswith("Z"):
                ts_str += "+00:00"
            max_dt = datetime.fromisoformat(ts_str)
        else:
            max_dt = max_ts

        if max_dt.tzinfo is None:
            max_dt = max_dt.replace(tzinfo=timezone.utc)

        cutoff = (max_dt - timedelta(hours=24)) if is_pg else (max_dt - timedelta(hours=24)).isoformat()

        # 2. Query active hotels and their cheapest offer in the latest scrape run (using window partition)
        checkin_guard = "" if archive_cutoff else "AND (oc.checkin_date IS NULL OR oc.checkin_date >= :today_date)"
        active_sql = f"""
            WITH ranked_offers AS (
                SELECT 
                    h.hotel_id,
                    h.display_name,
                    h.country,
                    h.region,
                    h.stars,
                    h.ta_rating,
                    h.ta_reviews,
                    h.main_image_url,
                    oc.checkin_date,
                    oc.duration_nights,
                    oc.airport_code,
                    oc.offer_url,
                    oc.cohort_hash,
                    ps.total_price_pln as current_price,
                    ps.recorded_at,
                    oc.board_basis,
                    ROW_NUMBER() OVER (PARTITION BY h.hotel_id ORDER BY ps.recorded_at DESC, ps.total_price_pln ASC) as rn
                FROM price_snapshots ps
                JOIN offer_cohorts oc ON ps.{join_col} = oc.{join_col}
                JOIN hotels h ON oc.hotel_id = h.hotel_id
                WHERE {filter_expr}
                  AND ps.recorded_at >= :cutoff
                  {checkin_guard}
            )
            SELECT 
                hotel_id,
                display_name,
                country,
                region,
                stars,
                ta_rating,
                ta_reviews,
                main_image_url,
                checkin_date,
                duration_nights,
                airport_code,
                offer_url,
                current_price,
                recorded_at,
                cohort_hash,
                board_basis
            FROM ranked_offers
            WHERE rn = 1
            ORDER BY current_price ASC;
        """
        a_stmt = text(active_sql)
        if not is_pg:
            from sqlalchemy import bindparam
            a_stmt = a_stmt.bindparams(bindparam("fids", expanding=True))

        active_params = {"fids": fids, "cutoff": cutoff}
        if not archive_cutoff:
            from datetime import date as _date
            active_params["today_date"] = _date.today() if is_pg else _date.today().isoformat()

        active_res = await db.execute(a_stmt, active_params)
        active_rows = active_res.fetchall()

        if not active_rows:
            # Wider window fallback if last scrape was slightly sparse
            cutoff_24h = (max_dt - timedelta(hours=24)) if is_pg else (max_dt - timedelta(hours=24)).isoformat()
            active_params["cutoff"] = cutoff_24h
            active_res = await db.execute(a_stmt, active_params)
            active_rows = active_res.fetchall()

        if not active_rows:
            return [], None

        hotel_ids = [r[0] for r in active_rows]

        # 3. Expand hotel IDs to query variants across alias clusters
        from app.services.watchlist_service import WatchlistService
        from app.models.hotel import Hotel

        active_h_res = await db.execute(select(Hotel).where(Hotel.hotel_id.in_(hotel_ids)))
        active_h_map = {h.hotel_id: h for h in active_h_res.scalars().all()}

        all_query_hids: Set[str] = set()
        variant_to_primary: Dict[str, Set[str]] = {}
        for hid in hotel_ids:
            h_obj = active_h_map.get(hid)
            vars_set = set(await WatchlistService._find_related_hotel_ids(db, h_obj)) if h_obj else {hid}
            vars_set.add(hid)
            all_query_hids.update(vars_set)
            for v in vars_set:
                if v not in variant_to_primary:
                    variant_to_primary[v] = set()
                variant_to_primary[v].add(hid)

        query_hids_list = list(all_query_hids)

        # Batch fetch historical min/max aggregate stats directly in SQL
        placeholders = ",".join(f":h{i}" for i in range(len(query_hids_list)))
        h_params = {f"h{i}": hid for i, hid in enumerate(query_hids_list)}
        h_params["fids"] = fids

        stats_sql = f"""
            SELECT 
                oc.hotel_id,
                MIN(ps.total_price_pln) as hist_min,
                MAX(ps.total_price_pln) as hist_max
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.{join_col} = oc.{join_col}
            WHERE {filter_expr}
              AND {oc_filter_expr}
              AND oc.hotel_id IN ({placeholders})
            GROUP BY oc.hotel_id;
        """
        s_stmt = text(stats_sql)
        if not is_pg:
            from sqlalchemy import bindparam
            s_stmt = s_stmt.bindparams(bindparam("fids", expanding=True))

        stats_res = await db.execute(s_stmt, h_params)
        hotel_stats: Dict[str, Tuple[float, float]] = {}
        for r in stats_res.fetchall():
            row_hid = r[0]
            r_min = float(r[1])
            r_max = float(r[2])
            for prim in variant_to_primary.get(row_hid, {row_hid}):
                if prim not in hotel_stats:
                    hotel_stats[prim] = (r_min, r_max)
                else:
                    cur_min, cur_max = hotel_stats[prim]
                    hotel_stats[prim] = (min(cur_min, r_min), max(cur_max, r_max))

        # 3b. Fetch recent 30-day snapshots for 24h/7d change, median, and Deal Score
        recent_cutoff = (max_dt - timedelta(days=30)) if is_pg else (max_dt - timedelta(days=30)).isoformat()
        h_params_recent = dict(h_params)
        h_params_recent["recent_cutoff"] = recent_cutoff

        hist_sql = f"""
            SELECT 
                oc.hotel_id,
                ps.recorded_at,
                ps.total_price_pln
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.{join_col} = oc.{join_col}
            WHERE {filter_expr}
              AND {oc_filter_expr}
              AND oc.hotel_id IN ({placeholders})
              AND ps.recorded_at >= :recent_cutoff
            ORDER BY ps.recorded_at ASC;
        """
        h_stmt = text(hist_sql)
        if not is_pg:
            from sqlalchemy import bindparam
            h_stmt = h_stmt.bindparams(bindparam("fids", expanding=True))

        hist_res = await db.execute(h_stmt, h_params_recent)
        hist_rows = hist_res.fetchall()

        # 3c. Strict 1:1 cross-filter benchmark stats (same adults, children, and duration_nights bucket!)
        spec = resolve_filter_spec(filter_id) or resolve_filter_spec(canonical_fid)
        target_adults = int((spec or {}).get("adults", 1 if ("_1p" in canonical_fid or canonical_fid in ("cyprus_7_10", "filter_cyprus_7_10")) else 2))
        target_children = int((spec or {}).get("children", 0 if target_adults == 1 else 1))
        dur_min = int((spec or {}).get("duration_min", 13 if "13_16" in canonical_fid else 6))
        dur_max = int((spec or {}).get("duration_max", 16 if "13_16" in canonical_fid else 10))
        dur_lo = max(1, dur_min - 1)
        dur_hi = dur_max + 1

        active_checkins = [r[8] for r in active_rows if r[8]]
        filter_type = classify_filter_type(canonical_fid, title=(spec or {}).get("title"), checkin_dates=active_checkins)
        is_lastminute = filter_type == "lastminute"

        cross_stats: Dict[str, Tuple[float, float, float, int]] = {}
        upcoming_std_by_hotel: Dict[str, Dict[str, Any]] = {}
        if query_hids_list:
            cross_cutoff = (max_dt - timedelta(days=180)) if is_pg else (max_dt - timedelta(days=180)).isoformat()
            c_params = {f"h{i}": hid for i, hid in enumerate(query_hids_list)}
            c_params["cross_cutoff"] = cross_cutoff
            c_params["t_ad"] = target_adults
            c_params["t_ch"] = target_children
            c_params["dur_lo"] = dur_lo
            c_params["dur_hi"] = dur_hi
            med_expr = (
                "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ps.total_price_pln)"
                if is_pg
                else "AVG(ps.total_price_pln)"
            )
            cross_sql = f"""
                SELECT 
                    oc.hotel_id,
                    CASE WHEN LOWER(COALESCE(oc.board_basis, 'All Inclusive')) LIKE '%all%' THEN 'AI' ELSE 'NON_AI' END as brd_tier,
                    MIN(ps.total_price_pln) as c_min,
                    MAX(ps.total_price_pln) as c_max,
                    {med_expr} as c_med,
                    COUNT(ps.id) as c_cnt
                FROM price_snapshots ps
                JOIN offer_cohorts oc ON ps.{join_col} = oc.{join_col}
                WHERE oc.hotel_id IN ({placeholders})
                  AND ps.recorded_at >= :cross_cutoff
                  AND oc.adults = :t_ad
                  AND oc.children = :t_ch
                  AND oc.duration_nights BETWEEN :dur_lo AND :dur_hi
                  AND oc.filter_id NOT LIKE '%lastminute%'
                GROUP BY oc.hotel_id, brd_tier;
            """
            try:
                c_res = await db.execute(text(cross_sql), c_params)
                for r in c_res.fetchall():
                    row_hid = r[0]
                    brd_tier = r[1]
                    c_min = float(r[2]) if r[2] is not None else None
                    c_max = float(r[3]) if r[3] is not None else None
                    c_med = float(r[4]) if r[4] is not None else None
                    c_cnt = int(r[5] or 0)
                    if c_min is not None and c_med is not None and c_cnt >= 3:
                        for prim in variant_to_primary.get(row_hid, {row_hid}):
                            key = (prim, brd_tier)
                            if key not in cross_stats:
                                cross_stats[key] = (c_min, c_max, c_med, c_cnt)
                            else:
                                o_min, o_max, o_med, o_cnt = cross_stats[key]
                                tot = o_cnt + c_cnt
                                weighted_med = (o_med * o_cnt + c_med * c_cnt) / max(1, tot)
                                cross_stats[key] = (min(o_min, c_min), max(o_max, c_max), weighted_med, tot)
            except Exception as e:
                logger.warning(f"Cross-filter stats lookup failed: {e}")

            # Batched lookup of live upcoming standard departures (D >= 5 days, fresh within 7 days) for lastminute
            if is_lastminute:
                fresh_rec = (datetime.now(timezone.utc) - timedelta(days=7))
                min_std_dep = (datetime.utcnow().date() + timedelta(days=5))
                std_params = {f"h{i}": hid for i, hid in enumerate(query_hids_list)}
                std_params["fresh_rec"] = fresh_rec if is_pg else fresh_rec.isoformat()
                std_params["min_std_dep"] = min_std_dep if is_pg else min_std_dep.isoformat()
                std_params["t_ad"] = target_adults
                std_params["t_ch"] = target_children
                std_params["dur_lo"] = dur_lo
                std_params["dur_hi"] = dur_hi
                std_sql = f"""
                    SELECT
                        oc.hotel_id,
                        ps.total_price_pln,
                        oc.checkin_date,
                        oc.airport_code
                    FROM price_snapshots ps
                    JOIN offer_cohorts oc ON ps.{join_col} = oc.{join_col}
                    WHERE oc.hotel_id IN ({placeholders})
                      AND ps.recorded_at >= :fresh_rec
                      AND oc.checkin_date >= :min_std_dep
                      AND oc.adults = :t_ad
                      AND oc.children = :t_ch
                      AND oc.duration_nights BETWEEN :dur_lo AND :dur_hi
                      AND oc.filter_id NOT LIKE '%lastminute%'
                """
                try:
                    std_res = await db.execute(text(std_sql), std_params)
                    for row_hid, s_price, s_dep, s_air in std_res.fetchall():
                        sp = float(s_price or 0.0)
                        if sp <= 0:
                            continue
                        s_dep_str = str(s_dep)[:10] if s_dep else None
                        for prim in variant_to_primary.get(row_hid, {row_hid}):
                            cur = upcoming_std_by_hotel.get(prim)
                            if not cur or sp < cur["price"]:
                                upcoming_std_by_hotel[prim] = {
                                    "price": round(sp, 0),
                                    "date": s_dep_str,
                                    "airport": s_air or "",
                                }
                except Exception as std_err:
                    logger.warning(f"Upcoming standard departure batch lookup failed: {std_err}")

        # Group history points by primary hotel_id
        hotel_history: Dict[str, List[Tuple[datetime, float]]] = {}
        for r_hid, r_at, p_val in hist_rows:
            try:
                if isinstance(r_at, str):
                    ts_clean = r_at.replace("Z", "+00:00").replace(" ", "T")
                    if "+" not in ts_clean and not ts_clean.endswith("Z"):
                        ts_clean += "+00:00"
                    dt = datetime.fromisoformat(ts_clean)
                else:
                    dt = r_at
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            for prim in variant_to_primary.get(r_hid, {r_hid}):
                if prim not in hotel_history:
                    hotel_history[prim] = []
                hotel_history[prim].append((dt, float(p_val)))

        for prim in hotel_history:
            hotel_history[prim].sort(key=lambda x: x[0])

        # 4. Construct catalog cards with metrics and badges
        cards = []
        for row in active_rows:
            (
                h_id,
                disp_name,
                country,
                region,
                stars_val,
                ta_rating,
                ta_reviews,
                img_url,
                checkin_dt,
                dur_nights,
                airport_code,
                offer_url,
                curr_price,
                last_rec_at,
                cohort_hash,
                raw_board_basis,
            ) = row
            norm_air = normalize_airport_code(airport_code, offer_url)
            norm_brd = normalize_board_basis(raw_board_basis)

            curr_price = float(curr_price)
            hist_pts = hotel_history.get(h_id, [])
            stats_tuple = hotel_stats.get(h_id)
            row_brd_tier = "AI" if "all" in norm_brd.lower() else "NON_AI"
            c_tuple = cross_stats.get((h_id, row_brd_tier))

            if stats_tuple:
                hist_min = round(stats_tuple[0], 0)
                hist_max = round(stats_tuple[1], 0)
            elif c_tuple:
                hist_min = round(c_tuple[0], 0)
                hist_max = round(c_tuple[1], 0)
            elif hist_pts:
                all_p = [p[1] for p in hist_pts]
                hist_min = round(min(all_p), 0)
                hist_max = round(max(all_p), 0)
            else:
                hist_min = curr_price
                hist_max = curr_price

            # Detect urgency / lastminute status
            c_date = None
            days_to_dep = None
            if checkin_dt:
                try:
                    c_date = (
                        datetime.strptime(str(checkin_dt).split("T")[0], "%Y-%m-%d").date()
                        if isinstance(checkin_dt, str)
                        else (checkin_dt.date() if isinstance(checkin_dt, datetime) else checkin_dt)
                    )
                    days_to_dep = (c_date - datetime.utcnow().date()).days
                except Exception:
                    c_date = None
            is_lm = is_lastminute or (days_to_dep is not None and 0 <= days_to_dep <= 4)

            has_local_history = len(hist_pts) >= 3
            history_span_days = (
                (hist_pts[-1][0] - hist_pts[0][0]).days if len(hist_pts) >= 2 else 0
            )
            chg_30d: Optional[float] = None
            if has_local_history:
                all_prices = [p[1] for p in hist_pts]
                local_med = round(statistics.median(all_prices), 0)
                # For short-lived lastminute radars or short histories (< 7d), prefer 1:1 canonical cross-filter median
                if (is_lm or history_span_days < 7) and c_tuple and c_tuple[2] and c_tuple[2] > 0:
                    typical_med = round(c_tuple[2], 0)
                else:
                    typical_med = local_med

                # Look for price ~24h ago, ~48h ago, ~7d ago, and ~30d trend
                latest_dt = hist_pts[-1][0]
                dt_24h_target = latest_dt - timedelta(hours=24)
                dt_48h_target = latest_dt - timedelta(hours=48)
                dt_7d_target = latest_dt - timedelta(days=7)

                p_24h = None
                p_48h = None
                p_7d = None

                win_48h = [pt for pt in hist_pts if pt[0] >= dt_48h_target]
                if len(win_48h) >= 2 and (latest_dt - win_48h[0][0]).total_seconds() >= 10 * 3600:
                    p_48h = win_48h[0][1]
                else:
                    older_10h = [pt for pt in hist_pts if (latest_dt - pt[0]).total_seconds() >= 10 * 3600]
                    if older_10h:
                        p_48h = older_10h[-1][1]

                for dt, p in reversed(hist_pts):
                    if p_24h is None and dt <= dt_24h_target:
                        p_24h = p
                    if p_7d is None and dt <= dt_7d_target:
                        p_7d = p
                    if p_24h is not None and p_7d is not None:
                        break

                chg_24h = round((curr_price - p_24h) / p_24h * 100.0, 1) if p_24h else 0.0
                chg_48h = round((curr_price - p_48h) / p_48h * 100.0, 1) if p_48h else 0.0
                chg_7d = round((curr_price - p_7d) / p_7d * 100.0, 1) if p_7d else 0.0
                if history_span_days >= 5 and hist_pts[0][1] > 0:
                    chg_30d = round((curr_price - hist_pts[0][1]) / hist_pts[0][1] * 100.0, 1)
            elif c_tuple and c_tuple[2] and c_tuple[2] > 0:
                typical_med = round(c_tuple[2], 0)
                chg_24h = 0.0
                chg_48h = 0.0
                chg_7d = 0.0
            else:
                typical_med = None
                chg_24h = 0.0
                chg_48h = 0.0
                chg_7d = 0.0

            # Knowledge base enrichment (accurate beach line, TripAdvisor rating, and infrastructure)
            h_obj = active_h_map.get(h_id)
            dossier = HotelKnowledgeService.get_hotel_dossier(
                hotel_name=disp_name,
                destination=country,
                country=country,
                stars=stars_val or 4,
                current_price=curr_price,
                main_image_url=img_url,
                db_specs=h_obj.specs if h_obj else None,
                db_reputation=h_obj.reputation if h_obj else None,
            )
            final_ta_rating = (
                float(ta_rating)
                if ta_rating
                else (float(dossier["ta_rating"]) if dossier.get("ta_rating") else None)
            )
            final_ta_reviews = (
                int(ta_reviews)
                if ta_reviews
                else (int(dossier["ta_reviews"]) if dossier.get("ta_reviews") else 0)
            )
            beach_line = dossier.get("beach_line", 1)
            beach_type = dossier.get("beach_type", "песчано-галечный пляж")
            has_aquapark = dossier.get("has_aquapark", False)
            has_heated_pools = dossier.get("has_heated_pools", False)

            # Unified Single-Source-of-Truth Deal Assessment
            effective_samples = max(len(hist_pts), int(c_tuple[3])) if (c_tuple and (is_lm or history_span_days < 7)) else len(hist_pts)
            has_sufficient_history = effective_samples >= 3 and (typical_med is not None and typical_med > 0)
            df_hist = pd.DataFrame(hist_pts, columns=["scraped_at", "price"]) if len(hist_pts) >= 3 else None
            season_info = get_destination_season_info(country, c_date)
            std_info = upcoming_std_by_hotel.get(h_id) if is_lm else None

            assessment = compute_unified_deal_assessment(
                latest_price=curr_price,
                typical_price=typical_med,
                hist_df=df_hist,
                samples_count=effective_samples,
                ta_rating=final_ta_rating,
                ta_review_count=final_ta_reviews,
                filter_type=filter_type,
                days_to_dep=days_to_dep,
                season_info=season_info,
                upcoming_std_price=std_info["price"] if std_info else None,
                upcoming_std_date=std_info["date"] if std_info else None,
                change_48h_pct=chg_48h,
                change_30d_pct=chg_30d,
            )
            deal_score = assessment["deal_score"]
            confidence = assessment["confidence"]
            delta_vs_typical = assessment["avg_delta_pct"]
            hopper_verdict = assessment["hopper_verdict"]
            action_label = assessment["action_label"]
            recommendation = assessment["recommendation"]
            spread_vs_std_pln = assessment["spread_vs_std_pln"]
            spread_vs_std_pct = assessment["spread_vs_std_pct"]

            # Concise, truthful badges without overclaiming
            badges = []
            if is_lm and spread_vs_std_pln is not None and spread_vs_std_pln > 50:
                badges.append(f"Регулярный дешевле −{int(abs(spread_vs_std_pln))} zł")
            elif is_lm and delta_vs_typical is not None and delta_vs_typical <= -15.0:
                badges.append(f"Сброс −{abs(delta_vs_typical):.0f}%")

            if has_sufficient_history and curr_price <= hist_min * 1.01 and hopper_verdict == "BUY NOW":
                badges.append("Исторический минимум")
            if has_local_history and chg_48h <= -3.0:
                badges.append(f"Снижение 48ч ({chg_48h}%)")
            elif has_local_history and chg_24h <= -3.0:
                badges.append(f"Снижение 24ч ({chg_24h}%)")
            if deal_score >= 80 and not is_lm and hopper_verdict == "BUY NOW":
                badges.append("Выгодная цена")

            if is_lm and days_to_dep is not None:
                if days_to_dep == 0:
                    badges.append("⚡ Вылет сегодня")
                elif days_to_dep == 1:
                    badges.append("⚡ Вылет завтра")
                elif days_to_dep <= 4:
                    badges.append(f"⚡ Вылет через {days_to_dep} дн.")

            # Formatted strings
            checkin_str = checkin_dt.strftime("%Y-%m-%d") if hasattr(checkin_dt, "strftime") else str(checkin_dt)
            last_updated_str = (
                last_rec_at.isoformat()
                if hasattr(last_rec_at, "isoformat")
                else str(last_rec_at)
            )

            cards.append({
                "hotel_id": h_id,
                "display_name": disp_name,
                "country": country,
                "region": region or country,
                "stars": stars_val or 4,
                "ta_rating": final_ta_rating,
                "ta_reviews": final_ta_reviews,
                "main_image_url": img_url,
                "current_min_price": curr_price,
                "typical_median_price": typical_med,
                "historical_min_price": hist_min,
                "historical_max_price": hist_max,
                "delta_vs_typical_pct": delta_vs_typical,
                "change_24h_pct": chg_24h,
                "change_48h_pct": chg_48h,
                "change_7d_pct": chg_7d,
                "change_30d_pct": chg_30d,
                "deal_score": deal_score,
                "deal_confidence": confidence,
                "hopper_verdict": hopper_verdict,
                "action_label": action_label,
                "recommendation": recommendation,
                "upcoming_std_price": std_info["price"] if std_info else None,
                "upcoming_std_date": std_info["date"] if std_info else None,
                "upcoming_std_airport": std_info["airport"] if std_info else None,
                "spread_vs_std_pln": spread_vs_std_pln,
                "spread_vs_std_pct": spread_vs_std_pct,
                "badges": badges,
                "beach_line": beach_line,
                "beach_type": beach_type,
                "has_aquapark": has_aquapark,
                "has_heated_pools": has_heated_pools,
                "cheapest_checkin_date": checkin_str,
                "cheapest_duration_nights": dur_nights or 7,
                "cheapest_airport_code": norm_air or "WAW",
                "board_basis": norm_brd,
                "cheapest_offer_url": offer_url,
                "cohort_hash": cohort_hash,
                "last_updated": last_updated_str,
            })

        return cards, max_ts
