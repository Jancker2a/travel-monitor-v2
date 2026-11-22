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
        related_hotel_ids: Optional[List[str]] = None,
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

        all_hids = list(set([clean_hotel_id] + [h.strip().lower() for h in (related_hotel_ids or []) if h]))
        h_placeholders = ",".join(f":hid_{i}" for i in range(len(all_hids)))
        base_params = {f"hid_{i}": h for i, h in enumerate(all_hids)}

        # SQL Query to pull all snapshots for this hotel and its aliases with matching composition
        # Note: We filter by duration +/- 2 nights and normalize price per night to target_nights
        query_sql = f"""
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
            WHERE oc.hotel_id IN ({h_placeholders})
              AND oc.checkin_date IS NOT NULL
              AND oc.adults = :adults
              AND oc.children = :children
              AND oc.duration_nights BETWEEN :min_nights AND :max_nights
            ORDER BY ps.recorded_at DESC
        """
        q_params = {
            **base_params,
            "adults": target_adults,
            "children": target_children,
            "min_nights": max(1, target_nights - 2),
            "max_nights": target_nights + 2,
        }
        res = await db.execute(text(query_sql), q_params)
        raw_rows = res.fetchall()

        # Fallback if no exact pax matches: try general matches across all aliases
        if not raw_rows and target_children > 0:
            fb_sql = f"""
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
                WHERE oc.hotel_id IN ({h_placeholders})
                  AND oc.checkin_date IS NOT NULL
                  AND oc.duration_nights BETWEEN :min_nights AND :max_nights
                ORDER BY ps.recorded_at DESC
                LIMIT 200
            """
            fb_params = {
                **base_params,
                "min_nights": max(1, target_nights - 2),
                "max_nights": target_nights + 2,
            }
            res_fb = await db.execute(text(fb_sql), fb_params)
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

        # Determine current offer perspective: is it Last Minute or Regular/Early Booking?
        is_current_lm = False
        today_date = date.today()
        days_from_now_to_checkin = None
        if checkin_date:
            days_from_now_to_checkin = (checkin_date - today_date).days
            if 0 <= days_from_now_to_checkin <= 4:
                is_current_lm = True

        # Helper functions for seasonal and date range formatting
        MONTHS_SHORT = {1: "янв", 2: "февр", 3: "мар", 4: "апр", 5: "мая", 6: "июн", 7: "июл", 8: "авг", 9: "сент", 10: "окт", 11: "нояб", 12: "дек"}

        def format_date_range(dates: List[date]) -> str:
            if not dates:
                return ""
            dates = sorted(dates)
            min_d, max_d = dates[0], dates[-1]
            if min_d == max_d:
                return f"{min_d.day} {MONTHS_SHORT[min_d.month]}"
            if min_d.month == max_d.month:
                return f"{min_d.day}–{max_d.day} {MONTHS_SHORT[min_d.month]}"
            return f"{MONTHS_SHORT[min_d.month]} – {MONTHS_SHORT[max_d.month]}"

        def get_season_category(month: int) -> str:
            if month in (6, 7, 8):
                return "summer"
            if month in (9, 10):
                return "autumn_velvet"
            if month in (11, 12, 1, 2):
                return "winter_low"
            return "spring"

        def get_season_name(month: int) -> str:
            if month in (6, 7, 8):
                return "Лето (высокий сезон)"
            if month in (9, 10):
                return "Бархатный сезон"
            if month in (11, 12, 1, 2):
                return "Низкий/зимний сезон"
            return "Весенний сезон"

        # Determine target departure date and its seasonal bracket
        target_dep_date = checkin_date
        if not target_dep_date and horizons["last_minute"]:
            try:
                target_dep_date = date.fromisoformat(horizons["last_minute"][-1]["checkin_date"])
            except Exception:
                pass
        elif not target_dep_date and raw_rows:
            try:
                target_dep_date = date.fromisoformat(str(raw_rows[0][2]))
            except Exception:
                pass

        target_season_cat = get_season_category(target_dep_date.month) if target_dep_date else None
        target_season_label = get_season_name(target_dep_date.month) if target_dep_date else ""

        # Compute summary stats per horizon with explicit departure dates & seasons
        def summarize(items: List[Dict[str, Any]], horizon_key: str = "") -> Optional[Dict[str, Any]]:
            if not items:
                return None
            prices = [it["price_pln"] for it in items]
            prices.sort()
            median_p = prices[len(prices) // 2]
            min_p = min(prices)
            avg_p = sum(prices) / len(prices)

            checkin_dates = []
            for it in items:
                if it.get("checkin_date"):
                    try:
                        checkin_dates.append(date.fromisoformat(str(it["checkin_date"])))
                    except Exception:
                        pass

            # Target date formatting: avoid wide multi-month spans like "июн - нояб" for active view
            if horizon_key == "last_minute" and is_current_lm and checkin_date:
                dates_label = f"{checkin_date.day} {MONTHS_SHORT.get(checkin_date.month, '')}"
                display_p = round(current_price, 0) if current_price else round(median_p, 0)
            elif target_dep_date and checkin_dates:
                near_dates = [d for d in checkin_dates if abs((d - target_dep_date).days) <= 45]
                dates_label = format_date_range(near_dates if near_dates else checkin_dates)
                display_p = round(median_p, 0)
            else:
                dates_label = format_date_range(checkin_dates)
                display_p = round(median_p, 0)

            first_m = checkin_dates[0].month if checkin_dates else (target_dep_date.month if target_dep_date else 11)
            season_label = get_season_name(first_m)

            is_same_season = True
            if target_season_cat and checkin_dates:
                is_same_season = any(get_season_category(d.month) == target_season_cat for d in checkin_dates)

            return {
                "count": len(items),
                "display_price_pln": display_p,
                "current_price_pln": round(current_price, 0) if (is_current_lm and current_price and horizon_key == "last_minute") else None,
                "min_price_pln": round(min_p, 0),
                "median_price_pln": round(median_p, 0),
                "avg_price_pln": round(avg_p, 0),
                "departure_dates_label": dates_label,
                "season_label": season_label,
                "is_same_season": is_same_season,
                "best_offer": min(items, key=lambda x: x["price_pln"]),
            }

        stats_lm = summarize(horizons["last_minute"], horizon_key="last_minute")
        stats_short = summarize(horizons["short_notice"], horizon_key="short_notice")
        stats_std = summarize(horizons["standard"], horizon_key="standard")
        stats_eb = summarize(horizons["early_booking"], horizon_key="early_booking")

        # Reference price for comparison
        active_lm_price = (current_price if is_current_lm and current_price else (stats_lm["display_price_pln"] if stats_lm else None))
        active_std_price = stats_std["median_price_pln"] if stats_std else (stats_short["median_price_pln"] if stats_short else None)
        active_eb_price = stats_eb["median_price_pln"] if stats_eb else None
        active_std_price = stats_std["median_price_pln"] if stats_std else (stats_short["median_price_pln"] if stats_short else None)
        active_eb_price = stats_eb["median_price_pln"] if stats_eb else None

        # Build Direct Comparison between Hot Offer and upcoming Regular Offer
        direct_comparison = None
        comp_std = stats_std or stats_short

        # Select the best upcoming regular offer (D >= 5 days) from short_notice or standard
        # Prefer fresh snapshots (recorded in the last 7 days) to reflect live market options
        fresh_cutoff = (today_date - timedelta(days=7))
        upcoming_pool = [
            it for it in (horizons["short_notice"] + horizons["standard"])
            if it.get("checkin_date") and it.get("recorded_at")
        ]
        fresh_pool = []
        for it in upcoming_pool:
            try:
                rec_d = date.fromisoformat(str(it["recorded_at"]).split()[0])
                if rec_d >= fresh_cutoff:
                    fresh_pool.append(it)
            except Exception:
                pass

        candidates = fresh_pool if fresh_pool else upcoming_pool
        best_std_offer = min(candidates, key=lambda x: x["price_pln"]) if candidates else (comp_std.get("best_offer") if comp_std else None)

        if (is_current_lm or stats_lm) and best_std_offer:
            lm_best = stats_lm.get("best_offer") if stats_lm else None
            lm_price = current_price if (is_current_lm and current_price) else (lm_best["price_pln"] if lm_best else None)
            std_price = best_std_offer["price_pln"]

            if lm_price and std_price:
                price_diff = round(std_price - lm_price, 0)  # positive: hot cheaper; negative: regular cheaper
                diff_pct = round((abs(price_diff) / max(1.0, std_price)) * 100, 1)

                lm_date_str = str(checkin_date) if checkin_date else (lm_best.get("checkin_date") if lm_best else (str(target_dep_date) if target_dep_date else None))
                std_date_str = best_std_offer.get("checkin_date")

                def fmt_iso_date(d_val: Optional[str]) -> str:
                    if not d_val:
                        return ""
                    try:
                        return date.fromisoformat(str(d_val)[:10]).strftime("%d.%m.%Y")
                    except Exception:
                        return str(d_val)

                lm_date_fmt = fmt_iso_date(lm_date_str)
                std_date_fmt = fmt_iso_date(std_date_str)

                days_gap = None
                if lm_date_str and std_date_str:
                    try:
                        d1 = date.fromisoformat(str(lm_date_str)[:10])
                        d2 = date.fromisoformat(str(std_date_str)[:10])
                        days_gap = (d2 - d1).days
                    except Exception:
                        pass

                is_hot_cheaper = price_diff > 50.0
                is_std_cheaper = price_diff < -50.0
                is_same_flight_date = bool(lm_date_fmt and std_date_fmt and lm_date_fmt == std_date_fmt)

                if is_std_cheaper:
                    surcharge = abs(price_diff)
                    if is_same_flight_date:
                        comp_summary = f"На ту же дату ({std_date_fmt}) регулярный рейс на {surcharge:,.0f} zł (-{diff_pct}%) выгоднее срочного тура!"
                    elif days_gap and days_gap > 0:
                        comp_summary = f"Вылет {std_date_fmt} (через {days_gap} дн.) на {surcharge:,.0f} zł (-{diff_pct}%) выгоднее вылета {lm_date_fmt}."
                    else:
                        comp_summary = f"Вылет {std_date_fmt} на {surcharge:,.0f} zł (-{diff_pct}%) выгоднее вылета {lm_date_fmt}."
                elif is_hot_cheaper:
                    if is_same_flight_date:
                        comp_summary = f"Горящий тур на {lm_date_fmt} на {price_diff:,.0f} zł (-{diff_pct}%) дешевле регулярного тарифа."
                    elif days_gap and days_gap > 0:
                        comp_summary = f"Горящий вылет ({lm_date_fmt}) на {price_diff:,.0f} zł (-{diff_pct}%) дешевле вылета {std_date_fmt} (через {days_gap} дн.)."
                    else:
                        comp_summary = f"Горящий вылет ({lm_date_fmt}) на {price_diff:,.0f} zł (-{diff_pct}%) дешевле вылета {std_date_fmt}."
                else:
                    comp_summary = f"Цены горящего ({lm_date_fmt}) и стандартного ({std_date_fmt}) вылетов практически идентичны."

                direct_comparison = {
                    "has_comparison": True,
                    "is_hot_cheaper": is_hot_cheaper,
                    "is_std_cheaper": is_std_cheaper,
                    "is_same_flight_date": is_same_flight_date,
                    "price_diff_pln": price_diff,
                    "diff_pct": diff_pct,
                    "days_gap": days_gap,
                    "hot_offer": {
                        "price_pln": round(lm_price, 0),
                        "checkin_date": lm_date_str,
                        "checkin_date_formatted": lm_date_fmt,
                        "airport": lm_best.get("airport", "") if lm_best else "",
                        "offer_url": lm_best.get("offer_url") if lm_best else None,
                    },
                    "standard_offer": {
                        "price_pln": round(std_price, 0),
                        "checkin_date": std_date_str,
                        "checkin_date_formatted": std_date_fmt,
                        "airport": best_std_offer.get("airport", ""),
                        "offer_url": best_std_offer.get("offer_url") or None,
                    },
                    "early_booking_offer": {
                        "price_pln": round(stats_eb["median_price_pln"], 0),
                        "departure_dates_label": stats_eb.get("departure_dates_label"),
                        "season_label": stats_eb.get("season_label"),
                        "is_same_season": stats_eb.get("is_same_season"),
                    } if stats_eb else None,
                    "summary": comp_summary.replace(",", " "),
                }

        # Detect cross-season comparisons (e.g. Summer Early Booking vs Winter Last Minute)
        is_cross_season_eb = bool(stats_eb and not stats_eb.get("is_same_season"))
        is_cross_season_std = bool(stats_std and not stats_std.get("is_same_season"))
        is_cross_season = is_cross_season_eb or is_cross_season_std

        season_note = None
        if is_cross_season_eb and active_eb_price and stats_eb:
            season_note = (
                f"Внимание: цена раннего бронирования ({active_eb_price:,.0f} zł) указана для летнего высокого сезона ({stats_eb.get('departure_dates_label', 'лето')}), "
                f"где базовые тарифы отеля выше. Прямое сравнение лета с зимой некорректно — честный дисконт рассчитывается относительно стандартного тарифа на те же даты."
            ).replace(",", " ")

        # Build dual-direction verdict with seasonal awareness
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
            "is_cross_season_comparison": is_cross_season,
            "season_note": season_note,
        }

        # SCENARIO A: Evaluating a Last-Minute Deal (Is it a genuine dump?)
        if is_current_lm and active_lm_price:
            lm_date_disp = (
                direct_comparison["hot_offer"]["checkin_date_formatted"]
                if direct_comparison and direct_comparison.get("hot_offer") and direct_comparison["hot_offer"].get("checkin_date_formatted")
                else (checkin_date.strftime("%d.%m.%Y") if checkin_date else "")
            )
            std_date_disp = (
                direct_comparison["standard_offer"]["checkin_date_formatted"]
                if direct_comparison and direct_comparison.get("standard_offer") and direct_comparison["standard_offer"].get("checkin_date_formatted")
                else (comp_std.get("departure_dates_label") or "")
            )

            lm_dates_str = f" на дату {lm_date_disp}" if lm_date_disp else ""
            std_dates_str = f" на вылет {std_date_disp}" if std_date_disp else ""

            if active_std_price:
                diff_std = active_std_price - active_lm_price
                pct_std = round((diff_std / active_std_price) * 100, 1)
                verdict["savings_vs_standard_pln"] = round(diff_std, 0)
                verdict["savings_vs_standard_pct"] = pct_std

                # Only credit Early Booking savings if it is the SAME season!
                diff_eb = None
                pct_eb = None
                if active_eb_price and not is_cross_season_eb:
                    diff_eb = active_eb_price - active_lm_price
                    pct_eb = round((diff_eb / active_eb_price) * 100, 1)
                    verdict["savings_vs_eb_pln"] = round(diff_eb, 0)
                    verdict["savings_vs_eb_pct"] = pct_eb

                # Priority 1: When live direct comparison is available, base verdict STRICTLY on the real live flights
                if direct_comparison:
                    is_std_cheaper = direct_comparison.get("is_std_cheaper", False)
                    is_hot_cheaper = direct_comparison.get("is_hot_cheaper", False)
                    diff_pln = direct_comparison["price_diff_pln"]  # positive: hot cheaper; negative: std cheaper
                    diff_pct = direct_comparison["diff_pct"]
                    std_offer = direct_comparison["standard_offer"]
                    hot_offer = direct_comparison["hot_offer"]
                    days_gap_val = direct_comparison.get("days_gap")
                    days_msg = f"через {days_gap_val} дн. " if (days_gap_val and days_gap_val > 0) else ""

                    std_d = std_offer.get("checkin_date_formatted") or std_offer.get("checkin_date") or ""
                    std_apt = f" ({std_offer['airport']})" if std_offer.get("airport") else ""
                    std_p = std_offer["price_pln"]

                    hot_d = hot_offer.get("checkin_date_formatted") or hot_offer.get("checkin_date") or ""
                    hot_apt = f" ({hot_offer['airport']})" if hot_offer.get("airport") else ""

                    is_same_day = (hot_d == std_d)

                    if is_std_cheaper:
                        diff_abs = abs(diff_pln)
                        verdict["type"] = "URGENT_SURCHARGE"
                        verdict["badge"] = f"📈 Вылет {days_msg}дешевле (-{diff_abs:,.0f} zł)".replace(",", " ") if not is_same_day else f"📈 Регулярный рейс дешевле (-{diff_abs:,.0f} zł)".replace(",", " ")
                        verdict["headline"] = (
                            f"Горящий тур дороже на {diff_abs:,.0f} zł (+{diff_pct:.0f}%), чем регулярный рейс на ту же дату"
                            if is_same_day
                            else f"Горящий тур дороже на {diff_abs:,.0f} zł (+{diff_pct:.0f}%), чем вылет {days_msg}позже"
                        ).replace(",", " ")

                        if is_same_day:
                            verdict["description"] = (
                                f"Срочный вылет на дату {hot_d}{hot_apt} стоит {active_lm_price:,.0f} zł. "
                                f"Однако на эту же дату ({std_d}{std_apt}) в регулярном радаре доступен вылет "
                                f"за {std_p:,.0f} zł (дешевле на {diff_abs:,.0f} zł). "
                                f"Покупать горящий тур не имеет смысла — регулярный рейс на эту же дату дешевле."
                            ).replace(",", " ")
                            verdict["recommendation"] = f"Рекомендуем выбрать регулярный рейс {std_d}{std_apt}: экономия {diff_abs:,.0f} zł без спешки с чемоданом."
                        else:
                            verdict["description"] = (
                                f"Срочный вылет на дату {hot_d}{hot_apt} стоит {active_lm_price:,.0f} zł. "
                                f"Однако на дату {std_d}{std_apt} {days_msg}в регулярном радаре доступен вылет "
                                f"за {std_p:,.0f} zł (дешевле на {diff_abs:,.0f} zł). "
                                f"Покупать горящий тур не имеет смысла — туроператор повысил тариф на последние места срочного чартера."
                            ).replace(",", " ")
                            verdict["recommendation"] = f"Рекомендуем выбрать вылет {std_d}{std_apt}: экономия {diff_abs:,.0f} zł без спешки с чемоданом."

                        verdict["savings_vs_standard_pln"] = -diff_abs
                        verdict["savings_vs_standard_pct"] = -diff_pct

                    elif is_hot_cheaper and diff_pct >= 15.0 and diff_pln >= 800:
                        # Genuine deep flash dump
                        verdict["type"] = "REAL_DUMP"
                        verdict["badge"] = f"🔥 Честный сброс цены (-{diff_pln:,.0f} zł)".replace(",", " ")
                        verdict["headline"] = f"Горящий вылет дешевле регулярного на {diff_pln:,.0f} zł (-{diff_pct:.0f}%)".replace(",", " ")
                        verdict["description"] = (
                            f"Срочный вылет на дату {hot_d}{hot_apt} стоит {active_lm_price:,.0f} zł. "
                            f"Ближайший регулярный вылет {std_d}{std_apt} стоит {std_p:,.0f} zł "
                            f"(чистая экономия от сброса перед рейсом — {diff_pln:,.0f} zł). "
                            f"Туроператор сбросил цену для заполнения рейса."
                        ).replace(",", " ")
                        verdict["recommendation"] = "Максимально выгодный момент для бронирования с чемоданом наготове."
                        verdict["savings_vs_standard_pln"] = diff_pln
                        verdict["savings_vs_standard_pct"] = diff_pct

                    else:
                        # Minor difference (< 15% or < 800 zł)
                        diff_pos = max(0.0, diff_pln)
                        verdict["type"] = "FAKE_LAST_MINUTE"
                        verdict["badge"] = f"⚖️ Обычный тариф (разница {diff_pos:,.0f} zł)".replace(",", " ") if diff_pos > 0 else "⚖️ Обычный тариф"
                        verdict["headline"] = f"Разница со стандартным рейсом незначительна ({diff_pos:,.0f} zł / {diff_pct:.0f}%)".replace(",", " ")
                        verdict["description"] = (
                            f"Срочный вылет на дату {hot_d} ({active_lm_price:,.0f} zł) практически не отличается "
                            f"от регулярного вылета {std_d} ({std_p:,.0f} zł). "
                            f"Фактического глубокого горящего дисконта туроператор не предоставил."
                        ).replace(",", " ")
                        verdict["recommendation"] = "Бронируйте только если дата критична; глубокой горящей скидки нет."
                        verdict["savings_vs_standard_pln"] = diff_pos
                        verdict["savings_vs_standard_pct"] = diff_pct

                elif diff_std < -50.0:
                    diff_abs = abs(diff_std)
                    pct_abs = abs(pct_std)
                    days_gap_val = direct_comparison.get("days_gap") if direct_comparison else None
                    days_msg = f"через {days_gap_val} дн. " if (days_gap_val and days_gap_val > 0) else ""
                    std_apt = f" ({direct_comparison['standard_offer']['airport']})" if (direct_comparison and direct_comparison['standard_offer'].get("airport")) else ""
                    std_d = (
                        direct_comparison['standard_offer']['checkin_date_formatted']
                        if (direct_comparison and direct_comparison.get('standard_offer') and direct_comparison['standard_offer'].get('checkin_date_formatted'))
                        else (std_date_disp or "позже")
                    )

                    verdict["type"] = "URGENT_SURCHARGE"
                    verdict["badge"] = f"📈 Вылет {days_msg}дешевле (-{diff_abs:,.0f} zł)".replace(",", " ")
                    verdict["headline"] = f"Горящий тур дороже на {diff_abs:,.0f} zł (+{pct_abs:.0f}%), чем стандартная цена".replace(",", " ")
                    verdict["description"] = (
                        f"Срочный вылет{lm_dates_str} стоит {active_lm_price:,.0f} zł. "
                        f"Однако в регулярном радаре доступен вылет {std_d}{std_apt} "
                        f"за {active_std_price:,.0f} zł (дешевле на {diff_abs:,.0f} zł). "
                        f"Покупать горящий тур не имеет смысла — туроператор повысил тариф на последние места срочного чартера."
                    ).replace(",", " ")
                    verdict["recommendation"] = f"Рекомендуем выбрать вылет {std_d}{std_apt}: экономия {diff_abs:,.0f} zł без спешки с чемоданом."

                elif pct_std >= 12.0:
                    verdict["type"] = "REAL_DUMP"
                    verdict["badge"] = "🔥 Честный сброс цены"
                    verdict["headline"] = f"Тур горит на {abs(pct_std):.0f}% дешевле стандартной цены"
                    
                    if active_eb_price and not is_cross_season_eb and diff_eb and diff_eb > 0:
                        eb_snippet = f" и на {diff_eb:,.0f} zł дешевле раннего бронирования на эти же даты"
                    elif active_eb_price and is_cross_season_eb:
                        eb_snippet = f" (летнее раннее бронирование составляло {active_eb_price:,.0f} zł в высокий сезон)"
                    else:
                        eb_snippet = ""

                    verdict["description"] = (
                        f"Отель зафиксирован по цене {active_lm_price:,.0f} zł{lm_dates_str}. "
                        f"Стандартная цена сезона{std_dates_str} составляет {active_std_price:,.0f} zł "
                        f"(разница с сезонной планкой — {diff_std:,.0f} zł){eb_snippet}. "
                        f"Туроператор сбросил цену для заполнения рейса."
                    ).replace(",", " ")
                    verdict["recommendation"] = "Максимально выгодный момент для бронирования с чемоданом наготове."

                else:
                    verdict["type"] = "FAKE_LAST_MINUTE"
                    verdict["badge"] = "⚖️ Обычная цена без скидки"
                    verdict["headline"] = "Срочный вылет продается по стандартной цене"
                    verdict["description"] = (
                        f"Цена горящего тура{lm_dates_str} ({active_lm_price:,.0f} zł) практически не отличается "
                        f"от стандартного тарифа{std_dates_str} ({active_std_price:,.0f} zł). "
                        f"Фактической горящей скидки туроператор не предоставил."
                    ).replace(",", " ")
                    verdict["recommendation"] = "Хватать только если вам критичны эти даты; реального дисконта нет."
            else:
                verdict["type"] = "INSUFFICIENT_STD"
                verdict["badge"] = "⚡ Горящий вылет"
                verdict["headline"] = f"Горящая цена: {active_lm_price:,.0f} zł".replace(",", " ")
                verdict["description"] = f"Для отеля зафиксирован срочный вылет{lm_dates_str}, но нет свежих точек за 2–4 недели."
                verdict["recommendation"] = "Сверяйте с общей планкой направления."

        # SCENARIO B: Evaluating a Regular / Early Booking Offer (Should I wait for Last Minute?)
        else:
            lm_count = len(horizons["last_minute"])
            lm_min = stats_lm["min_price_pln"] if stats_lm else None
            curr_target_price = current_price or active_eb_price or active_std_price or 0.0

            # Check if LM points belong to a different season
            is_cross_season_lm = bool(stats_lm and not stats_lm.get("is_same_season"))

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

                if is_cross_season_lm:
                    season_note = (
                        f"Обратите внимание: горящие сбросы ({lm_min:,.0f} zł) зафиксированы в низкий зимний сезон ({stats_lm.get('departure_dates_label', 'зима')}). "
                        f"Для летнего пикового отдыха ({target_season_label}) отель обычно держит высокую планку и редко доживает до вылета."
                    ).replace(",", " ")
                    verdict["season_note"] = season_note
                    verdict["is_cross_season_comparison"] = True

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

        # Build departure price story for the specific departure date window (D +/- 4 days)
        departure_price_story = None
        if target_dep_date:
            window_days = 4
            min_chk = target_dep_date - timedelta(days=window_days)
            max_chk = target_dep_date + timedelta(days=window_days)

            window_items = []
            for r in raw_rows:
                chk_d = r[2]
                if isinstance(chk_d, str):
                    try:
                        chk_d = date.fromisoformat(chk_d[:10])
                    except Exception:
                        continue
                if not isinstance(chk_d, date) or not (min_chk <= chk_d <= max_chk):
                    continue

                rec_dt = r[1]
                if isinstance(rec_dt, str):
                    try:
                        rec_d = datetime.fromisoformat(rec_dt.replace("Z", "+00:00")).date()
                    except Exception:
                        rec_d = date.today()
                elif isinstance(rec_dt, (datetime,)):
                    rec_d = rec_dt.date()
                else:
                    rec_d = date.today()

                row_nights = int(r[3] or target_nights)
                norm_p = (float(r[0]) / row_nights) * target_nights
                days_before = (chk_d - rec_d).days

                window_items.append({
                    "price_pln": round(norm_p, 0),
                    "days_before": days_before,
                    "checkin_date": chk_d,
                    "recorded_date": rec_d,
                    "airport": str(r[6] or ""),
                    "is_exact_date": (chk_d == target_dep_date),
                })

            eb_candidates = [it for it in window_items if it["days_before"] >= 55]
            month_candidates = [it for it in window_items if 20 <= it["days_before"] < 55]
            short_candidates = [it for it in window_items if 5 <= it["days_before"] < 20]
            lm_candidates = [it for it in window_items if 0 <= it["days_before"] <= 4]

            eb_stage = None
            if eb_candidates:
                exact_eb = [it for it in eb_candidates if it["is_exact_date"]]
                eb_stage = min(exact_eb, key=lambda x: x["price_pln"]) if exact_eb else min(eb_candidates, key=lambda x: x["price_pln"])
            elif stats_eb and stats_eb.get("best_offer"):
                eb_bo = stats_eb["best_offer"]
                try:
                    c_d = date.fromisoformat(eb_bo["checkin_date"]) if isinstance(eb_bo.get("checkin_date"), str) else target_dep_date
                except Exception:
                    c_d = target_dep_date
                eb_stage = {
                    "price_pln": round(eb_bo["price_pln"], 0),
                    "days_before": eb_bo.get("days_to_dep", 90),
                    "checkin_date": c_d,
                    "recorded_date": date.today(),
                    "airport": eb_bo.get("airport", ""),
                    "is_exact_date": False,
                    "is_seasonal_fallback": True,
                }

            month_stage = None
            if month_candidates:
                exact_m = [it for it in month_candidates if it["is_exact_date"]]
                month_stage = min(exact_m, key=lambda x: x["price_pln"]) if exact_m else min(month_candidates, key=lambda x: x["price_pln"])

            short_stage = None
            if short_candidates:
                exact_s = [it for it in short_candidates if it["is_exact_date"]]
                short_stage = min(exact_s, key=lambda x: x["price_pln"]) if exact_s else min(short_candidates, key=lambda x: x["price_pln"])

            lm_stage = None
            if is_current_lm and current_price:
                lm_stage = {
                    "price_pln": round(current_price, 0),
                    "days_before": days_from_now_to_checkin if days_from_now_to_checkin is not None else 2,
                    "checkin_date": target_dep_date,
                    "recorded_date": date.today(),
                    "airport": "",
                    "is_exact_date": True,
                }
            elif lm_candidates:
                exact_lm = [it for it in lm_candidates if it["is_exact_date"]]
                lm_stage = min(exact_lm, key=lambda x: x["price_pln"]) if exact_lm else min(lm_candidates, key=lambda x: x["price_pln"])

            available_stages = [s for s in [eb_stage, month_stage, short_stage, lm_stage] if s is not None]
            if len(available_stages) >= 2 and lm_stage:
                def _fmt_p(val: float) -> str:
                    return f"{int(round(val)):_}".replace("_", " ")

                story_parts = []
                if eb_stage:
                    eb_date_fmt = eb_stage["checkin_date"].strftime("%d.%m.%Y")
                    p_str = _fmt_p(eb_stage['price_pln'])
                    if eb_stage.get("is_seasonal_fallback"):
                        story_parts.append(f"Раннее бронирование на сезон стоило {p_str} zł")
                    else:
                        story_parts.append(f"Раннее бронирование на {eb_date_fmt} стоило {p_str} zł")

                if month_stage:
                    m_date_fmt = month_stage["checkin_date"].strftime("%d.%m.%Y")
                    m_days = month_stage["days_before"]
                    p_str = _fmt_p(month_stage['price_pln'])
                    if eb_stage:
                        story_parts.append(f"за {m_days} дн. до поездки (на вылет {m_date_fmt}) тур можно было купить за {p_str} zł")
                    else:
                        story_parts.append(f"За {m_days} дн. до поездки на дату {m_date_fmt} тур стоил {p_str} zł")

                if short_stage and (not month_stage or abs(short_stage["price_pln"] - month_stage["price_pln"]) > 100):
                    s_date_fmt = short_stage["checkin_date"].strftime("%d.%m.%Y")
                    s_days = short_stage["days_before"]
                    p_str = _fmt_p(short_stage['price_pln'])
                    story_parts.append(f"за {s_days} дн. до старта (вылет {s_date_fmt}) цена составляла {p_str} zł")

                lm_date_fmt = lm_stage["checkin_date"].strftime("%d.%m.%Y")
                lm_days = lm_stage["days_before"]
                lm_p_str = _fmt_p(lm_stage['price_pln'])
                story_parts.append(f"горящий тур за {lm_days} дн. до вылета (на дату {lm_date_fmt}) продается за {lm_p_str} zł")

                pre_prices = [s["price_pln"] for s in [eb_stage, month_stage, short_stage] if s is not None]
                min_pre = min(pre_prices) if pre_prices else lm_stage["price_pln"]
                diff_to_min_pre = lm_stage["price_pln"] - min_pre
                pct_to_min_pre = round((diff_to_min_pre / max(1.0, min_pre)) * 100, 1)

                if diff_to_min_pre <= -200 and pct_to_min_pre <= -8.0:
                    trajectory = "DEEP_DROP"
                    badge = "🔥 Предложение очень выгодное"
                    conclusion = f"— предложение очень выгодное (экономия {_fmt_p(abs(diff_to_min_pre))} zł к предварительной цене)."
                elif diff_to_min_pre >= 200 or pct_to_min_pre >= 5.0:
                    trajectory = "SURCHARGE_RISE"
                    badge = "⚠️ Предложение не выгодное"
                    conclusion = f"— предложение не выгодное: переплата {_fmt_p(diff_to_min_pre)} zł (+{pct_to_min_pre:.0f}%) из-за наценки на последние места перед вылетом."
                else:
                    trajectory = "STABLE"
                    badge = "⚖️ Стандартная цена"
                    conclusion = "— цена находится на стандартном уровне без выраженного дисконта."

                verdict_text = ", ".join(story_parts) + " " + conclusion

                # Construct chronological timeline steps for clean visual cards
                timeline_steps = []
                prev_price = None

                if eb_stage:
                    p = eb_stage["price_pln"]
                    timeline_steps.append({
                        "key": "early_booking",
                        "title": "🏷️ Раннее",
                        "days_label": f"За {eb_stage['days_before']} дн.",
                        "checkin_date": eb_stage["checkin_date"].strftime("%d.%m.%Y"),
                        "price_pln": p,
                        "delta_prev_pln": None,
                        "delta_prev_pct": None,
                        "is_current": False,
                    })
                    prev_price = p

                if month_stage:
                    p = month_stage["price_pln"]
                    d_pln = round(p - prev_price, 0) if prev_price is not None else None
                    d_pct = round((d_pln / prev_price) * 100, 1) if (prev_price and d_pln is not None) else None
                    timeline_steps.append({
                        "key": "month_before",
                        "title": "📅 За 3–4 нед.",
                        "days_label": f"За {month_stage['days_before']} дн.",
                        "checkin_date": month_stage["checkin_date"].strftime("%d.%m.%Y"),
                        "price_pln": p,
                        "delta_prev_pln": d_pln,
                        "delta_prev_pct": d_pct,
                        "is_current": False,
                    })
                    prev_price = p

                if short_stage and (not month_stage or abs(short_stage["price_pln"] - month_stage["price_pln"]) > 50):
                    p = short_stage["price_pln"]
                    d_pln = round(p - prev_price, 0) if prev_price is not None else None
                    d_pct = round((d_pln / prev_price) * 100, 1) if (prev_price and d_pln is not None) else None
                    timeline_steps.append({
                        "key": "two_weeks_before",
                        "title": "⏳ За 1–2 нед.",
                        "days_label": f"За {short_stage['days_before']} дн.",
                        "checkin_date": short_stage["checkin_date"].strftime("%d.%m.%Y"),
                        "price_pln": p,
                        "delta_prev_pln": d_pln,
                        "delta_prev_pct": d_pct,
                        "is_current": False,
                    })
                    prev_price = p

                p_lm = lm_stage["price_pln"]
                d_lm_pln = round(p_lm - prev_price, 0) if prev_price is not None else None
                d_lm_pct = round((d_lm_pln / prev_price) * 100, 1) if (prev_price and d_lm_pln is not None) else None
                timeline_steps.append({
                    "key": "last_minute",
                    "title": "⚡ Горящий (сейчас)",
                    "days_label": f"За {lm_stage['days_before']} дн.",
                    "checkin_date": lm_stage["checkin_date"].strftime("%d.%m.%Y"),
                    "price_pln": p_lm,
                    "delta_prev_pln": d_lm_pln,
                    "delta_prev_pct": d_lm_pct,
                    "is_current": True,
                })

                clean_conclusion = conclusion.lstrip("— ").strip()

                departure_price_story = {
                    "has_story": True,
                    "target_checkin_date": target_dep_date.strftime("%Y-%m-%d"),
                    "date_window_label": f"вылеты {min_chk.strftime('%d.%m')} – {max_chk.strftime('%d.%m')}",
                    "trajectory": trajectory,
                    "trajectory_badge": badge,
                    "stages": {
                        "early_booking": {
                            "price_pln": eb_stage["price_pln"],
                            "checkin_date": eb_stage["checkin_date"].strftime("%d.%m.%Y"),
                            "days_before": eb_stage["days_before"],
                            "is_exact_date_match": eb_stage.get("is_exact_date", False),
                        } if eb_stage else None,
                        "month_before": {
                            "price_pln": month_stage["price_pln"],
                            "checkin_date": month_stage["checkin_date"].strftime("%d.%m.%Y"),
                            "days_before": month_stage["days_before"],
                            "is_exact_date_match": month_stage.get("is_exact_date", False),
                        } if month_stage else None,
                        "two_weeks_before": {
                            "price_pln": short_stage["price_pln"],
                            "checkin_date": short_stage["checkin_date"].strftime("%d.%m.%Y"),
                            "days_before": short_stage["days_before"],
                            "is_exact_date_match": short_stage.get("is_exact_date", False),
                        } if short_stage else None,
                        "last_minute": {
                            "price_pln": lm_stage["price_pln"],
                            "checkin_date": lm_stage["checkin_date"].strftime("%d.%m.%Y"),
                            "days_before": lm_stage["days_before"],
                            "is_exact_date_match": lm_stage.get("is_exact_date", True),
                        },
                    },
                    "timeline_steps": timeline_steps,
                    "conclusion": clean_conclusion,
                    "verdict_text": verdict_text,
                }

        # Build Historical Best Dump (Рекордный горящий сброс за всю историю наблюдений)
        historical_best_dump = None
        if stats_lm and stats_lm.get("best_offer"):
            best_dump = stats_lm["best_offer"]
            dump_price = round(best_dump["price_pln"], 0)
            dump_chk_str = str(best_dump.get("checkin_date", ""))
            dump_rec_str = str(best_dump.get("recorded_at", ""))
            dump_apt = str(best_dump.get("airport", ""))
            dump_days = int(best_dump.get("days_to_dep", 2))

            try:
                dump_chk_fmt = date.fromisoformat(dump_chk_str[:10]).strftime("%d.%m.%Y")
            except Exception:
                dump_chk_fmt = dump_chk_str
            try:
                dump_rec_fmt = date.fromisoformat(dump_rec_str[:10]).strftime("%d.%m.%Y")
            except Exception:
                dump_rec_fmt = dump_rec_str

            dump_month = None
            try:
                dump_month = date.fromisoformat(dump_chk_str[:10]).month
            except Exception:
                pass

            matching_period_prices = []
            for it in (horizons["standard"] + horizons["short_notice"] + horizons["early_booking"]):
                if it.get("checkin_date"):
                    try:
                        im = date.fromisoformat(str(it["checkin_date"])[:10]).month
                        if dump_month and im == dump_month:
                            matching_period_prices.append(it["price_pln"])
                    except Exception:
                        pass
            if matching_period_prices:
                matching_period_prices.sort()
                norm_bench = matching_period_prices[len(matching_period_prices) // 2]
                month_names = {
                    1: "январе", 2: "феврале", 3: "марте", 4: "апреле",
                    5: "мае", 6: "июне", 7: "июле", 8: "августе",
                    9: "сентябре", 10: "октябре", 11: "ноябре", 12: "декабре"
                }
                m_name = month_names.get(dump_month, "этот сезон")
                norm_label = f"в {m_name}"
            else:
                norm_bench = active_std_price or (stats_eb["median_price_pln"] if stats_eb else dump_price * 1.3)
                norm_label = "по сезону"

            norm_bench = round(norm_bench, 0)
            dump_savings = max(0.0, round(norm_bench - dump_price, 0))
            dump_discount_pct = round((dump_savings / max(1.0, norm_bench)) * 100, 1)

            is_record_now = bool(current_price and current_price <= dump_price + 50.0)

            p_dump_fmt = f"{int(dump_price):_}".replace("_", " ")
            p_norm_fmt = f"{int(norm_bench):_}".replace("_", " ")
            p_sav_fmt = f"{int(dump_savings):_}".replace("_", " ")

            if dump_savings >= 300 and dump_discount_pct >= 8.0:
                narrative = (
                    f"Этот отель можно было купить за {p_dump_fmt} zł в замере {dump_rec_fmt} "
                    f"на дату вылета {dump_chk_fmt} (за {dump_days} дн. до рейса) "
                    f"при средней цене {norm_label} {p_norm_fmt} zł "
                    f"(чистая скидка -{dump_discount_pct:.0f}% / экономия {p_sav_fmt} zł)."
                )
            else:
                narrative = (
                    f"Исторический минимум отеля на горящих вылетах (0–4 дня) составлял {p_dump_fmt} zł "
                    f"(замер {dump_rec_fmt} на дату вылета {dump_chk_fmt})."
                )

            historical_best_dump = {
                "has_dump": True,
                "price_pln": dump_price,
                "checkin_date": dump_chk_str,
                "checkin_date_formatted": dump_chk_fmt,
                "recorded_at": dump_rec_str,
                "recorded_at_formatted": dump_rec_fmt,
                "days_before": dump_days,
                "airport": dump_apt,
                "benchmark_norm_pln": norm_bench,
                "savings_pln": dump_savings,
                "discount_pct": dump_discount_pct,
                "is_record_now": is_record_now,
                "narrative": narrative,
            }

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
            "direct_comparison": direct_comparison,
            "departure_price_story": departure_price_story,
            "historical_best_dump": historical_best_dump,
            "all_time_min_pln": round(all_time_min, 0) if all_time_min != float("inf") else None,
            "verdict": verdict,
        }
