import logging
import os
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, date, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.timeline_service import resolve_filter_id, get_all_filter_id_variants
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
        cohort_col = "cohort_id" if is_pg else "cohort_hash"
        filter_expr = "ps.filter_id = ANY(:fids)" if is_pg else "ps.filter_id IN :fids"

        # 1. Fetch monitor metadata
        m_sql = "SELECT id, title, destination FROM filter_monitors WHERE id = :fid"
        m_res = await db.execute(text(m_sql), {"fid": canonical_fid})
        m_row = m_res.fetchone()

        if not m_row and canonical_fid != filter_id:
            m_res = await db.execute(text(m_sql), {"fid": filter_id})
            m_row = m_res.fetchone()
            canonical_fid = filter_id

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
                "headline": "Данные обновляются",
                "market_phase": "Ожидание данных",
                "charter_dynamics": "Сбор актуальных предложений для этого направления продолжается...",
                "floor_status": "",
                "strategic_directive": "Проверьте фильтр через несколько минут.",
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
            from sqlalchemy import bindparam
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
            }

        prices = [float(r[8]) for r in rows if r[8]]
        median_price = prices[len(prices) // 2] if prices else 0.0
        min_price = prices[0] if prices else 0.0

        # Calculate days to departure
        today = date.today()
        days_list = []
        valid_dates = []
        for r in rows:
            c_date_val = r[4]
            if c_date_val:
                try:
                    if isinstance(c_date_val, datetime):
                        c_date = c_date_val.date()
                    elif isinstance(c_date_val, date):
                        c_date = c_date_val
                    elif "-" in str(c_date_val):
                        c_date = datetime.strptime(str(c_date_val)[:10], "%Y-%m-%d").date()
                    else:
                        c_date = today
                    d_diff = (c_date - today).days
                    if d_diff >= 0:
                        days_list.append(d_diff)
                        valid_dates.append(c_date)
                except Exception as e:
                    logger.debug(f"Date parse error: {e}")

        min_days = min(days_list) if days_list else 14
        max_days = max(days_list) if days_list else 28
        med_days = days_list[len(days_list) // 2] if days_list else 21
        nearest_dep = min(valid_dates).strftime("%d.%m") if valid_dates else ""
        furthest_dep = max(valid_dates).strftime("%d.%m") if valid_dates else ""

        # Destination context and climate advice
        dest_advice = {
            "egypt": {
                "country": "Египет",
                "climate_and_weather_advice": "Теплое море (+23..+26°C), воздух днем +24..+28°C. Ключевой фактор комфорта — закрытая от зимних ветров бухта и подогреваемый бассейн.",
            },
            "turkey": {
                "country": "Турция",
                "climate_and_weather_advice": "Средиземноморский климат, отличная инфраструктура и сезонные скидки раннего бронирования.",
            },
            "greece": {
                "country": "Греция",
                "climate_and_weather_advice": "Мягкий климат, чистое море и стабильные цены на туры.",
            },
            "cyprus": {
                "country": "Кипр",
                "climate_and_weather_advice": "Мягкая погода, длинная береговая линия и высокий европейский уровень сервиса.",
            },
        }.get(dest.lower(), {
            "country": dest.capitalize(),
            "climate_and_weather_advice": "Хорошие погодные условия и стабильные цены.",
        })

        # Calculate floor saturation (hotels at season minimum)
        hist_min_sql = f"""
            SELECT oc.hotel_id, MIN(ps.total_price_pln) as hist_min
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.{cohort_col} = oc.{cohort_col}
            WHERE {filter_expr}
            GROUP BY oc.hotel_id;
        """
        hm_stmt = text(hist_min_sql)
        if not is_pg:
            from sqlalchemy import bindparam
            hm_stmt = hm_stmt.bindparams(bindparam("fids", expanding=True))
        h_res = await db.execute(hm_stmt, {"fids": fids})
        hist_mins = dict(h_res.fetchall())

        floor_count = sum(
            1 for r in rows if float(r[8]) <= float(hist_mins.get(r[0], 0.0)) * 1.01
        )
        floor_pct = round((floor_count / len(rows)) * 100, 1) if rows else 0.0

        market_context = {
            "filter_id": canonical_fid,
            "filter_title": title,
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
                "is_wide_window": (max_days - min_days) > 10,
                "destination_context": dest_advice,
            },
            "floor_saturation": {
                "floor_breaker_count": floor_count,
                "floor_breaker_pct": floor_pct,
            },
            "raw_offers": [
                {
                    "hotel_id": r[0],
                    "hotel_name": r[1],
                    "price": float(r[8]),
                    "ta_rating": float(r[2]) if r[2] else 4.0,
                    "ta_review_count": int(r[3] or 0),
                    "departure_airport": r[6],
                    "duration": f"{r[5]} dni",
                }
                for r in rows
            ],
        }

        # Synthesize intelligence: try LLM first if API key is present, fallback to deterministic engine
        gem_key = os.getenv("GEMINI_API_KEY")
        oai_key = os.getenv("OPENAI_API_KEY")
        report = None

        if gem_key:
            try:
                logger.info(f"Invoking Gemini LLM for filter {canonical_fid}...")
                report = ai_market_oracle.call_gemini_oracle(market_context, gem_key)
                if report and "macro_briefing" in report:
                    report["macro_briefing"]["synthesized_by"] = "Google Gemini 2.5 Flash (Online)"
            except Exception as e:
                logger.warning(f"Gemini oracle call failed, falling back: {e}")

        if not report and oai_key:
            try:
                logger.info(f"Invoking OpenAI LLM for filter {canonical_fid}...")
                report = ai_market_oracle.call_openai_oracle(market_context, oai_key)
                if report and "macro_briefing" in report:
                    report["macro_briefing"]["synthesized_by"] = "OpenAI GPT-4o (Online)"
            except Exception as e:
                logger.warning(f"OpenAI oracle call failed, falling back: {e}")

        if not report:
            report = ai_market_oracle.generate_rule_based_briefing(market_context)

        macro = report.get("macro_briefing", {})

        res = {
            "filter_id": filter_id,
            "title": title,
            "headline": macro.get("headline", ""),
            "market_phase": macro.get("market_phase", ""),
            "charter_dynamics": macro.get("charter_dynamics", ""),
            "floor_status": macro.get("floor_status", ""),
            "strategic_directive": macro.get("strategic_directive", ""),
            "buy_now_recommendation": macro.get("buy_now_recommendation", {}),
            "key_anomalies": macro.get("key_anomalies", []),
            "synthesized_by": macro.get("synthesized_by", "Rule-Based Deterministic Engine (Offline)"),
        }
        _ORACLE_CACHE[canonical_fid] = (now_ts, res)
        return res

