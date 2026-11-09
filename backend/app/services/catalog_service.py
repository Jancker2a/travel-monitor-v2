import logging
import statistics
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger("travel_monitor_2.catalog")

from app.services.timeline_service import resolve_filter_id


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

        # 1. Find the latest recorded scrape time for this filter
        time_res = await db.execute(
            text("""
                SELECT MAX(ps.recorded_at) 
                FROM price_snapshots ps
                JOIN offer_cohorts oc ON ps.cohort_hash = oc.cohort_hash
                WHERE (ps.filter_id = :fid OR oc.destination_code = :fid)
            """),
            {"fid": canonical_fid},
        )
        max_ts = time_res.scalar()

        if not max_ts and canonical_fid != filter_id:
            time_res = await db.execute(
                text("""
                    SELECT MAX(ps.recorded_at) 
                    FROM price_snapshots ps
                    JOIN offer_cohorts oc ON ps.cohort_hash = oc.cohort_hash
                    WHERE (ps.filter_id = :fid OR oc.destination_code = :fid)
                """),
                {"fid": filter_id},
            )
            max_ts = time_res.scalar()
            canonical_fid = filter_id

        if not max_ts:
            return {"filter_id": filter_id, "total_hotels": 0, "hotels": []}

        if isinstance(max_ts, str):
            ts_str = max_ts.replace("Z", "+00:00").replace(" ", "T")
            if "+" not in ts_str and not ts_str.endswith("Z"):
                ts_str += "+00:00"
            max_dt = datetime.fromisoformat(ts_str)
        else:
            max_dt = max_ts

        if max_dt.tzinfo is None:
            max_dt = max_dt.replace(tzinfo=timezone.utc)

        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False
        cutoff = (max_dt - timedelta(hours=4)) if is_pg else (max_dt - timedelta(hours=4)).isoformat()

        # 2. Query active hotels and their cheapest offer in the latest scrape run (using window partition)
        active_sql = """
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
                JOIN offer_cohorts oc ON ps.cohort_hash = oc.cohort_hash
                JOIN hotels h ON oc.hotel_id = h.hotel_id
                WHERE (ps.filter_id = :fid OR oc.destination_code = :fid)
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
        active_res = await db.execute(text(active_sql), {"fid": canonical_fid, "cutoff": cutoff})
        active_rows = active_res.fetchall()

        if not active_rows:
            # Wider window fallback if last scrape was slightly sparse
            cutoff_24h = (max_dt - timedelta(hours=24)) if is_pg else (max_dt - timedelta(hours=24)).isoformat()
            active_res = await db.execute(text(active_sql), {"fid": canonical_fid, "cutoff": cutoff_24h})
            active_rows = active_res.fetchall()

        if not active_rows:
            return {"filter_id": filter_id, "total_hotels": 0, "hotels": []}

        hotel_ids = [r[0] for r in active_rows]

        # 3. Batch fetch all historical snapshots for these hotels under this filter
        placeholders = ",".join(f":h{i}" for i in range(len(hotel_ids)))
        h_params = {f"h{i}": hid for i, hid in enumerate(hotel_ids)}
        h_params["fid"] = canonical_fid

        hist_sql = f"""
            SELECT 
                oc.hotel_id,
                ps.recorded_at,
                ps.total_price_pln
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.cohort_hash = oc.cohort_hash
            WHERE (ps.filter_id = :fid OR oc.destination_code = :fid)
              AND oc.hotel_id IN ({placeholders})
            ORDER BY ps.recorded_at ASC;
        """
        hist_res = await db.execute(text(hist_sql), h_params)
        hist_rows = hist_res.fetchall()

        # Group history points by hotel_id
        hotel_history: Dict[str, List[Tuple[datetime, float]]] = {}
        for h_id, r_at, p_val in hist_rows:
            if h_id not in hotel_history:
                hotel_history[h_id] = []
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
            hotel_history[h_id].append((dt, float(p_val)))

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

            if hist_pts:
                all_prices = [p[1] for p in hist_pts]
                hist_min = round(min(all_prices), 0)
                hist_max = round(max(all_prices), 0)
                typical_med = round(statistics.median(all_prices), 0)

                # Look for price ~24h ago
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
                hist_min = curr_price
                hist_max = curr_price
                typical_med = curr_price
                chg_24h = 0.0
                chg_7d = 0.0

            delta_vs_typical = (
                round((curr_price - typical_med) / typical_med * 100.0, 1)
                if typical_med > 0
                else 0.0
            )

            # Deal Score calculation
            rel_disc = (typical_med - curr_price) / typical_med if typical_med > 0 else 0.0
            score_discount = _clamp(50 + rel_disc * 200, 0, 100)

            # Bonus for recent price drop
            momentum_bonus = 0
            if chg_24h < -3.0:
                momentum_bonus = 15
            elif chg_24h > 3.0:
                momentum_bonus = -10

            # TripAdvisor quality blend
            ta_bonus = 0
            if ta_rating and float(ta_rating) >= 4.5:
                ta_bonus = 8
            elif ta_rating and float(ta_rating) >= 4.0:
                ta_bonus = 4

            raw_score = score_discount * 0.70 + (50 + momentum_bonus) * 0.20 + (50 + ta_bonus) * 0.10
            deal_score = int(round(_clamp(raw_score, 0, 100)))

            confidence = "High" if len(hist_pts) >= 20 else ("Medium" if len(hist_pts) >= 8 else "Low")

            # Badges
            badges = []
            if curr_price <= hist_min * 1.01:
                badges.append("Исторический минимум")
            if chg_24h <= -3.0:
                badges.append(f"Снижение за 24ч ({chg_24h}%)")
            if deal_score >= 80:
                badges.append("Выгодная цена")
            if ta_rating and float(ta_rating) >= 4.5:
                badges.append(f"Жемчужина {ta_rating}★")

            cards.append({
                "hotel_id": h_id,
                "display_name": disp_name,
                "country": country,
                "stars": stars_val or 4,
                "ta_rating": float(ta_rating) if ta_rating else None,
                "ta_reviews": int(ta_reviews or 0),
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
                "cheapest_checkin_date": checkin_dt,
                "cheapest_duration_nights": dur_nights or 7,
                "cheapest_airport_code": airport_code or "WAW",
                "cheapest_offer_url": offer_url,
                "last_updated": last_rec_at,
            })

        # 5. Apply filters
        filtered_cards = cards
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

