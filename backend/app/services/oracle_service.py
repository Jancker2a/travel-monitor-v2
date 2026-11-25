import logging
import os
import statistics
import time
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, date, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, bindparam

from app.services.timeline_service import resolve_filter_id, get_all_filter_id_variants
from app.services.canonical_filters import resolve_filter_spec, classify_filter_type
from app.services import ai_market_oracle

logger = logging.getLogger("travel_monitor_2.oracle")

_ORACLE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_ORACLE_CACHE_TTL = 300.0  # 5 minutes


class OracleService:
    @classmethod
    async def get_filter_oracle(cls, db: AsyncSession, filter_id: str) -> Dict[str, Any]:
        """
        Synthesizes the AI Market Intelligence Briefing for a filter.
        Computes market phase, flight dynamics, floor breaker statistics,
        and 'If buying now' top recommendations with exact parity to v1.
        """
        canonical_fid = resolve_filter_id(filter_id)
        now_ts = time.time()
        if canonical_fid in _ORACLE_CACHE:
            c_time, c_data = _ORACLE_CACHE[canonical_fid]
            if now_ts - c_time < _ORACLE_CACHE_TTL:
                return c_data
        fids = get_all_filter_id_variants(filter_id)
        is_pg = (db.bind.dialect.name == "postgresql") if db.bind else False
        cohort_col = "cohort_id"
        filter_expr = "ps.filter_id = ANY(:fids)" if is_pg else "ps.filter_id IN :fids"

        # 1. Fetch monitor metadata
        m_sql = "SELECT id, title, destination FROM filter_monitors WHERE id = :fid"
        m_res = await db.execute(text(m_sql), {"fid": canonical_fid})
        m_row = m_res.fetchone()

        if not m_row and canonical_fid != filter_id:
            m_res = await db.execute(text(m_sql), {"fid": filter_id})
            m_row = m_res.fetchone()
            canonical_fid = filter_id

        if not m_row:
            clean_uid = filter_id.replace("monitor_", "").replace("user_", "").replace("filter_", "")
            u_sql = "SELECT id, title, filter_params_json FROM user_monitors WHERE id = :uid"
            u_res = await db.execute(text(u_sql), {"uid": clean_uid})
            u_row = u_res.fetchone()
            if u_row:
                import json
                try:
                    u_params = json.loads(u_row[2]) if u_row[2] else {}
                except Exception:
                    u_params = {}
                title = u_row[1]
                dest = u_params.get("destination") or "egypt"
                m_row = (u_row[0], title, dest)

        title = m_row[1] if m_row else filter_id
        dest = m_row[2] if m_row else "egypt"

        # 2. Fetch latest offers for this filter
        stmt = text(f"SELECT MAX(ps.recorded_at) FROM price_snapshots ps WHERE {filter_expr}")
        if not is_pg:
            from sqlalchemy import bindparam
            stmt = stmt.bindparams(bindparam("fids", expanding=True))
        time_res = await db.execute(stmt, {"fids": fids})
        max_ts = time_res.scalar()

        if not max_ts:
            return {
                "filter_id": filter_id,
                "title": title,
                "headline": "Мониторинг активен: зафиксирован первый срез цен",
                "market_phase": "Начало отслеживания",
                "charter_dynamics": f"Сбор актуальных предложений по направлению {dest.capitalize()} запущен. По мере накопления истории (замеры каждые 3ч) здесь появится прогноз лучшего момента покупки и анализ чартерной загрузки.",
                "floor_status": "История цен накапливается.",
                "strategic_directive": "Мониторинг обновляется каждые 3 часа. Нажмите «Обновить ⚡» для немедленного замера.",
                "buy_now_recommendation": {"has_worthy_deals": False, "top_picks": []},
                "key_anomalies": [],
            }

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

        offers_sql = f"""
            WITH ranked_offers AS (
                SELECT 
                    h.hotel_id,
                    h.display_name,
                    h.stars,
                    h.ta_rating,
                    h.ta_reviews,
                    oc.checkin_date,
                    oc.duration_nights,
                    oc.airport_code,
                    oc.offer_url,
                    ps.total_price_pln as current_price,
                    ps.recorded_at,
                    ROW_NUMBER() OVER (PARTITION BY h.hotel_id ORDER BY ps.total_price_pln ASC, ps.recorded_at DESC) as rn
                FROM price_snapshots ps
                JOIN offer_cohorts oc ON ps.{cohort_col} = oc.{cohort_col}
                JOIN hotels h ON oc.hotel_id = h.hotel_id
                WHERE {filter_expr}
                  AND ps.recorded_at >= :cutoff
            )
            SELECT 
                hotel_id,
                display_name,
                stars,
                ta_rating,
                ta_reviews,
                checkin_date,
                duration_nights,
                airport_code,
                offer_url,
                current_price
            FROM ranked_offers
            WHERE rn = 1
            ORDER BY current_price ASC;
        """
        o_stmt = text(offers_sql)
        if not is_pg:
            o_stmt = o_stmt.bindparams(bindparam("fids", expanding=True))

        res = await db.execute(o_stmt, {"fids": fids, "cutoff": cutoff})
        rows = res.fetchall()

        if not rows:
            # Fallback to 24h cutoff
            cutoff_24h = (max_dt - timedelta(hours=24)) if is_pg else (max_dt - timedelta(hours=24)).isoformat()
            res = await db.execute(o_stmt, {"fids": fids, "cutoff": cutoff_24h})
            rows = res.fetchall()

        if not rows:
            return {
                "filter_id": filter_id,
                "title": title,
                "headline": "Данные обновляются",
                "market_phase": "Ожидание данных",
                "charter_dynamics": "Сбор актуальных предложений для этого направления продолжается...",
                "floor_status": "",
                "strategic_directive": "Проверьте фильтр через несколько минут.",
                "buy_now_recommendation": {"has_worthy_deals": False, "top_picks": []},
                "key_anomalies": [],
                "synthesized_by": "Аналитический движок (данные БД)",
            }

        prices = sorted(float(r[9]) for r in rows if r[9])
        median_price = prices[len(prices) // 2] if prices else 0.0
        min_price = prices[0] if prices else 0.0

        # Calculate days to departure + next realistic flight (if today flights exist)
        today = date.today()
        days_list: List[int] = []
        valid_dates: List[date] = []
        today_count = 0
        for r in rows:
            c_date_val = r[5]
            if c_date_val:
                try:
                    if isinstance(c_date_val, datetime):
                        c_date = c_date_val.date()
                    elif isinstance(c_date_val, date):
                        c_date = c_date_val
                    else:
                        c_date = datetime.strptime(str(c_date_val)[:10], "%Y-%m-%d").date()
                    d_diff = (c_date - today).days
                    if d_diff >= 0:
                        days_list.append(d_diff)
                        valid_dates.append(c_date)
                        if d_diff == 0:
                            today_count += 1
                except Exception as e:
                    logger.debug(f"Date parse error: {e}")

        min_days = min(days_list) if days_list else 14
        max_days = max(days_list) if days_list else 28
        sorted_days = sorted(days_list)
        med_days = sorted_days[len(sorted_days) // 2] if sorted_days else 21
        nearest_dep = min(valid_dates).strftime("%d.%m") if valid_dates else ""
        furthest_dep = max(valid_dates).strftime("%d.%m") if valid_dates else ""
        future_pairs = sorted((d, dt) for d, dt in zip(days_list, valid_dates) if d >= 1)
        next_real_d = future_pairs[0][0] if future_pairs else min_days
        next_real_dep = future_pairs[0][1].strftime("%d.%m") if future_pairs else nearest_dep

        spec = resolve_filter_spec(filter_id) or resolve_filter_spec(canonical_fid)
        filter_type = classify_filter_type(canonical_fid, title=title, checkin_dates=valid_dates)

        target_adults = int((spec or {}).get("adults", 1 if "_1p" in canonical_fid else 2))
        target_children = int((spec or {}).get("children", 0 if target_adults == 1 else 1))
        if target_adults == 1 and target_children == 0:
            price_scope = "на 1 взрослого"
        elif target_adults == 2 and target_children == 0:
            price_scope = "за двоих взрослых"
        else:
            price_scope = f"на семью ({target_adults} взр. + {target_children} реб.)"

        nights_list = [int(r[6]) for r in rows if r[6]]
        med_nights = int(statistics.median(nights_list)) if nights_list else int((spec or {}).get("duration_min", 7))
        cost_per_day_med = round(median_price / max(1, med_nights), 0) if median_price else 0

        # Destination context and climate advice
        dest_advice = {
            "egypt": {
                "country": "Египет",
                "climate_and_weather_advice": "Теплое море, солнце круглый год. Зимой критичны безветренная бухта и подогреваемый бассейн.",
            },
            "turkey": {
                "country": "Турция",
                "climate_and_weather_advice": "Анталийское и Эгейское побережье, развитый All Inclusive и семейная инфраструктура.",
            },
            "greece": {
                "country": "Греция",
                "climate_and_weather_advice": "Островные курорты с мягким средиземноморским климатом и короткими чартерами.",
            },
            "cyprus": {
                "country": "Кипр",
                "climate_and_weather_advice": "Длинный купальный сезон и стабильный европейский сервис.",
            },
        }.get(dest.lower(), {
            "country": dest.capitalize(),
            "climate_and_weather_advice": "Стабильные курортные условия для пакетного отдыха.",
        })

        # Full historical stats per hotel in this filter (min, avg/med, count)
        hist_stats_sql = f"""
            SELECT oc.hotel_id,
                   MIN(ps.total_price_pln) as hist_min,
                   AVG(ps.total_price_pln) as hist_avg,
                   MAX(ps.total_price_pln) as hist_max,
                   COUNT(ps.id) as snaps_cnt
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.{cohort_col} = oc.{cohort_col}
            WHERE {filter_expr}
            GROUP BY oc.hotel_id;
        """
        hm_stmt = text(hist_stats_sql)
        if not is_pg:
            hm_stmt = hm_stmt.bindparams(bindparam("fids", expanding=True))
        h_res = await db.execute(hm_stmt, {"fids": fids})
        hist_stats_map: Dict[str, Tuple[float, float, float, int]] = {}
        for hid, hmin, havg, hmax, hcnt in h_res.fetchall():
            hist_stats_map[hid] = (
                float(hmin or 0.0),
                float(havg or 0.0),
                float(hmax or 0.0),
                int(hcnt or 0),
            )

        # Cross-filter 1:1 stats when this filter has young history (< 5 snaps per hotel)
        avg_snaps = statistics.mean([v[3] for v in hist_stats_map.values()]) if hist_stats_map else 0
        cross_med_map: Dict[str, Tuple[float, float, int]] = {}
        if avg_snaps < 5 and rows:
            dur_lo = max(1, med_nights - 2)
            dur_hi = med_nights + 2
            hids_only = [r[0] for r in rows]
            c_ph = ",".join(f":ch{i}" for i in range(len(hids_only)))
            c_params: Dict[str, Any] = {f"ch{i}": hid for i, hid in enumerate(hids_only)}
            c_params["ad"] = target_adults
            c_params["ch"] = target_children
            c_params["dl"] = dur_lo
            c_params["dh"] = dur_hi
            c_sql = f"""
                SELECT oc.hotel_id, MIN(ps.total_price_pln), AVG(ps.total_price_pln), COUNT(ps.id)
                FROM price_snapshots ps
                JOIN offer_cohorts oc ON ps.{cohort_col} = oc.{cohort_col}
                WHERE oc.hotel_id IN ({c_ph})
                  AND oc.adults = :ad AND oc.children = :ch
                  AND oc.duration_nights BETWEEN :dl AND :dh
                GROUP BY oc.hotel_id
                HAVING COUNT(ps.id) >= 3
            """
            for chid, cmin, cavg, ccnt in (await db.execute(text(c_sql), c_params)).fetchall():
                cross_med_map[chid] = (float(cmin or 0), float(cavg or 0), int(ccnt or 0))

        # Airport breakdown from active filter offers (48h)
        apt_sql = f"""
            SELECT oc.airport_code,
                   COUNT(DISTINCT oc.hotel_id) as h_cnt,
                   AVG(ps.total_price_pln) as avg_p,
                   MIN(ps.total_price_pln) as min_p
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.{cohort_col} = oc.{cohort_col}
            WHERE {filter_expr}
              AND ps.recorded_at >= :cutoff_48h
              AND oc.airport_code IS NOT NULL
            GROUP BY oc.airport_code
            HAVING COUNT(*) >= 3
            ORDER BY avg_p ASC
        """
        apt_stmt = text(apt_sql)
        if not is_pg:
            apt_stmt = apt_stmt.bindparams(bindparam("fids", expanding=True))
        c48_val = (max_dt - timedelta(hours=48)) if is_pg else (max_dt - timedelta(hours=48)).isoformat()
        apt_rows = (await db.execute(apt_stmt, {"fids": fids, "cutoff_48h": c48_val})).fetchall()
        airports_comparison: Dict[str, Any] = {"multi_airport": False}
        if len(apt_rows) >= 2:
            cheapest = apt_rows[0]
            expensive = apt_rows[-1]
            spread = round(float(expensive[2] or 0) - float(cheapest[2] or 0), 0)
            airports_comparison = {
                "multi_airport": True,
                "cheapest_hub": cheapest[0],
                "cheapest_avg_pln": round(float(cheapest[2] or 0), 0),
                "expensive_hub": expensive[0],
                "expensive_avg_pln": round(float(expensive[2] or 0), 0),
                "spread_pln": spread,
                "insight": f"Вылеты из {cheapest[0]} в среднем на {spread:,.0f} zł дешевле, чем из {expensive[0]}.",
                "hubs": [
                    {"airport": r[0], "hotels": int(r[1]), "avg_price": round(float(r[2] or 0), 0), "min_price": round(float(r[3] or 0), 0)}
                    for r in apt_rows
                ],
            }

        # Market 7-day trend
        market_trends: Dict[str, Any] = {}
        c7_start = (max_dt - timedelta(days=9)) if is_pg else (max_dt - timedelta(days=9)).isoformat()
        c7_end = (max_dt - timedelta(days=6)) if is_pg else (max_dt - timedelta(days=6)).isoformat()
        tr_sql = f"""
            SELECT AVG(ps.total_price_pln)
            FROM price_snapshots ps
            WHERE {filter_expr}
              AND ps.recorded_at BETWEEN :t_start AND :t_end
        """
        tr_stmt = text(tr_sql)
        if not is_pg:
            tr_stmt = tr_stmt.bindparams(bindparam("fids", expanding=True))
        avg_7d_ago = (await db.execute(tr_stmt, {"fids": fids, "t_start": c7_start, "t_end": c7_end})).scalar()
        avg_now = statistics.mean(prices) if prices else 0.0
        if avg_7d_ago and float(avg_7d_ago) > 0 and avg_now > 0:
            d_pln = round(avg_now - float(avg_7d_ago), 0)
            d_pct = round((d_pln / float(avg_7d_ago)) * 100.0, 1)
            market_trends = {"trend_7d_pct": d_pct, "delta_7d_pln": d_pln}

        # Build quantitative intelligence per hotel (truthful ratings & real drops)
        all_hotel_intel: Dict[str, Dict[str, Any]] = {}
        top_candidates: List[Dict[str, Any]] = []
        flash_drops: List[Dict[str, Any]] = []
        gems: List[Dict[str, Any]] = []
        floor_count = 0

        # Group prices by star tier for peer comparison (fair price)
        star_pools: Dict[int, List[float]] = {}
        for r in rows:
            st = int(r[2] or 4)
            star_pools.setdefault(st, []).append(float(r[9] or 0.0))
        star_medians = {st: statistics.median(vals) for st, vals in star_pools.items() if vals}

        for idx, r in enumerate(rows):
            hid, hname, hstars, ta_r, ta_cnt, _, _, hair, hurl, cur_p_raw = r
            cur_p = float(cur_p_raw or 0.0)
            st = int(hstars or 4)
            h_stat = hist_stats_map.get(hid)
            c_stat = cross_med_map.get(hid)

            if h_stat and h_stat[3] >= 5:
                h_min, h_med, h_max, h_cnt = h_stat
            elif c_stat and c_stat[2] >= 5:
                h_min, h_med, h_max, h_cnt = c_stat[0], c_stat[1], cur_p, c_stat[2]
            elif h_stat:
                h_min, h_med, h_max, h_cnt = h_stat
            else:
                h_min, h_med, h_max, h_cnt = cur_p, cur_p, cur_p, 1

            has_hist = h_cnt >= 3 and h_med > 0
            if has_hist and cur_p <= h_min * 1.01 and h_med >= cur_p * 1.03:
                floor_count += 1

            delta_vs_med_pct = round(((cur_p - h_med) / h_med) * 100.0, 1) if has_hist else 0.0
            is_flash = has_hist and cur_p < h_min * 1.01 and delta_vs_med_pct <= -15.0
            drop_pct_vs_med = abs(delta_vs_med_pct) if is_flash else 0.0

            peer_med = star_medians.get(st, median_price) or cur_p
            fp_delta_pct = round(((cur_p - peer_med) / peer_med) * 100.0, 1) if peer_med > 0 else 0.0
            if fp_delta_pct <= -12.0:
                fp_class = "fair-underpriced"
            elif fp_delta_pct >= 15.0:
                fp_class = "fair-overpriced"
            else:
                fp_class = "fair"

            real_ta = float(ta_r) if (ta_r is not None and float(ta_r) > 0) else 0.0
            real_ta_cnt = int(ta_cnt or 0)
            is_gem = bool(real_ta >= 4.4 and real_ta_cnt >= 20 and fp_delta_pct <= -10.0 and delta_vs_med_pct <= 2.0)

            bw_class = "panic" if min_days <= 4 else ("in_window" if delta_vs_med_pct <= -10.0 else "early")
            bw_badge = (
                "⚡ Горящее окно" if filter_type == "lastminute"
                else ("🎯 В окне скидки" if delta_vs_med_pct <= -10.0 else "")
            )

            intel_obj = {
                "hotel_id": hid,
                "hotel_name": hname,
                "stars": st,
                "current_price": cur_p,
                "historical_min": h_min,
                "historical_median": h_med,
                "historical_max": h_max,
                "samples_count": h_cnt,
                "rating": real_ta,
                "ta_rating": real_ta,
                "review_count": real_ta_cnt,
                "departure_airport": hair or "WAW",
                "offer_url": hurl or "",
                "quantile_in_filter": round(idx / max(1, len(rows)), 2),
                "flash_drop": {
                    "is_flash": is_flash,
                    "drop_pct": drop_pct_vs_med,
                    "badge": f"⚡ −{drop_pct_vs_med:.0f}%" if is_flash else "",
                    "tip": "",
                },
                "fair_price": {
                    "class": fp_class,
                    "delta_pct": fp_delta_pct,
                    "tier": f"{st}★",
                    "stars": st,
                    "badge": "",
                    "tip": "",
                },
                "gem": {
                    "is_gem": is_gem,
                    "rating": real_ta,
                    "badge": f"💎 {real_ta:g}★" if is_gem else "",
                    "tip": "",
                },
                "booking_window": {
                    "window_class": bw_class,
                    "window_badge": bw_badge,
                    "optimal_window": "сейчас",
                    "window_tip": "",
                },
            }
            all_hotel_intel[hname] = intel_obj

            if is_flash and len(flash_drops) < 3:
                flash_drops.append({"hotel_name": hname, "current_price": cur_p, "drop_pct": drop_pct_vs_med})
            if is_gem and len(gems) < 3:
                gems.append({"hotel_name": hname, "price": cur_p, "rating": real_ta, "stars": st})
            if has_hist and delta_vs_med_pct <= -8.0 and real_ta >= 4.0 and len(top_candidates) < 10:
                top_candidates.append(intel_obj)

        floor_pct = round((floor_count / len(rows)) * 100, 1) if rows else 0.0

        early_booking_ctx: Dict[str, Any] = {}
        if filter_type == "early_booking" or min_days >= 45:
            try:
                from app.services.analytics_service import AnalyticsService
                eb_data = await AnalyticsService.get_early_booking_analytics(db, filter_id=filter_id)
                eb_sum = eb_data.get("summary") or {}
                if eb_data.get("has_data"):
                    early_booking_ctx = {
                        "verdict": eb_sum.get("verdict"),
                        "ebas_score": eb_sum.get("ebas_score"),
                        "sold_out_rate_at_14d": round(float(eb_sum.get("sold_out_risk_pct", 0.0)) / 100.0, 2),
                    }
            except Exception as eb_err:
                logger.debug(f"EB context fetch skipped: {eb_err}")

        market_context = {
            "filter_id": canonical_fid,
            "filter_title": title,
            "filter_type": filter_type,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "market_stats": {
                "hotel_count": len(rows),
                "median_price": median_price,
                "min_price": min_price,
                "p10_price": prices[min(len(prices) - 1, int(len(prices) * 0.1))],
                "min_days_to_departure": min_days,
                "max_days_to_departure": max_days,
                "median_days_to_departure": med_days,
                "nearest_departure_date": nearest_dep,
                "furthest_departure_date": furthest_dep,
                "has_today_departures": min_days == 0,
                "today_departures_count": today_count,
                "next_realistic_days_to_departure": next_real_d,
                "next_realistic_departure_date": next_real_dep,
                "is_wide_window": (max_days - min_days) > 10,
                "destination_context": dest_advice,
                "tourists": {"adults": target_adults, "children": target_children, "price_scope": price_scope},
                "trip_duration": {
                    "nights": med_nights,
                    "label": f"{med_nights} ночей",
                    "is_long_trip": med_nights >= 12,
                    "cost_per_day_median_pln": cost_per_day_med,
                },
            },
            "floor_saturation": {
                "floor_breaker_count": floor_count,
                "floor_breaker_pct": floor_pct,
            },
            "airports_comparison": airports_comparison,
            "market_trends": market_trends,
            "early_booking": early_booking_ctx,
            "all_hotel_intelligence": all_hotel_intel,
            "top_candidates": top_candidates,
            "flash_drops": flash_drops,
            "gems": gems,
            "raw_offers": [
                {
                    "hotel_id": r[0],
                    "hotel_name": r[1],
                    "price": float(r[9]),
                    "ta_rating": float(r[3]) if r[3] else None,
                    "ta_review_count": int(r[4] or 0),
                    "departure_airport": r[7],
                    "duration": f"{r[6]} dni",
                }
                for r in rows
            ],
        }

        # Synthesize intelligence: try LLM first if API key is present, fallback to deterministic engine
        gem_key = os.getenv("GEMINI_API_KEY")
        oai_key = os.getenv("OPENAI_API_KEY")
        provider_pref = os.getenv("LLM_PROVIDER", "").lower()
        report = None

        # 1. If OpenAI is explicitly preferred or only OpenAI is configured
        if (provider_pref == "openai" or not gem_key) and oai_key:
            try:
                logger.info(f"Invoking OpenAI LLM for filter {canonical_fid}...")
                report = ai_market_oracle.call_openai_oracle(market_context, oai_key)
            except Exception as e:
                logger.warning(f"OpenAI oracle call failed: {e}")

        # 2. Otherwise try Gemini
        if not report and gem_key:
            try:
                logger.info(f"Invoking Gemini LLM for filter {canonical_fid}...")
                report = ai_market_oracle.call_gemini_oracle(market_context, gem_key)
            except Exception as e:
                logger.warning(f"Gemini oracle call failed, falling back: {e}")

        # 3. Fallback to OpenAI if Gemini was attempted and failed
        if not report and oai_key:
            try:
                logger.info(f"Falling back to OpenAI LLM for filter {canonical_fid}...")
                report = ai_market_oracle.call_openai_oracle(market_context, oai_key)
            except Exception as e:
                logger.warning(f"OpenAI fallback call failed: {e}")

        # 4. Final fallback to rule-based engine
        if not report:
            report = ai_market_oracle.generate_rule_based_briefing(market_context)

        macro = report.get("macro_briefing", {})

        res = {
            "filter_id": filter_id,
            "filter_type": filter_type,
            "title": title,
            "headline": macro.get("headline", ""),
            "market_phase": macro.get("market_phase", ""),
            "charter_dynamics": macro.get("charter_dynamics", ""),
            "floor_status": macro.get("floor_status", ""),
            "strategic_directive": macro.get("strategic_directive", ""),
            "buy_now_recommendation": macro.get("buy_now_recommendation", {}),
            "key_anomalies": macro.get("key_anomalies", []),
            "synthesized_by": macro.get("synthesized_by", "Аналитический движок (данные БД)"),
        }
        _ORACLE_CACHE[canonical_fid] = (now_ts, res)
        return res

