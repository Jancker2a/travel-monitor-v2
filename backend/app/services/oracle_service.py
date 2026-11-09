import logging
from typing import Dict, Any, Optional
from datetime import datetime, date, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.timeline_service import ALIAS_MAP
from app.services import ai_market_oracle

logger = logging.getLogger("travel_monitor_2.oracle")


class OracleService:
    @classmethod
    async def get_filter_oracle(cls, db: AsyncSession, filter_id: str) -> Dict[str, Any]:
        """
        Synthesizes the AI Market Intelligence Briefing for a filter.
        Computes market phase, flight dynamics, floor breaker statistics,
        and 'If buying now' top recommendations with exact parity to v1.
        """
        canonical_fid = ALIAS_MAP.get(filter_id, filter_id)

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
        offers_sql = """
            SELECT 
                h.hotel_id,
                h.display_name,
                h.ta_rating,
                h.ta_reviews,
                oc.checkin_date,
                oc.duration_nights,
                oc.airport_code,
                oc.offer_url,
                MIN(ps.total_price_pln) as current_price
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.cohort_hash = oc.cohort_hash
            JOIN hotels h ON oc.hotel_id = h.hotel_id
            WHERE ps.filter_id = :fid
              AND ps.recorded_at >= datetime((SELECT MAX(recorded_at) FROM price_snapshots WHERE filter_id = :fid), '-4 hours')
            GROUP BY h.hotel_id
            ORDER BY current_price ASC;
        """
        res = await db.execute(text(offers_sql), {"fid": canonical_fid})
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
        for r in rows:
            c_date_str = r[4]
            if c_date_str:
                try:
                    c_date = (
                        datetime.strptime(c_date_str, "%Y-%m-%d").date()
                        if "-" in str(c_date_str)
                        else today
                    )
                    d_diff = (c_date - today).days
                    if d_diff >= 0:
                        days_list.append(d_diff)
                except Exception:
                    pass

        min_days = min(days_list) if days_list else 30
        max_days = max(days_list) if days_list else 45
        med_days = days_list[len(days_list) // 2] if days_list else 35

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
        hist_min_sql = """
            SELECT oc.hotel_id, MIN(ps.total_price_pln) as hist_min
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.cohort_hash = oc.cohort_hash
            WHERE ps.filter_id = :fid
            GROUP BY oc.hotel_id;
        """
        h_res = await db.execute(text(hist_min_sql), {"fid": canonical_fid})
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

        # Synthesize rule-based brief
        report = ai_market_oracle.generate_rule_based_briefing(market_context)
        macro = report.get("macro_briefing", {})

        return {
            "filter_id": filter_id,
            "title": title,
            "headline": macro.get("headline", ""),
            "market_phase": macro.get("market_phase", ""),
            "charter_dynamics": macro.get("charter_dynamics", ""),
            "floor_status": macro.get("floor_status", ""),
            "strategic_directive": macro.get("strategic_directive", ""),
            "buy_now_recommendation": macro.get("buy_now_recommendation", {}),
            "key_anomalies": macro.get("key_anomalies", []),
        }
