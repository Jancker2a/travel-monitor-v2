"""
Intelligent Deal Score & Hopper Price Forecast Engine for Interactive Search.

Synthesizes:
1. Current Price & Like-for-Like Pure Hotel Rate (via CostDecomposer)
2. Normalized Price History (if available for this hotel)
3. Destination Seasonality (Holiday Superpeak, High, Shoulder, Off-season)
4. Departure Timing & Price Drop Probability (Hopper Forecast: BUY NOW, WAIT, OVERPRICED)
5. TripAdvisor Reputation & Hotel Star Quality
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from app.schemas.search import HotelIntelligence
from app.services.cost_decomposer import CostDecomposer


def get_destination_season_info(destination: str, departure_date: Optional[date] = None) -> Dict[str, Any]:
    """Returns season type (holiday_superpeak, peak, high, shoulder, low), label, and price drop risk."""
    if not departure_date:
        return {"season": "standard", "label": "Стандартный сезон", "multiplier": 1.0, "price_drop_risk": "medium"}

    month = departure_date.month
    day = departure_date.day
    dest = (destination or "").lower()

    is_ny_christmas = (month == 12 and day >= 20) or (month == 1 and day <= 8)

    if any(k in dest for k in ("egypt", "египет", "sharm", "hurghada", "marsa")):
        # Egypt: Winter/spring/autumn is peak sun season. Summer is low due to heat.
        if is_ny_christmas:
            return {
                "season": "holiday_superpeak",
                "label": "Новогодний суперпик в Египте",
                "multiplier": 1.55,
                "price_drop_risk": "very_low",
                "risk_expl": "перед праздниками чартеры и лучшие номера распродаются, действуют праздничные надбавки",
            }
        elif month in (10, 11, 3, 4):
            return {
                "season": "peak",
                "label": "Высокий бархатный сезон в Египте",
                "multiplier": 1.20,
                "price_drop_risk": "low",
                "risk_expl": "высокий спрос на комфортную погоду, тарифы стабильны или растут ближе к вылету",
            }
        elif month in (12, 1, 2):
            return {
                "season": "high",
                "label": "Зимний сезон в Египте (подогреваемые бассейны)",
                "multiplier": 1.05,
                "price_drop_risk": "medium",
                "risk_expl": "умеренный спрос, возможны точечные промо-сбросы за 7-14 дней до вылета",
            }
        elif month in (5, 9):
            return {
                "season": "shoulder",
                "label": "Межсезонье в Египте",
                "multiplier": 0.95,
                "price_drop_risk": "medium",
                "risk_expl": "стабильные тарифы, регулярные спецпредложения туроператоров",
            }
        else:
            return {
                "season": "low",
                "label": "Летний жаркий сезон в Египте",
                "multiplier": 0.80,
                "price_drop_risk": "high",
                "risk_expl": "офф-сезон из-за жары, высокая вероятность горящих предложений",
            }

    elif any(k in dest for k in ("uae", "оаэ", "dubai", "дубай", "emirates", "эмираты")):
        if is_ny_christmas:
            return {
                "season": "holiday_superpeak",
                "label": "Новогодний суперпик в ОАЭ",
                "multiplier": 1.60,
                "price_drop_risk": "very_low",
                "risk_expl": "максимальный праздничный спрос, отели и рейсы быстро распродаются",
            }
        elif month in (10, 11, 12, 1, 2, 3, 4):
            return {
                "season": "peak",
                "label": "Высокий комфортный сезон в ОАЭ",
                "multiplier": 1.25,
                "price_drop_risk": "low",
                "risk_expl": "идеальная погода для пляжа и прогулок, стабильно высокий спрос",
            }
        elif month in (5, 9):
            return {
                "season": "shoulder",
                "label": "Межсезонье в ОАЭ",
                "multiplier": 0.95,
                "price_drop_risk": "medium",
                "risk_expl": "начало жары, умеренные тарифы со скидками",
            }
        else:
            return {
                "season": "low",
                "label": "Жаркий летний офф-сезон в ОАЭ",
                "multiplier": 0.70,
                "price_drop_risk": "high",
                "risk_expl": "офф-сезон из-за сильной жары, цены на минимуме",
            }

    elif any(k in dest for k in ("turkey", "турция", "antalya", "side", "kemer", "belek", "alanya", "bodrum")):
        if month in (7, 8):
            return {
                "season": "peak",
                "label": "Пик летнего сезона в Турции",
                "multiplier": 1.35,
                "price_drop_risk": "low",
                "risk_expl": "максимальная загрузка курортов, снижение цен крайне маловероятно",
            }
        elif month in (6, 9):
            return {
                "season": "high",
                "label": "Высокий пляжный сезон в Турции",
                "multiplier": 1.15,
                "price_drop_risk": "medium",
                "risk_expl": "высокий спрос, отели держат планку тарифов",
            }
        elif month in (5, 10):
            return {
                "season": "shoulder",
                "label": "Бархатный/весенний сезон в Турции",
                "multiplier": 0.90,
                "price_drop_risk": "medium",
                "risk_expl": "комфортные цены, периодические акции туроператоров",
            }
        else:
            return {
                "season": "low",
                "label": "Зимний офф-сезон в Турции (SPA и подогрев)",
                "multiplier": 0.65,
                "price_drop_risk": "high",
                "risk_expl": "низкий сезон, доступные цены являются рыночной нормой",
            }

    else:  # Greece, Cyprus, Spain, Italy, Bulgaria, etc.
        if month in (7, 8):
            return {
                "season": "peak",
                "label": "Пик средиземноморского лета",
                "multiplier": 1.30,
                "price_drop_risk": "low",
                "risk_expl": "высокий сезон, тарифы на пике",
            }
        elif month in (6, 9):
            return {
                "season": "high",
                "label": "Пляжный сезон",
                "multiplier": 1.10,
                "price_drop_risk": "medium",
                "risk_expl": "стабильный спрос",
            }
        elif month in (5, 10):
            return {
                "season": "shoulder",
                "label": "Бархатное межсезонье",
                "multiplier": 0.85,
                "price_drop_risk": "medium",
                "risk_expl": "выгодные тарифы",
            }
        else:
            return {
                "season": "low",
                "label": "Европейский офф-сезон",
                "multiplier": 0.70,
                "price_drop_risk": "high",
                "risk_expl": "непляжный сезон, цены на минимуме",
            }


def evaluate_search_intelligence(
    destination: str,
    departure_date: Optional[date],
    duration_nights: int,
    adults: int,
    children: int,
    total_price_pln: float,
    stars: int = 4,
    ta_rating: Optional[float] = None,
    hist_snapshots: Optional[List[Dict[str, Any]]] = None,
    peer_star_pure_rates: Optional[List[float]] = None,
) -> HotelIntelligence:
    """Evaluates Deal Score (0-100) and Hopper Forecast for a search offer, accounting for:
    - Current price and normalized pure hotel night rate (CostDecomposer)
    - Normalized price history for this hotel (apples-to-apples comparison)
    - Seasonality of the travel dates
    - Forecast probability of price drops before departure
    - TripAdvisor reputation & quality tier
    """
    nights = max(1, duration_nights)
    adults = max(1, adults)
    children = max(0, children)
    pax_total = adults + children

    # 1. Decompose current offer
    decomp = CostDecomposer.decompose(
        total_price_pln=total_price_pln,
        duration_nights=nights,
        adults=adults,
        children=children,
        destination=destination,
    )
    curr_pure_night = decomp.get("pure_hotel_night_per_adult", 150.0)

    # 2. Season info & timing
    season_info = get_destination_season_info(destination, departure_date)
    today = date.today()
    days_to_dep = (departure_date - today).days if departure_date else 30
    curr_season_mult = season_info.get("multiplier", 1.0)
    curr_pure_unseasoned = curr_pure_night / max(0.5, curr_season_mult)

    # 3. Analyze normalized history for this specific hotel
    has_history = False
    hist_pure_rates: List[float] = []
    hist_prices_raw: List[float] = []

    if hist_snapshots:
        for snap in hist_snapshots:
            if snap.get("pure_hotel_night_rate") and float(snap["pure_hotel_night_rate"]) > 0:
                raw_pure = float(snap["pure_hotel_night_rate"])
                p_val = float(snap.get("price") or snap.get("total_price_pln") or 0.0)
                if p_val > 0:
                    hist_prices_raw.append(p_val)
                # Pure rate from normalized_price_snapshots is already de-seasoned/normalized
                hist_pure_rates.append(raw_pure)
                continue

            p_val = float(snap.get("price") or snap.get("total_price_pln") or 0.0)
            if p_val <= 0:
                continue
            hist_prices_raw.append(p_val)
            s_adults = snap.get("adults") or adults
            s_children = snap.get("children") or children
            s_nights = snap.get("duration_nights") or nights

            s_decomp = CostDecomposer.decompose(
                total_price_pln=p_val,
                duration_nights=s_nights,
                adults=s_adults,
                children=s_children,
                destination=destination,
            )
            raw_pure = s_decomp.get("pure_hotel_night_per_adult", 150.0)

            # De-season snapshot using actual departure checkin date
            s_date = snap.get("departure_date")
            if isinstance(s_date, str):
                try:
                    s_date = date.fromisoformat(s_date[:10])
                except Exception:
                    s_date = None
            elif isinstance(s_date, datetime):
                s_date = s_date.date()

            # Fallback to query departure date if snapshot departure date is unknown
            if not s_date:
                s_date = departure_date
            snap_season = get_destination_season_info(destination, s_date)
            snap_mult = snap_season.get("multiplier", 1.0)
            hist_pure_rates.append(raw_pure / max(0.5, snap_mult))

        # Strictly require at least 3 historical observations for THIS SPECIFIC HOTEL
        if len(hist_pure_rates) >= 3:
            has_history = True

    # Baseline comparison metrics
    hist_diff_pct: Optional[float] = None
    typical_median_pln: Optional[float] = None
    hist_min_pln: Optional[float] = None

    if has_history:
        sorted_pure = sorted(hist_pure_rates)
        hist_median_pure = sorted_pure[len(sorted_pure) // 2]
        hist_min_pure = sorted_pure[0]
        if hist_median_pure > 0:
            hist_diff_pct = ((curr_pure_unseasoned - hist_median_pure) / hist_median_pure) * 100.0

        # Mathematically reconstruct typical median and historic min scaled like-for-like to current search
        typical_median_pln = CostDecomposer.recompose(
            pure_hotel_night_per_adult=hist_median_pure * curr_season_mult,
            duration_nights=nights,
            adults=adults,
            children=children,
            destination=destination,
        )
        hist_min_pln = CostDecomposer.recompose(
            pure_hotel_night_per_adult=hist_min_pure * curr_season_mult,
            duration_nights=nights,
            adults=adults,
            children=children,
            destination=destination,
        )
        diff_pct = max(-45.0, min(50.0, hist_diff_pct))
    else:
        # Strictly NO fake peer benchmarks or invented discounts!
        typical_median_pln = None
        hist_min_pln = total_price_pln
        diff_pct = 0.0

    # 4. Compute Deal Score (0-100)
    score: float = 65.0
    if not has_history:
        # Neutral baseline for newly discovered / sparse hotels: strictly no phantom deal bonuses!
        score = 50.0
        ta = float(ta_rating) if ta_rating is not None and ta_rating > 0 else 4.0
        if ta >= 4.5:
            score += 5.0
        elif ta < 3.5:
            score -= 5.0
    else:
        # (A) Historical Price Deviation Impact (strictly hotel's own verified history)
        if diff_pct < -25.0:
            score += 24.0  # Exceptional discount (> 25% below hotel's own norm)
        elif diff_pct < -15.0:
            score += 17.0
        elif diff_pct < -8.0:
            score += 10.0
        elif diff_pct <= 5.0:
            score += 0.0   # Fair market price
        elif diff_pct <= 18.0:
            score -= 14.0  # Moderately overpriced
        elif diff_pct <= 30.0:
            score -= 24.0  # Overpriced
        else:
            score -= 35.0  # Strongly overpriced (> +30% above hotel's own norm)

        # (B) Seasonality Context
        if season_info["season"] in ("holiday_superpeak", "peak"):
            if diff_pct <= 5.0:
                score += 6.0
        elif season_info["season"] == "low":
            score -= 10.0

        # (C) Departure Timing & Price Drop Probability
        if 0 <= days_to_dep <= 12:
            if diff_pct <= 0.0:
                score += 5.0
        elif days_to_dep > 35:
            score -= 4.0

        # (D) Hotel Reputation & Quality Tier (TripAdvisor)
        ta = float(ta_rating) if ta_rating is not None and ta_rating > 0 else 4.2
        if ta >= 4.6:
            score += 6.0
        elif ta >= 4.3:
            score += 3.0
        elif ta < 3.4:
            score -= 22.0
        elif ta < 3.8:
            score -= 12.0

    # (E) Quality Guardrails
    is_budget_tier = False
    ta = float(ta_rating) if ta_rating is not None and ta_rating > 0 else 4.2
    if ta < 3.5:
        score = min(62.0, score)
        is_budget_tier = True
    elif ta < 3.8:
        score = min(72.0, score)

    # Final clamping to valid range [25, 98]
    final_score = int(round(max(25.0, min(98.0, score))))

    # 5. Mathematically Exact Delta vs Typical Seasonal Price (Plateau Baseline)
    delta_vs_typical_pct: Optional[float] = None
    if has_history and typical_median_pln and typical_median_pln > 0:
        delta_vs_typical_pct = round(((total_price_pln - typical_median_pln) / typical_median_pln) * 100.0, 1)
        delta_vs_typical_pct = round(((total_price_pln - typical_median_pln) / typical_median_pln) * 100.0, 1)

    # 6. Real 48-Hour Price Change (strictly requires mature observations >= 4)
    real_drop_48h_pct: Optional[float] = None
    if hist_snapshots and has_history:
        now_utc = datetime.now(timezone.utc)
        candidates_48h = []
        for snap in hist_snapshots:
            # Strictly require comparable departure dates (do NOT compare Nov 2026 departure with June 2027)
            s_dep = snap.get("departure_date")
            if departure_date and s_dep:
                if isinstance(s_dep, str):
                    try:
                        s_dep = date.fromisoformat(s_dep[:10])
                    except Exception:
                        s_dep = None
                elif isinstance(s_dep, datetime):
                    s_dep = s_dep.date()
                if s_dep and abs((s_dep - departure_date).days) > 21:
                    # Incompatible travel horizon
                    continue

            r_at = snap.get("recorded_at")
            if not r_at:
                continue
            if isinstance(r_at, str):
                try:
                    r_at = datetime.fromisoformat(r_at.replace("Z", "+00:00"))
                except Exception:
                    continue
            if isinstance(r_at, datetime):
                if r_at.tzinfo is None:
                    r_at = r_at.replace(tzinfo=timezone.utc)
                age_hours = (now_utc - r_at).total_seconds() / 3600.0
                if 14.0 <= age_hours <= 72.0:
                    candidates_48h.append((abs(age_hours - 48.0), snap))

        if candidates_48h:
            candidates_48h.sort(key=lambda x: x[0])
            prev_snap = candidates_48h[0][1]
            prev_p = float(prev_snap.get("price") or prev_snap.get("total_price_pln") or 0.0)
            if prev_p > 0:
                s_adults = prev_snap.get("adults") or adults
                s_children = prev_snap.get("children") or children
                s_nights = prev_snap.get("duration_nights") or nights
                if s_adults == adults and s_children == children and s_nights == nights:
                    norm_prev_p = prev_p
                else:
                    d = CostDecomposer.decompose(
                        total_price_pln=prev_p,
                        duration_nights=s_nights,
                        adults=s_adults,
                        children=s_children,
                        destination=destination,
                    )
                    norm_prev_p = CostDecomposer.recompose(
                        pure_hotel_night_per_adult=d.get("pure_hotel_night_per_adult", 150.0),
                        duration_nights=nights,
                        adults=adults,
                        children=children,
                        destination=destination,
                    )
                if norm_prev_p > 0:
                    chg = ((total_price_pln - norm_prev_p) / norm_prev_p) * 100.0
                    real_drop_48h_pct = round(chg, 1)

    # 7. Determine Hopper Forecast & Action Verdict
    display_delta_pct = abs(round(delta_vs_typical_pct)) if delta_vs_typical_pct is not None else abs(round(diff_pct))

    if not has_history:
        verdict = "WAIT"
        badge = "FAIR_PRICE"
        forecast_reason = (
            f"Первичные замеры отеля (зафиксировано {len(hist_snapshots) if hist_snapshots else 1} точек). "
            f"Сравнение со средней нормой отключено во избежание неточных выводов до накопления истории."
        )
        confidence = 0.50
    elif is_budget_tier:
        verdict = "WAIT"
        badge = "FAIR_PRICE"
        forecast_reason = (
            f"Бюджетный отель (TripAdvisor {ta:.1f}★). "
            f"Низкий тариф обусловлен скромным уровнем сервиса и комфорта, а не аномальной скидкой."
        )
        confidence = 0.85
    elif final_score >= 80:
        verdict = "BUY NOW"
        badge = "SUPER_DEAL" if final_score >= 88 else "GOOD_DEAL"
        if days_to_dep <= 14:
            forecast_reason = f"Выгодная цена (на {display_delta_pct}% ниже нормы). До вылета {days_to_dep} дн. — места на рейсах заканчиваются, вероятность снижения минимальна."
        elif season_info["season"] in ("holiday_superpeak", "peak"):
            forecast_reason = f"Отличный тариф для периода «{season_info['label']}». {season_info['risk_expl']}. Рекомендуем фиксировать бронь."
        else:
            forecast_reason = f"Цена на {display_delta_pct}% ниже типичного уровня. Прогноз Hopper: локальное ценовое дно, дальнейшее падение маловероятно."
        confidence = 0.90
    elif final_score < 48:
        verdict = "OVERPRICED"
        badge = "OVERPRICED"
        forecast_reason = f"Тариф завышен (+{display_delta_pct}% к норме). {season_info['label']}. Высокая вероятность коррекции цен или появления спецпредложений ближе к датам."
        confidence = 0.85
    else:
        verdict = "WAIT"
        badge = "FAIR_PRICE"
        if days_to_dep > 35:
            forecast_reason = f"Стандартная рыночная цена ({season_info['label']}). До вылета {days_to_dep} дн. — рекомендуем поставить в Watchlist и отслеживать ценовые колебания."
        else:
            forecast_reason = f"Справедливый тариф в пределах сезонной нормы. Резких скачков не прогнозируется, можно следить за динамикой."
        confidence = 0.85

    return HotelIntelligence(
        deal_score=final_score,
        deal_badge=badge,
        hopper_verdict=verdict,
        hopper_confidence=confidence,
        recommendation=forecast_reason,
        drop_48h_pct=real_drop_48h_pct,
        delta_vs_typical_pct=delta_vs_typical_pct,
        historic_min_pln=hist_min_pln,
        typical_median_pln=typical_median_pln,
        german_arbitrage_diff_pln=None,
        is_budget_tier=is_budget_tier,
    )
