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
from datetime import date, datetime
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

    if hist_snapshots and len(hist_snapshots) >= 2:
        for snap in hist_snapshots:
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

        if len(hist_pure_rates) >= 2:
            has_history = True

    # Baseline comparison metrics
    hist_diff_pct: Optional[float] = None

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
    else:
        typical_median_pln = total_price_pln
        hist_min_pln = total_price_pln

    peer_diff_pct: Optional[float] = None
    if peer_star_pure_rates and len(peer_star_pure_rates) >= 3:
        sorted_peers = sorted(peer_star_pure_rates)
        peer_median_pure = sorted_peers[len(sorted_peers) // 2]
        if peer_median_pure > 0:
            peer_diff_pct = ((curr_pure_night - peer_median_pure) / peer_median_pure) * 100.0
            if not has_history:
                typical_median_pln = CostDecomposer.recompose(
                    pure_hotel_night_per_adult=peer_median_pure,
                    duration_nights=nights,
                    adults=adults,
                    children=children,
                    destination=destination,
                )
                hist_min_pln = round(typical_median_pln * 0.85, 2)

    if hist_diff_pct is not None and peer_diff_pct is not None:
        # Blend hotel's own seasonal history (65%) with live market peers of same star level (35%)
        diff_pct = hist_diff_pct * 0.65 + peer_diff_pct * 0.35
    elif hist_diff_pct is not None:
        diff_pct = hist_diff_pct
    elif peer_diff_pct is not None:
        diff_pct = peer_diff_pct
    else:
        diff_pct = 0.0

    # Guard: Clamp diff_pct so extreme anomalies don't distort evaluation
    diff_pct = max(-45.0, min(50.0, diff_pct))

    # 4. Compute Deal Score (0-100)
    # Neutral starting baseline: 65 points (fair market equilibrium)
    score: float = 65.0

    # (A) Historical / Market Price Deviation Impact
    if diff_pct < -25.0:
        score += 24.0  # Exceptional discount (> 25% below norm)
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
        score -= 35.0  # Strongly overpriced (> +30% above norm)

    # (B) Seasonality Context
    # If in peak season / holiday superpeak, getting a normal or discounted price is especially valuable
    if season_info["season"] in ("holiday_superpeak", "peak"):
        if diff_pct <= 5.0:
            score += 6.0  # Holding a stable or low price during high demand is a great deal
    elif season_info["season"] == "low":
        # In low season, cheap prices are standard seasonal reality, NOT a rare anomaly.
        score -= 10.0

    # (C) Departure Timing & Price Drop Probability
    if 0 <= days_to_dep <= 12:
        # Last-minute window: if price is already good, urgency is high
        if diff_pct <= 0.0:
            score += 5.0
    elif days_to_dep > 35:
        # Far in advance: high probability of later promotional price cuts or adjustments
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

    # (E) Quality Guardrails:
    # A hotel with low TripAdvisor rating (< 3.5★) is inherently a budget/poor-quality property.
    # A low price for poor quality is standard equilibrium, NEVER an 80+ Hot Deal or BUY NOW.
    is_budget_tier = False
    if ta < 3.5:
        score = min(62.0, score)
        is_budget_tier = True
    elif ta < 3.8:
        score = min(72.0, score)

    # Final clamping to valid range [25, 98]
    final_score = int(round(max(25.0, min(98.0, score))))

    # 5. Determine Hopper Forecast & Action Verdict
    if is_budget_tier:
        verdict = "WAIT"
        badge = "FAIR_PRICE"
        forecast_reason = (
            f"Бюджетный отель (TripAdvisor {ta:.1f}★). "
            f"Низкий тариф обусловлен скромным уровнем сервиса и комфорта, а не аномальной скидкой."
        )
    elif final_score >= 80:
        verdict = "BUY NOW"
        badge = "SUPER_DEAL" if final_score >= 88 else "GOOD_DEAL"
        if days_to_dep <= 14:
            forecast_reason = f"Выгодная цена (на {abs(round(diff_pct))}% ниже нормы). До вылета {days_to_dep} дн. — места на рейсах заканчиваются, вероятность снижения минимальна."
        elif season_info["season"] in ("holiday_superpeak", "peak"):
            forecast_reason = f"Отличный тариф для периода «{season_info['label']}». {season_info['risk_expl']}. Рекомендуем фиксировать бронь."
        else:
            forecast_reason = f"Цена на {abs(round(diff_pct))}% ниже типичного уровня. Прогноз Hopper: локальное ценовое дно, дальнейшее падение маловероятно."
    elif final_score < 48:
        verdict = "OVERPRICED"
        badge = "OVERPRICED"
        forecast_reason = f"Тариф завышен (+{round(diff_pct):.0f}% к норме). {season_info['label']}. Высокая вероятность коррекции цен или появления спецпредложений ближе к датам."
    else:
        verdict = "WAIT"
        badge = "FAIR_PRICE"
        if days_to_dep > 35:
            forecast_reason = f"Стандартная рыночная цена ({season_info['label']}). До вылета {days_to_dep} дн. — рекомендуем поставить в Watchlist и отслеживать ценовые колебания."
        else:
            forecast_reason = f"Справедливый тариф в пределах сезонной нормы. Резких скачков не прогнозируется, можно следить за динамикой."

    confidence = 0.90 if has_history else (0.80 if peer_star_pure_rates else 0.70)

    return HotelIntelligence(
        deal_score=final_score,
        deal_badge=badge,
        hopper_verdict=verdict,
        hopper_confidence=confidence,
        recommendation=forecast_reason,
        drop_48h_pct=round(diff_pct, 1),
        historic_min_pln=hist_min_pln,
        typical_median_pln=typical_median_pln,
        german_arbitrage_diff_pln=None,
    )
