"""
Horizon Arbitrage Service (Early Booking vs Standard vs Last Minute).
Evaluates whether a last-minute flash deal is genuinely advantageous compared to
pre-booking (standard horizon 14-45d) and Early Booking (>60d), and vice versa
evaluates for regular/early booking offers whether the hotel is prone to dumping
or is scarce and prone to selling out.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import date, datetime, timezone, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("travel_monitor_2.horizon_arbitrage")


class HorizonArbitrageService:
    """Computes multi-horizon price comparisons across booking windows."""

    @classmethod
    async def get_hotel_horizon_arbitrage(
        cls,
        db: AsyncSession,
        hotel_id: str,
        adults: int = 2,
        children: int = 1,
        duration_nights: int = 7,
        checkin_date: Optional[date] = None,
        current_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Analyzes historical snapshots for the hotel across four canonical booking horizons:
        - Early Booking (EB): D >= 60 days before departure
        - Standard Window (STD): 14 <= D <= 45 days before departure
        - Short Notice (SHORT): 5 <= D <= 13 days before departure
        - Last Minute Flash (LM): 0 <= D <= 4 days before departure
        """
        clean_hotel_id = hotel_id.strip().lower()
        target_nights = max(1, int(duration_nights or 7))
        target_adults = max(1, int(adults or 2))
        target_children = int(children or 0)

        # SQL Query to pull all snapshots for this hotel with matching or close composition
        # Note: We filter by duration +/- 2 nights and normalize price per night to target_nights
        query = text("""
            SELECT 
                ps.total_price_pln,
                ps.recorded_at,
                oc.checkin_date,
                oc.duration_nights,
                oc.adults,
                oc.children,
                oc.airport_code,
                oc.filter_id,
                oc.offer_url
            FROM price_snapshots ps
            JOIN offer_cohorts oc ON ps.cohort_id = oc.cohort_id
            WHERE oc.hotel_id = :hotel_id
              AND oc.checkin_date IS NOT NULL
              AND oc.adults = :adults
              AND oc.children = :children
              AND oc.duration_nights BETWEEN :min_nights AND :max_nights
            ORDER BY ps.recorded_at DESC
        """)

        res = await db.execute(query, {
            "hotel_id": clean_hotel_id,
            "adults": target_adults,
            "children": target_children,
            "min_nights": max(1, target_nights - 2),
            "max_nights": target_nights + 2,
        })
        raw_rows = res.fetchall()

        # Fallback if no exact pax matches: try 2 adults if 2+1 was requested, or general matches
        if not raw_rows and target_children > 0:
            fallback_query = text("""
                SELECT 
                    ps.total_price_pln,
                    ps.recorded_at,
                    oc.checkin_date,
                    oc.duration_nights,
                    oc.adults,
                    oc.children,
                    oc.airport_code,
                    oc.filter_id,
                    oc.offer_url
                FROM price_snapshots ps
                JOIN offer_cohorts oc ON ps.cohort_id = oc.cohort_id
                WHERE oc.hotel_id = :hotel_id
                  AND oc.checkin_date IS NOT NULL
                  AND oc.duration_nights BETWEEN :min_nights AND :max_nights
                ORDER BY ps.recorded_at DESC
                LIMIT 200
            """)
            res_fb = await db.execute(fallback_query, {
                "hotel_id": clean_hotel_id,
                "min_nights": max(1, target_nights - 2),
                "max_nights": target_nights + 2,
            })
            raw_rows = res_fb.fetchall()

        if not raw_rows:
            return {
                "available": False,
                "hotel_id": clean_hotel_id,
                "message": "Недостаточно исторических данных по горизонтам для данного отеля.",
            }

        # Buckets for horizons
        horizons = {
            "last_minute": [],   # 0..4 days
            "short_notice": [],  # 5..13 days
            "standard": [],      # 14..45 days
            "early_booking": [], # 60+ days
        }

        all_time_min = float("inf")
        latest_price = current_price or 0.0

        for r in raw_rows:
            price = float(r[0])
            rec_dt = r[1]
            if isinstance(rec_dt, str):
                rec_d = datetime.fromisoformat(rec_dt.replace("Z", "+00:00")).date()
            elif isinstance(rec_dt, datetime):
                rec_d = rec_dt.date()
            else:
                rec_d = date.today()

            chk_d = r[2]
            if isinstance(chk_d, str):
                try:
                    chk_d = date.fromisoformat(chk_d)
                except Exception:
                    continue
            elif not isinstance(chk_d, date):
                continue

            row_nights = int(r[3] or target_nights)
            # Normalize price to target duration (e.g. 7 nights)
            norm_price = (price / row_nights) * target_nights

            if norm_price < all_time_min:
                all_time_min = norm_price

            days_to_dep = (chk_d - rec_d).days

            item = {
                "price_pln": norm_price,
                "raw_price_pln": price,
                "days_to_dep": days_to_dep,
                "checkin_date": str(chk_d),
                "recorded_at": str(rec_d),
                "duration_nights": row_nights,
                "airport": str(r[6] or ""),
                "filter_id": str(r[7] or ""),
                "offer_url": str(r[8] or ""),
            }

            if 0 <= days_to_dep <= 4:
                horizons["last_minute"].append(item)
            elif 5 <= days_to_dep <= 13:
                horizons["short_notice"].append(item)
            elif 14 <= days_to_dep <= 45:
                horizons["standard"].append(item)
            elif days_to_dep >= 60:
                horizons["early_booking"].append(item)

        # Compute summary stats per horizon
        def summarize(items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
            if not items:
                return None
            prices = [it["price_pln"] for it in items]
            prices.sort()
            median_p = prices[len(prices) // 2]
            min_p = min(prices)
            avg_p = sum(prices) / len(prices)
            return {
                "count": len(items),
                "min_price_pln": round(min_p, 0),
                "median_price_pln": round(median_p, 0),
                "avg_price_pln": round(avg_p, 0),
                "best_offer": min(items, key=lambda x: x["price_pln"]),
            }

        stats_lm = summarize(horizons["last_minute"])
        stats_short = summarize(horizons["short_notice"])
        stats_std = summarize(horizons["standard"])
        stats_eb = summarize(horizons["early_booking"])

        # Determine current offer perspective: is it Last Minute or Regular/Early Booking?
        is_current_lm = False
        today_date = date.today()
        days_from_now_to_checkin = None
        if checkin_date:
            days_from_now_to_checkin = (checkin_date - today_date).days
            if 0 <= days_from_now_to_checkin <= 4:
                is_current_lm = True

        # Reference price for comparison
        active_lm_price = (current_price if is_current_lm and current_price else (stats_lm["min_price_pln"] if stats_lm else None))
        active_std_price = stats_std["median_price_pln"] if stats_std else (stats_short["median_price_pln"] if stats_short else None)
        active_eb_price = stats_eb["median_price_pln"] if stats_eb else None

        # Build dual-direction verdict
        verdict = {
            "perspective": "LAST_MINUTE" if is_current_lm else "REGULAR_OR_EARLY",
            "type": "NEUTRAL",
            "badge": "Информация",
            "headline": "Стандартная динамика",
            "description": "Цены отеля распределены без выраженных аномалий.",
            "recommendation": "Ориентируйтесь на сезонный бюджет.",
            "savings_vs_standard_pln": None,
            "savings_vs_standard_pct": None,
            "savings_vs_eb_pln": None,
            "savings_vs_eb_pct": None,
        }

        # SCENARIO A: Evaluating a Last-Minute Deal (Is it a genuine dump?)
        if is_current_lm and active_lm_price:
            if active_std_price:
                diff_std = active_std_price - active_lm_price
                pct_std = round((diff_std / active_std_price) * 100, 1)
                verdict["savings_vs_standard_pln"] = round(diff_std, 0)
                verdict["savings_vs_standard_pct"] = pct_std

                if active_eb_price:
                    diff_eb = active_eb_price - active_lm_price
                    pct_eb = round((diff_eb / active_eb_price) * 100, 1)
                    verdict["savings_vs_eb_pln"] = round(diff_eb, 0)
                    verdict["savings_vs_eb_pct"] = pct_eb

                if pct_std >= 15.0:
                    verdict["type"] = "REAL_DUMP"
                    verdict["badge"] = "🔥 Честный сброс цены"
                    verdict["headline"] = f"Тур горит на {abs(pct_std):.0f}% дешевле стандартной цены"
                    eb_str = f" и на {diff_eb:,.0f} zł дешевле раннего бронирования" if active_eb_price and diff_eb > 0 else ""
                    verdict["description"] = (
                        f"Отель зафиксирован по цене {active_lm_price:,.0f} zł. "
                        f"За 2–4 недели до вылета аналогичный тур стоил {active_std_price:,.0f} zł "
                        f"(экономия {diff_std:,.0f} zł){eb_str}. Туроператор сбросил цену для заполнения рейса."
                    ).replace(",", " ")
                    verdict["recommendation"] = "Максимально выгодный момент для бронирования с чемоданом наготове."
                elif abs(pct_std) <= 8.0:
                    verdict["type"] = "FAKE_LAST_MINUTE"
                    verdict["badge"] = "⚖️ Обычная цена без скидки"
                    verdict["headline"] = "Срочный вылет продается по стандартной цене"
                    verdict["description"] = (
                        f"Цена горящего тура ({active_lm_price:,.0f} zł) практически не отличается "
                        f"от спокойного поиска месячной давности ({active_std_price:,.0f} zł). "
                        f"Фактической горящей скидки туроператор не предоставил."
                    ).replace(",", " ")
                    verdict["recommendation"] = "Хватать только если вам критичны эти даты; реального дисконта нет."
                elif pct_std <= -10.0:
                    verdict["type"] = "URGENT_SURCHARGE"
                    verdict["badge"] = "📈 Переплата за срочность"
                    verdict["headline"] = f"Тур на {abs(pct_std):.0f}% дороже, чем стоил заранее"
                    verdict["description"] = (
                        f"Срочный вылет стоит {active_lm_price:,.0f} zł, тогда как заранее его можно было взять "
                        f"за {active_std_price:,.0f} zł (+{abs(diff_std):,.0f} zł наценки). Чартер почти заполнен, "
                        f"остались последние места с повышенным тарифом."
                    ).replace(",", " ")
                    verdict["recommendation"] = "Бронировать не рекомендуется из-за переплаты за срочность."
            else:
                verdict["type"] = "INSUFFICIENT_STD"
                verdict["badge"] = "⚡ Горящий вылет"
                verdict["headline"] = f"Горящая цена: {active_lm_price:,.0f} zł".replace(",", " ")
                verdict["description"] = "Для этого отеля зафиксирован срочный вылет, но нет свежих точек за 2–4 недели."
                verdict["recommendation"] = "Сверяйте с общей планкой направления."

        # SCENARIO B: Evaluating a Regular / Early Booking Offer (Should I wait for Last Minute?)
        else:
            lm_count = len(horizons["last_minute"])
            lm_min = stats_lm["min_price_pln"] if stats_lm else None
            curr_target_price = current_price or active_eb_price or active_std_price or 0.0

            if lm_count == 0:
                verdict["type"] = "NEVER_DROPS"
                verdict["badge"] = "🔒 Отель-дефицит (Не горит)"
                verdict["headline"] = "Отель полностью распродается до вылета"
                verdict["description"] = (
                    "В истории наблюдений отель ни разу не появлялся в блоке горящих вылетов (0–4 дня). "
                    "Все номера и блоки мест на рейсах выкупаются заранее. Ожидание скидок перед вылетом приведет к Sold Out."
                )
                verdict["recommendation"] = "Фиксируйте бронирование заранее: отель не доживает до горящих."
            elif lm_min and curr_target_price > 0 and (curr_target_price - lm_min) / curr_target_price >= 0.20:
                diff_pot = curr_target_price - lm_min
                pct_pot = round((diff_pot / curr_target_price) * 100, 1)
                verdict["type"] = "REGULAR_DUMPER"
                verdict["badge"] = "⚡ Отель-сбросник (Часто горит)"
                verdict["headline"] = f"Перед вылетом сбрасывает до -{pct_pot:.0f}%"
                verdict["description"] = (
                    f"Отель регулярно появляется в горящих турах за 0–4 дня до вылета. "
                    f"Его исторический минимум на горящих составлял {lm_min:,.0f} zł "
                    f"(текущая цена {curr_target_price:,.0f} zł). "
                    f"Зафиксировано появлений на горящих: {lm_count}."
                ).replace(",", " ")
                verdict["recommendation"] = "Если даты вылета гибкие, есть высокий шанс поймать отель дешевле прямо перед рейсом."
            else:
                verdict["type"] = "STABLE_PRICING"
                verdict["badge"] = "⚖️ Стабильная ценовая политика"
                verdict["headline"] = "Разница между ранней и горящей ценой минимальна"
                lm_str = f"Минимум на горящих: {lm_min:,.0f} zł. " if lm_min else ""
                verdict["description"] = (
                    f"Отель держит стабильную ценовую планку в течение всего сезона. "
                    f"{lm_str}Экстремальных сбросов цен перед вылетом не фиксировалось."
                ).replace(",", " ")
                verdict["recommendation"] = "Бронируйте в спокойном режиме, ждать горящих ради 3–5% экономии нет смысла."

        return {
            "available": True,
            "hotel_id": clean_hotel_id,
            "target_nights": target_nights,
            "target_adults": target_adults,
            "target_children": target_children,
            "current_price_pln": current_price,
            "horizons": {
                "early_booking": stats_eb,
                "standard": stats_std,
                "short_notice": stats_short,
                "last_minute": stats_lm,
            },
            "all_time_min_pln": round(all_time_min, 0) if all_time_min != float("inf") else None,
            "verdict": verdict,
        }
