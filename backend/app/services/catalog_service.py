import logging
import re
import statistics
import time
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta, timezone
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger("travel_monitor_2.catalog")

from app.services.timeline_service import resolve_filter_id, get_all_filter_id_variants
from app.services.hotel_deal_score import compute_hotel_deal_metrics
from app.services.hotel_knowledge_service import HotelKnowledgeService

_CATALOG_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
_CACHE_TTL_SECONDS = 180  # 3 minutes in-memory cache


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
        if canonical_fid in _CATALOG_CACHE:
            c_time, c_cards = _CATALOG_CACHE[canonical_fid]
            if now_ts - c_time < _CACHE_TTL_SECONDS:
                cards = c_cards

        if cards is None:
            cards = await cls._compute_catalog_cards(db, filter_id, canonical_fid)
            _CATALOG_CACHE[canonical_fid] = (now_ts, cards)

        # 5. Apply filters
        filtered_cards = list(cards)
        if stars:
            filtered_cards = [c for c in filtered_cards if c["stars"] == stars]
        if search_query:
            sq = search_query.strip().lower()
            filtered_cards = [c for c in filtered_cards if sq in c["display_name"].lower()]
        if min_price is not None:
            filtered_cards = [c for c in filtered_cards if c["current_min_price"] >= min_price]
        if max_price is not None:
            filtered_cards = [c for c in filtered_cards if c["current_min_price"] <= max_price]

        # 6. Sorting
        reverse_order = order.lower() == "desc"
        if sort_by == "deal_score":
            filtered_cards.sort(key=lambda x: x["deal_score"], reverse=not reverse_order)
        elif sort_by == "ta_rating":
            filtered_cards.sort(key=lambda x: (x["ta_rating"] or 0, x["ta_reviews"]), reverse=not reverse_order)
        elif sort_by == "discount_24h":
            filtered_cards.sort(key=lambda x: x["change_24h_pct"], reverse=reverse_order)
        else:  # default "price"
            filtered_cards.sort(key=lambda x: x["current_min_price"], reverse=reverse_order)

        return {
            "filter_id": filter_id,
            "total_hotels": len(filtered_cards),
            "hotels": filtered_cards,
        }

    @classmethod
    async def _compute_catalog_cards(
        cls,
        db: AsyncSession,
        filter_id: str,
        canonical_fid: str,
    ) -> List[Dict[str, Any]]:
        fids = get_all_filter_id_variants(filter_id)
        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False
        filter_expr = "ps.filter_id = ANY(:fids)" if is_pg else "ps.filter_id IN :fids"
        join_col = "cohort_id" if is_pg else "cohort_hash"

        # 1. Find the latest recorded scrape time for this filter
        stmt = text(f"SELECT MAX(ps.recorded_at) FROM price_snapshots ps WHERE {filter_expr}")
        if not is_pg:
            from sqlalchemy import bindparam
            stmt = stmt.bindparams(bindparam("fids", expanding=True))
        time_res = await db.execute(stmt, {"fids": fids})
        max_ts = time_res.scalar()

        if not max_ts:
            return []

        if isinstance(max_ts, str):
            ts_str = max_ts.replace("Z", "+00:00").replace(" ", "T")
            if "+" not in ts_str and not ts_str.endswith("Z"):
                ts_str += "+00:00"
            max_dt = datetime.fromisoformat(ts_str)
        else:
            max_dt = max_ts

        if max_dt.tzinfo is None:
            max_dt = max_dt.replace(tzinfo=timezone.utc)

        cutoff = (max_dt - timedelta(hours=4)) if is_pg else (max_dt - timedelta(hours=4)).isoformat()

        # 2. Query active hotels and their cheapest offer in the latest scrape run (using window partition)
        active_sql = f"""
            WITH ranked_offers AS (
                SELECT 
                    h.hotel_id,
                    h.display_name,
                    h.country,
                    h.stars,
                    h.ta_rating,
                    h.ta_reviews,
                    h.main_image_url,
                    oc.checkin_date,
                    oc.duration_nights,
                    oc.airport_code,
                    oc.offer_url,
                    ps.total_price_pln as current_price,
                    ps.recorded_at,
                    ROW_NUMBER() OVER (PARTITION BY h.hotel_id ORDER BY ps.total_price_pln ASC, ps.recorded_at DESC) as rn
                FROM price_snapshots ps
                JOIN offer_cohorts oc ON ps.{join_col} = oc.{join_col}
                JOIN hotels h ON oc.hotel_id = h.hotel_id
                WHERE {filter_expr}
                  AND ps.recorded_at >= :cutoff
            )
            SELECT 
                hotel_id,
                display_name,
                country,
                stars,
                ta_rating,
                ta_reviews,
                main_image_url,
                checkin_date,
                duration_nights,
                airport_code,
                offer_url,
                current_price,
                recorded_at
            FROM ranked_offers
            WHERE rn = 1
            ORDER BY current_price ASC;
        """
        a_stmt = text(active_sql)
        if not is_pg:
            from sqlalchemy import bindparam
            a_stmt = a_stmt.bindparams(bindparam("fids", expanding=True))

        active_res = await db.execute(a_stmt, {"fids": fids, "cutoff": cutoff})
        active_rows = active_res.fetchall()

        if not active_rows:
            # Wider window fallback if last scrape was slightly sparse
            cutoff_24h = (max_dt - timedelta(hours=24)) if is_pg else (max_dt - timedelta(hours=24)).isoformat()
            active_res = await db.execute(a_stmt, {"fids": fids, "cutoff": cutoff_24h})
            active_rows = active_res.fetchall()

        if not active_rows:
            return []

        hotel_ids = [r[0] for r in active_rows]

        # 3. Expand hotel IDs to query variants (e.g. viva-sharm and viva-sharm-hotel)
        def _get_id_variants(hid: str) -> Set[str]:
            res = {hid}
            base = re.sub(r"-(hotel|resort|spa|village|palace|beach)$", "", hid)
            res.add(base)
            res.add(f"{base}-hotel")
            res.add(f"{base}-resort")
            return res

        all_query_hids: Set[str] = set()
        variant_to_primary: Dict[str, Set[str]] = {}
        for hid in hotel_ids:
            vars_set = _get_id_variants(hid)
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
            ) = row

            curr_price = float(curr_price)
            hist_pts = hotel_history.get(h_id, [])
            stats_tuple = hotel_stats.get(h_id)

            if stats_tuple:
                hist_min = round(stats_tuple[0], 0)
                hist_max = round(stats_tuple[1], 0)
            elif hist_pts:
                all_p = [p[1] for p in hist_pts]
                hist_min = round(min(all_p), 0)
                hist_max = round(max(all_p), 0)
            else:
                hist_min = curr_price
                hist_max = curr_price

            if hist_pts:
                all_prices = [p[1] for p in hist_pts]
                typical_med = round(statistics.median(all_prices), 0)

                # Look for price ~24h ago and ~7d ago
                latest_dt = hist_pts[-1][0]
                dt_24h_target = latest_dt - timedelta(hours=24)
                dt_7d_target = latest_dt - timedelta(days=7)

                p_24h = None
                p_7d = None

                for dt, p in reversed(hist_pts):
                    if p_24h is None and dt <= dt_24h_target:
                        p_24h = p
                    if p_7d is None and dt <= dt_7d_target:
                        p_7d = p
                    if p_24h is not None and p_7d is not None:
                        break

                chg_24h = round((curr_price - p_24h) / p_24h * 100.0, 1) if p_24h else 0.0
                chg_7d = round((curr_price - p_7d) / p_7d * 100.0, 1) if p_7d else 0.0
            else:
                typical_med = curr_price
                chg_24h = 0.0
                chg_7d = 0.0

            delta_vs_typical = (
                round((curr_price - typical_med) / typical_med * 100.0, 1)
                if typical_med > 0
                else 0.0
            )

            # Knowledge base enrichment (accurate beach line, TripAdvisor rating, and infrastructure)
            dossier = HotelKnowledgeService.get_hotel_dossier(
                hotel_name=disp_name,
                destination=country,
                country=country,
                stars=stars_val or 4,
                current_price=curr_price,
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

            # Deal Score calculation using mathematical V1 model (plateau segments, volatility, TA blend)
            if hist_pts:
                df_hist = pd.DataFrame(hist_pts, columns=["scraped_at", "price"])
                deal_metrics = compute_hotel_deal_metrics(
                    df_hist,
                    latest_price=curr_price,
                    time_col="scraped_at",
                    price_col="price",
                    ta_rating=final_ta_rating,
                    ta_review_count=final_ta_reviews,
                )
                deal_score = int(deal_metrics.get("deal_score", 50))
                confidence = deal_metrics.get("confidence", "Medium")
            else:
                deal_score = 50
                confidence = "Low"

            # Badges
            badges = []
            if curr_price <= hist_min * 1.01:
                badges.append("Исторический минимум")
            if chg_24h <= -3.0:
                badges.append(f"Снижение за 24ч ({chg_24h}%)")
            if deal_score >= 80:
                badges.append("Выгодная цена")

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
                "change_7d_pct": chg_7d,
                "deal_score": deal_score,
                "deal_confidence": confidence,
                "badges": badges,
                "beach_line": beach_line,
                "beach_type": beach_type,
                "has_aquapark": has_aquapark,
                "has_heated_pools": has_heated_pools,
                "cheapest_checkin_date": checkin_str,
                "cheapest_duration_nights": dur_nights or 7,
                "cheapest_airport_code": airport_code or "WAW",
                "cheapest_offer_url": offer_url,
                "last_updated": last_updated_str,
            })

        return cards
