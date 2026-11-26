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
from app.services.canonical_filters import classify_filter_type
from app.services.cost_decomposer import CostDecomposer
from app.services.hotel_deal_score import compute_unified_deal_assessment


def get_destination_season_info(destination: str, departure_date: Optional[date] = None) -> Dict[str, Any]:
    """Returns season type (holiday_superpeak, peak, high, shoulder, low), label, and price drop risk."""
    if not departure_date:
        return {"season": "standard", "label": "Стандартный сезон", "multiplier": 1.0, "price_drop_risk": "medium"}

    month = departure_date.month
    day = departure_date.day
    dest = (destination or "").lower()

    # True Christmas / New Year superpeak applies to departures spanning Dec 24..Jan 1.
    # Jan 3+ departures return to regular winter pricing right after Polish Trzech Kroli (Jan 6).
    is_ny_christmas = (month == 12 and day >= 20) or (month == 1 and day <= 2)

    if any(k in dest for k in ("egypt", "египет", "sharm", "hurghada", "marsa")):
        # Egypt: Winter/spring/autumn is main sun season; summer school holidays stay close to baseline.
        if is_ny_christmas:
            return {
                "season": "holiday_superpeak",
                "label": "Новогодний суперпик в Египте",
                "multiplier": 1.35,
                "price_drop_risk": "very_low",
                "risk_expl": "перед праздниками чартеры и лучшие номера распродаются, действуют праздничные надбавки",
            }
        elif month in (10, 11, 3, 4):
            return {
                "season": "peak",
                "label": "Высокий бархатный сезон в Египте",
                "multiplier": 1.12,
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
                "multiplier": 0.98,
                "price_drop_risk": "medium",
                "risk_expl": "стабильные тарифы, регулярные спецпредложения туроператоров",
            }
        else:
            return {
                "season": "low",
                "label": "Летний жаркий сезон в Египте",
                "multiplier": 0.95,
                "price_drop_risk": "high",
                "risk_expl": "офф-сезон из-за жары, частые промо-тарифы и горящие предложения",
            }

    elif any(k in dest for k in ("uae", "оаэ", "dubai", "дубай", "emirates", "эмираты")):
        if is_ny_christmas:
            return {
                "season": "holiday_superpeak",
                "label": "Новогодний суперпик в ОАЭ",
                "multiplier": 1.40,
                "price_drop_risk": "very_low",
                "risk_expl": "максимальный праздничный спрос, отели и рейсы быстро распродаются",
            }
        elif month in (10, 11, 12, 1, 2, 3, 4):
            return {
                "season": "peak",
                "label": "Высокий комфортный сезон в ОАЭ",
                "multiplier": 1.20,
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
                "multiplier": 0.78,
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


def _parse_dep_date(val: Any) -> Optional[date]:
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str) and len(val) >= 10:
        try:
            return date.fromisoformat(val[:10])
        except ValueError:
            return None
    return None


def get_season_bracket(destination: str, departure_date: Optional[date]) -> str:
    """Coarse seasonal regime bracket used to prioritize apples-to-apples historical pricing."""
    if not departure_date:
        return "unknown"
    info = get_destination_season_info(destination, departure_date)
    if info.get("season") == "holiday_superpeak":
        return "holiday_superpeak"
    m = departure_date.month
    if m in (11, 12, 1, 2):
        return "winter"
    if m in (6, 7, 8):
        return "summer"
    return "shoulder_peak"


def compute_seasonal_baseline_metrics(
    *,
    destination: str,
    target_dep_date: Optional[date],
    duration_nights: int,
    adults: int,
    children: int,
    rate_samples: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Computes truthful seasonal baseline (median / min / max PLN) for target departure & party.

    Prioritizes historical snapshots from the same seasonal regime (e.g. winter vs winter) when at
    least 3 explicit-date observations exist, preventing cross-season holiday/summer distortion.
    Falls back to clamped cross-season scaling only when same-season history is sparse.
    """
    target_season = get_destination_season_info(destination, target_dep_date)
    target_mult = max(0.5, float(target_season.get("multiplier", 1.0)))
    target_bracket = get_season_bracket(destination, target_dep_date)

    same_bracket_scaled_rates: List[float] = []
    all_scaled_rates: List[float] = []

    for sample in rate_samples:
        pure_rate = float(sample.get("pure_hotel_night_rate") or 0.0)
        if pure_rate <= 0:
            continue

        is_pre_unseasoned = bool(sample.get("is_already_unseasoned"))
        s_date = _parse_dep_date(sample.get("departure_date"))
        has_explicit_date = s_date is not None
        eff_date = s_date or target_dep_date

        if is_pre_unseasoned:
            # Normalized snapshot already represents de-seasoned base rate
            ratio = max(0.75, min(1.35, target_mult))
            scaled_rate = pure_rate * ratio
            all_scaled_rates.append(scaled_rate)
            continue

        snap_season = get_destination_season_info(destination, eff_date)
        snap_mult = max(0.5, float(snap_season.get("multiplier", 1.0)))
        ratio = max(0.75, min(1.35, target_mult / snap_mult))
        scaled_rate = pure_rate * ratio
        all_scaled_rates.append(scaled_rate)

        if has_explicit_date and target_bracket != "unknown":
            snap_bracket = get_season_bracket(destination, s_date)
            near_target = bool(
                target_dep_date
                and s_date
                and abs((s_date - target_dep_date).days) <= 45
                and target_bracket != "holiday_superpeak"
                and snap_bracket != "holiday_superpeak"
            )
            if snap_bracket == target_bracket or near_target:
                same_bracket_scaled_rates.append(scaled_rate)

    used_same_season = len(same_bracket_scaled_rates) >= 3
    chosen_rates = same_bracket_scaled_rates if used_same_season else all_scaled_rates

    if len(chosen_rates) < 3:
        return {
            "has_baseline": False,
            "used_same_season": False,
            "samples_used": len(chosen_rates),
            "season_info": target_season,
            "typical_median_pln": None,
            "hist_min_pln": None,
            "hist_max_pln": None,
        }

    sorted_rates = sorted(chosen_rates)
    med_rate = sorted_rates[len(sorted_rates) // 2]
    min_rate = sorted_rates[0]
    max_rate = sorted_rates[-1]

    typical_median_pln = round(
        CostDecomposer.recompose(
            pure_hotel_night_per_adult=med_rate,
            duration_nights=duration_nights,
            adults=adults,
            children=children,
            destination=destination,
        ),
        1,
    )
    hist_min_pln = round(
        CostDecomposer.recompose(
            pure_hotel_night_per_adult=min_rate,
            duration_nights=duration_nights,
            adults=adults,
            children=children,
            destination=destination,
        ),
        1,
    )
    hist_max_pln = round(
        CostDecomposer.recompose(
            pure_hotel_night_per_adult=max_rate,
            duration_nights=duration_nights,
            adults=adults,
            children=children,
            destination=destination,
        ),
        1,
    )

    return {
        "has_baseline": True,
        "used_same_season": used_same_season,
        "samples_used": len(chosen_rates),
        "season_info": target_season,
        "typical_median_pln": typical_median_pln,
        "hist_min_pln": hist_min_pln,
        "hist_max_pln": hist_max_pln,
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

    # 1. Decompose current offer & season info
    season_info = get_destination_season_info(destination, departure_date)
    today = date.today()
    days_to_dep = (departure_date - today).days if departure_date else 30

    # 2. Prepare pure rate samples for this specific hotel
    rate_samples: List[Dict[str, Any]] = []
    if hist_snapshots:
        for snap in hist_snapshots:
            if snap.get("pure_hotel_night_rate") and float(snap["pure_hotel_night_rate"]) > 0:
                rate_samples.append({
                    "pure_hotel_night_rate": float(snap["pure_hotel_night_rate"]),
                    "departure_date": snap.get("departure_date"),
                    "is_already_unseasoned": True,
                })
                continue

            p_val = float(snap.get("price") or snap.get("total_price_pln") or 0.0)
            if p_val <= 0:
                continue
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
            rate_samples.append({
                "pure_hotel_night_rate": float(raw_pure),
                "departure_date": snap.get("departure_date"),
                "is_already_unseasoned": False,
            })

    baseline = compute_seasonal_baseline_metrics(
        destination=destination,
        target_dep_date=departure_date,
        duration_nights=nights,
        adults=adults,
        children=children,
        rate_samples=rate_samples,
    )
    has_history = bool(baseline["has_baseline"])
    typical_median_pln = baseline["typical_median_pln"]
    hist_min_pln = baseline["hist_min_pln"] if has_history else total_price_pln
    samples_used = int(baseline["samples_used"])

    # 4. Compute Unified Deal Score (0-100) using single-source-of-truth engine
    ta_val = float(ta_rating) if (ta_rating is not None and float(ta_rating) > 0) else None
    is_budget_tier = bool(ta_val is not None and ta_val < 3.5)
    search_filter_type = classify_filter_type(
        None, checkin_dates=[departure_date] if departure_date else None
    )

    delta_vs_typical_pct: Optional[float] = None
    if has_history and typical_median_pln and typical_median_pln > 0:
        delta_vs_typical_pct = round(
            ((total_price_pln - typical_median_pln) / typical_median_pln) * 100.0, 1
        )

    # 6. Real 48-Hour Price Change (strictly requires mature observations >= 4)
    real_drop_48h_pct: Optional[float] = None
    if hist_snapshots and has_history:
        now_utc = datetime.now(timezone.utc)
        candidates_48h = []
        for snap in hist_snapshots:
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

    assessment = compute_unified_deal_assessment(
        latest_price=total_price_pln,
        typical_price=typical_median_pln,
        hist_df=None,
        samples_count=samples_used if has_history else len(rate_samples),
        ta_rating=ta_val,
        filter_type=search_filter_type,
        days_to_dep=days_to_dep,
        season_info=season_info,
        change_48h_pct=real_drop_48h_pct,
    )
    final_score = int(assessment["deal_score"])
    verdict = str(assessment["hopper_verdict"])
    badge = str(assessment["deal_badge"])
    forecast_reason = str(assessment["recommendation"])
    confidence = 0.50 if not has_history else (0.90 if verdict == "BUY NOW" else 0.85)

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
