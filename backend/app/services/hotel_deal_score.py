#!/usr/bin/env python3
"""Per-hotel Deal Score and Δ vs typical price (shared with departure analytics)."""

from __future__ import annotations

import math
import re
import statistics
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

MIN_PREMIUM_PLATEAU_HOURS = 6.0
MIN_PREMIUM_OBSERVATIONS = 2
ISOLATED_SPIKE_NEIGHBOR_RATIO = 0.55
# TripAdvisor: полный вес влияния на Deal Score при достаточном числе отзывов.
TA_DEAL_FULL_WEIGHT_REVIEWS = 50
TA_DEAL_NEUTRAL_RATING = 3.8
TA_DEAL_MAX_ADJUST = 8.0


def _clamp(v: float, lo: float, hi: float) -> float:
    if v is None:
        return lo
    try:
        val = float(v)
        if val != val or math.isnan(val):
            return lo
        return max(lo, min(hi, val))
    except (TypeError, ValueError):
        return lo


def _typical_observation_gap_hours(times: list, default: float = 1.0) -> float:
    """Median interval between consecutive observations (hours), ignoring long data gaps."""
    if len(times) < 2:
        return max(default, 0.5)
    gaps = []
    for i in range(1, len(times)):
        gaps.append((times[i] - times[i - 1]).total_seconds() / 3600.0)
    if not gaps:
        return max(default, 0.5)
    sorted_gaps = sorted(gaps)
    if len(sorted_gaps) >= 3:
        core = sorted_gaps[: max(1, (len(sorted_gaps) * 2) // 3)]
        typical = core[len(core) // 2]
    elif len(sorted_gaps) == 2:
        typical = sorted_gaps[0]
    else:
        typical = sorted_gaps[0]
    return max(typical, 0.5)


def _data_gap_threshold_hours(typical_gap: float) -> float:
    """Gap longer than this is treated as missing data, not price continuity."""
    return max(6.0, float(typical_gap) * 3.0)


def _iter_price_plateaus(times, prices):
    if not times or not prices or len(times) != len(prices):
        return
    typical_gap = _typical_observation_gap_hours(times)
    gap_threshold = _data_gap_threshold_hours(typical_gap)
    idx = 0
    while idx < len(prices):
        price = float(prices[idx])
        end = idx
        while end + 1 < len(prices) and float(prices[end + 1]) == price:
            end += 1
        if end + 1 < len(times):
            gap_after = (times[end + 1] - times[end]).total_seconds() / 3600.0
            if gap_after > gap_threshold:
                hours = typical_gap if end == idx else (
                    (times[end] - times[idx]).total_seconds() / 3600.0 + typical_gap
                )
            else:
                hours = (times[end + 1] - times[idx]).total_seconds() / 3600.0
        elif end > idx:
            hours = (times[end] - times[idx]).total_seconds() / 3600.0 + typical_gap
        elif idx > 0:
            hours = (times[idx] - times[idx - 1]).total_seconds() / 3600.0
        else:
            hours = typical_gap
        yield price, max(hours, 0.5)
        idx = end + 1


def _price_plateau_segments(grp: pd.DataFrame, time_col: str, price_col: str):
    if grp is None or grp.empty:
        return []
    work = grp.sort_values(time_col).dropna(subset=[time_col, price_col])
    if work.empty:
        return []
    times_series = work[time_col]
    if not pd.api.types.is_datetime64_any_dtype(times_series):
        times = pd.to_datetime(times_series, utc=True).tolist()
    else:
        if times_series.dt.tz is None:
            times = times_series.dt.tz_localize("UTC").tolist()
        else:
            times = times_series.dt.tz_convert("UTC").tolist()
    prices = work[price_col].astype(float).tolist()
    return list(_iter_price_plateaus(times, prices))


def time_weighted_price_baseline_from_segments(segments):
    if not segments:
        return None
    total_hours = sum(h for _, h in segments)
    if total_hours <= 0:
        return float(segments[-1][0])
    return sum(p * h for p, h in segments) / total_hours


def time_weighted_price_quantile_from_segments(segments, quantile: float):
    if not segments:
        return None
    q = max(0.0, min(1.0, float(quantile)))
    ordered = sorted(segments, key=lambda x: x[0])
    total_hours = sum(h for _, h in ordered)
    if total_hours <= 0:
        return float(ordered[-1][0])
    target = total_hours * q
    seen = 0.0
    for price, hours in ordered:
        seen += hours
        if seen >= target:
            return float(price)
    return float(ordered[-1][0])


def time_weighted_price_baseline(
    grp: pd.DataFrame,
    time_col: str = "scraped_at",
    price_col: str = "price",
    segments: Optional[list] = None,
):
    if segments is None:
        segments = _price_plateau_segments(grp, time_col, price_col)
    return time_weighted_price_baseline_from_segments(segments)


def time_weighted_price_quantile(
    grp: pd.DataFrame,
    quantile: float,
    time_col: str = "scraped_at",
    price_col: str = "price",
    segments: Optional[list] = None,
):
    if segments is None:
        segments = _price_plateau_segments(grp, time_col, price_col)
    return time_weighted_price_quantile_from_segments(segments, quantile)


def time_weighted_price_ecdf(segments, price: float) -> float:
    """Return the fraction of time (0.0 to 1.0) the hotel price was <= given price."""
    if not segments:
        return 0.5
    total_hours = sum(h for _, h in segments)
    if total_hours <= 0:
        return 0.5
    ordered = sorted(segments, key=lambda x: x[0])
    if price < ordered[0][0]:
        return 0.0
    if price >= ordered[-1][0]:
        return 1.0
    # Walk segments and linearly interpolate between discrete price levels
    cum_hours = 0.0
    for i in range(len(ordered)):
        p, h = ordered[i]
        if price < p:
            # Interpolate between previous segment and current
            prev_p = ordered[i - 1][0] if i > 0 else p
            prev_fraction = (cum_hours - (ordered[i - 1][1] if i > 0 else 0)) / total_hours
            cur_fraction = cum_hours / total_hours
            if p == prev_p:
                return cur_fraction
            ratio = (price - prev_p) / (p - prev_p)
            return _clamp(prev_fraction + ratio * (cur_fraction - prev_fraction), 0.0, 1.0)
        cum_hours += h
    return _clamp(cum_hours / total_hours, 0.0, 1.0)


def compute_smooth_rarity_score(segments, latest: float) -> float:
    """Smooth rarity score [10, 100] based on continuous ECDF quantile.
    
    Lowest historical price -> 100
    p10 price               -> 90
    p25 price               -> 75
    median (p50)            -> 50
    p75 price               -> 25
    highest historical price-> 10
    """
    if not segments or len(segments) == 1:
        return 50.0
    min_p = min(p for p, _ in segments)
    max_p = max(p for p, _ in segments)
    if min_p >= max_p:
        return 50.0

    cdf = time_weighted_price_ecdf(segments, latest)
    # cdf=0.0 (cheapest ever) -> 100.0, cdf=1.0 (most expensive ever) -> 10.0
    # cdf=0.5 -> 50.0
    rarity = 100.0 - cdf * 90.0
    return _clamp(rarity, 10.0, 100.0)


def robust_premium_peak(
    grp: pd.DataFrame,
    display_ceiling: float,
    time_col: str = "scraped_at",
    price_col: str = "price",
) -> Optional[float]:
    """Peak above display ceiling, ignoring short-lived isolated spikes (scraping glitches)."""
    if grp is None or grp.empty or display_ceiling is None:
        return None
    ceiling = float(display_ceiling)
    work = grp.dropna(subset=[time_col, price_col]).copy()
    if work.empty:
        return None
    work[price_col] = pd.to_numeric(work[price_col], errors="coerce")
    work = work.dropna(subset=[price_col]).sort_values(time_col)
    segments = _price_plateau_segments(work, time_col, price_col)
    if not segments:
        return None

    obs_above = work[work[price_col] > ceiling]
    obs_count_by_price: Dict[float, int] = {}
    for price, count in obs_above[price_col].astype(float).value_counts().items():
        obs_count_by_price[float(price)] = int(count)

    candidates: List[float] = []
    for i, (price, hours) in enumerate(segments):
        price = float(price)
        if price <= ceiling:
            continue
        obs_n = obs_count_by_price.get(price, 0)
        sustained = hours >= MIN_PREMIUM_PLATEAU_HOURS or obs_n >= MIN_PREMIUM_OBSERVATIONS
        if not sustained:
            continue
        if 0 < i < len(segments) - 1:
            prev_p = float(segments[i - 1][0])
            next_p = float(segments[i + 1][0])
            threshold = price * ISOLATED_SPIKE_NEIGHBOR_RATIO
            if prev_p < threshold and next_p < threshold:
                continue
        candidates.append(price)
    return max(candidates) if candidates else None


def build_premium_history_by_hotel(
    df_history: pd.DataFrame,
    display_ceiling: Optional[float],
    time_col: str = "scraped_at",
    price_col: str = "price",
) -> Dict[str, Dict[str, Any]]:
    """Peak prices per hotel in the full history band (up to history ceiling)."""
    out: Dict[str, Dict[str, Any]] = {}
    if df_history is None or df_history.empty:
        return out
    for name, grp in df_history.groupby("hotel_name", sort=False):
        prices = grp[price_col].astype(float)
        if prices.empty:
            continue
        premium_peak = robust_premium_peak(grp, display_ceiling, time_col, price_col)
        out[str(name)] = {
            "history_max": float(prices.max()),
            "premium_peak": premium_peak,
        }
    return out


def comeback_from_premium(
    current_price,
    premium_info: Optional[Dict[str, Any]],
    display_ceiling,
    min_drop_pct: float = 8.0,
) -> Optional[Dict[str, Any]]:
    """Hotel re-entered display band after being much more expensive in history."""
    if not premium_info or display_ceiling is None:
        return None
    try:
        current = float(current_price)
    except (TypeError, ValueError):
        return None
    if current > float(display_ceiling):
        return None
    peak = premium_info.get("premium_peak")
    if peak is None or peak <= float(display_ceiling):
        return None
    drop = (float(peak) - current) / float(peak) * 100.0
    if drop < min_drop_pct:
        return None
    return {
        "peak_price": float(peak),
        "drop_from_peak_pct": drop,
        "badge_html": (
            f"↩ Было до {peak:.0f} PLN"
            f' <span style="opacity:.85">(−{drop:.0f}%)</span>'
        ),
    }


def time_weighted_price_volatility(grp: pd.DataFrame, time_col: str = "scraped_at", price_col: str = "price"):
    segments = _price_plateau_segments(grp, time_col, price_col)
    if len(segments) < 2:
        return None
    total_hours = sum(h for _, h in segments)
    if total_hours <= 0:
        return None
    mean = sum(p * h for p, h in segments) / total_hours
    if mean <= 0:
        return None
    var = sum(h * (p - mean) ** 2 for p, h in segments) / total_hours
    return float(var ** 0.5 / mean)


def _listing_page_url(base_url: str, page_number: int) -> str:
    if page_number <= 1:
        return base_url
    if "?" in base_url:
        path, query = base_url.split("?", 1)
    else:
        path, query = base_url, ""
    query = re.sub(r"filter(?:\[|%5B)fp(?:\]|%5D)=[^&]*&?", "", query).strip("&")
    if not path.endswith("/"):
        path += "/"
    query_part = f"?{query}" if query else ""
    return f"{path}p:{page_number}/{query_part}"


def fetch_tripadvisor_from_listing_url(
    search_url: str,
    *,
    max_pages: int = 5,
    timeout_s: float = 25,
) -> Dict[str, Dict[str, Any]]:
    """Снимок TA с live-выдачи fly.pl (для backfill, пока CSV без ta_* колонок)."""
    import html as ihtml

    try:
        import requests
    except ImportError:
        return {}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    by_name: Dict[str, Dict[str, Any]] = {}
    by_offer: Dict[str, Dict[str, Any]] = {}

    for page_number in range(1, max_pages + 1):
        url = _listing_page_url(search_url, page_number)
        try:
            resp = requests.get(url, headers=headers, timeout=timeout_s)
        except Exception:
            break
        if resp.status_code != 200 or "card-offer-search" not in resp.text:
            break
        cards = re.split(r'<div class="card-offer-search', resp.text)[1:]
        if not cards:
            break
        page_hits = 0
        for card in cards:
            ta = extract_tripadvisor_from_card_html(card)
            if not ta.get("ta_rating"):
                continue
            name = ""
            mh = re.search(r'<h2[^>]*property="schema:name"[^>]*>(.*?)</h2>', card, re.S)
            if mh:
                name = re.sub(r"<[^>]+>", "", mh.group(1)).strip()
            if not name:
                nm = re.search(r'property="schema:name"[^>]*content="([^"]+)"', card)
                if nm:
                    name = ihtml.unescape(nm.group(1)).strip()
            offer_url = ""
            for pat in (
                r'property="schema:url"[^>]*content="([^"]+)"',
                r'data-phref="([^"]+)"',
            ):
                om = re.search(pat, card)
                if om:
                    offer_url = ihtml.unescape(om.group(1)).strip()
                    break
            payload = {
                "ta_rating": f"{float(ta['ta_rating']):.1f}",
                "ta_review_count": int(ta["ta_review_count"] or 0),
                "ta_source": "tripadvisor",
            }
            if name:
                by_name[name] = payload
                page_hits += 1
            if offer_url:
                by_offer[offer_url] = payload
        if page_hits == 0:
            break
    return {"by_name": by_name, "by_offer": by_offer}


def extract_tripadvisor_from_card_html(card_html: str) -> Dict[str, Any]:
    """TripAdvisor rating + review count из карточки fly.pl.

    ВАЖНО: fly.pl теперь показывает мульти-источник отзывов (Google + TripAdvisor)
    и собственный композитный рейтинг (schema:ratingValue). Чтобы не путать
    Google отзывы (например 4.5 ⭐) с TripAdvisor (например 3.2 🟢), парсер
    строго изолирует блок/картинку TripAdvisor и НЕ берет слепо schema:ratingValue.
    """
    empty = {"ta_rating": None, "ta_review_count": None, "ta_source": ""}
    if not card_html:
        return empty

    # 1. Официальный URL картинки/SVG рейтинга TripAdvisor (напр. ratings/traveler/3.2-37146-5.svg или 4.0-)
    img_m = re.search(
        r'tripadvisor\.com/[^"\']*/([0-9.]+)-[0-9]+-\d+\.svg',
        card_html,
        re.I,
    )
    if not img_m:
        img_m = re.search(
            r'tripadvisor\.com/img/cdsi/img2/ratings/traveler/([0-9.]+)-',
            card_html,
            re.I,
        )
    if img_m:
        try:
            empty["ta_rating"] = float(img_m.group(1))
        except (TypeError, ValueError):
            pass

    # 2. Bubble icon class pattern (напр. bubble_45 -> 4.5, bubble_32 -> 3.2)
    if empty["ta_rating"] is None:
        bubble_m = re.search(r'bubble_(\d{2})\b', card_html, re.I)
        if bubble_m:
            try:
                empty["ta_rating"] = float(bubble_m.group(1)) / 10.0
            except (TypeError, ValueError):
                pass

    # 3. Виджет мульти-источников: бейдж/блок TripAdvisor (отдельно от Google)
    if empty["ta_rating"] is None:
        ta_badge_m = re.search(
            r'(?:class="[^"]*tripadvisor[^"]*"|tripadvisor)[^>]*>[\s\S]{0,120}?\b([1-5][.,]\d)\b',
            card_html,
            re.I,
        )
        if ta_badge_m:
            try:
                empty["ta_rating"] = float(ta_badge_m.group(1).replace(",", "."))
            except (TypeError, ValueError):
                pass

    # 4. Текстовый балл строго рядом с упоминанием TripAdvisor
    if empty["ta_rating"] is None:
        text_m = re.search(
            r'(?:tripadvisor|ocena\s+podr[oó]żnych\s+tripadvisor)[^>]*?>[\s\S]{0,60}?\b([1-5][.,]\d)\s*(?:/\s*5)?',
            card_html,
            re.I,
        )
        if text_m:
            try:
                empty["ta_rating"] = float(text_m.group(1).replace(",", "."))
            except (TypeError, ValueError):
                pass

    # 5. Число отзывов строго для TripAdvisor:
    # 5a. В контейнере TripAdvisor (<div class="t-m-l">...<span class="c">...</span>)
    ta_block_m = re.search(r'<div class="t-m-l"[^>]*>(.*?)</div>', card_html, re.S)
    if ta_block_m:
        c_m = re.search(r'<span class="c"[^>]*>\s*([\d\s\xa0]+)\s*opini', ta_block_m.group(1), re.I)
        if c_m:
            try:
                empty["ta_review_count"] = int(re.sub(r"[^\d]", "", c_m.group(1)))
            except (TypeError, ValueError):
                pass

    # 5b. Рядом с упоминанием TripAdvisor
    if empty["ta_review_count"] is None and empty["ta_rating"] is not None:
        ta_rev_m = re.search(
            r'tripadvisor[\s\S]{0,150}?\b([\d\s\xa0]+)\s*(?:opini|recenz)',
            card_html,
            re.I,
        )
        if ta_rev_m:
            try:
                empty["ta_review_count"] = int(re.sub(r"[^\d]", "", ta_rev_m.group(1)))
            except (TypeError, ValueError):
                pass

    # 5c. Если подтвержден TripAdvisor и на карточке нет других источников (нет Google)
    if empty["ta_review_count"] is None and empty["ta_rating"] is not None:
        if "google" not in card_html.lower():
            count_m = re.search(r'property="schema:ratingCount"[^>]*content="([^"]+)"', card_html)
            if count_m:
                try:
                    empty["ta_review_count"] = int(float(count_m.group(1)))
                except (TypeError, ValueError):
                    pass
            else:
                opin_m = re.search(r"(\d+[\s\xa0]*\d*)\s*(?:opini|recenz)", card_html, re.I)
                if opin_m:
                    try:
                        empty["ta_review_count"] = int(re.sub(r"[^\d]", "", opin_m.group(1)))
                    except (TypeError, ValueError):
                        pass

    if empty["ta_rating"] is not None and empty["ta_rating"] > 0:
        empty["ta_source"] = "tripadvisor"

    return empty


def tripadvisor_review_weight(
    review_count: Any,
    *,
    full_weight_reviews: int = TA_DEAL_FULL_WEIGHT_REVIEWS,
) -> float:
    """0 для новых отелей; растёт с числом отзывов (в разумных пределах)."""
    try:
        reviews = int(review_count or 0)
    except (TypeError, ValueError):
        return 0.0
    if reviews <= 0:
        return 0.0
    return _clamp((reviews / max(1, full_weight_reviews)) ** 0.65, 0.0, 1.0)


def blend_tripadvisor_into_deal_score(
    deal_score: int,
    ta_rating: Any = None,
    ta_review_count: Any = None,
    *,
    neutral_rating: float = TA_DEAL_NEUTRAL_RATING,
    max_adjust: float = TA_DEAL_MAX_ADJUST,
    full_weight_reviews: int = TA_DEAL_FULL_WEIGHT_REVIEWS,
) -> Tuple[int, float]:
    """Смещает Deal Score по TA; без отзывов или рейтинга влияние ≈0."""
    try:
        cur_score = int(deal_score)
    except (TypeError, ValueError):
        cur_score = 50

    weight = tripadvisor_review_weight(ta_review_count, full_weight_reviews=full_weight_reviews)
    if weight < 0.05 or ta_rating is None:
        return cur_score, 0.0

    try:
        rating = float(ta_rating)
    except (TypeError, ValueError):
        return cur_score, 0.0

    if math.isnan(rating) or rating <= 0:
        return cur_score, 0.0

    delta = (rating - neutral_rating) * (max_adjust / 1.2)
    adjusted = int(round(_clamp(cur_score + delta * weight, 0, 100)))
    return adjusted, weight


def compute_hotel_deal_metrics(
    hist_df: pd.DataFrame,
    latest_price: float,
    time_col: str = "scraped_at",
    price_col: str = "price",
    ta_rating: Any = None,
    ta_review_count: Any = None,
    typical_price: Optional[float] = None,
) -> Dict[str, Any]:
    """Deal Score + Δ к типичной цене (как в дашборде, по истории офферов отеля)."""
    empty = {"deal_score": 0, "avg_delta_pct": 0.0, "confidence": "Low"}
    if hist_df is None or hist_df.empty:
        return empty
    try:
        latest = float(latest_price)
    except (TypeError, ValueError):
        return empty

    work = hist_df.dropna(subset=[time_col, price_col]).copy()
    if work.empty:
        return empty
    work[price_col] = pd.to_numeric(work[price_col], errors="coerce")
    work = work.dropna(subset=[price_col])
    if work.empty:
        return empty

    work = work.sort_values(time_col)
    prices = work[price_col].astype(float).tolist()
    samples = len(prices)
    segments = _price_plateau_segments(work, time_col, price_col)

    if typical_price is not None and typical_price > 0:
        typical = float(typical_price)
    else:
        tw_typical = time_weighted_price_baseline_from_segments(segments)
        p_median = float(statistics.median(prices)) if prices else latest
        if tw_typical is not None and p_median > 0:
            # If time-weighted plateau diverges heavily (>20%) from the point median due to sparse sampling/data gaps,
            # use point median to prevent phantom discount spikes
            if abs(tw_typical - p_median) / p_median > 0.20:
                typical = p_median
            else:
                typical = tw_typical
        else:
            typical = p_median or latest

    median = float(typical)
    p25 = time_weighted_price_quantile_from_segments(segments, 0.25) or latest
    p10 = time_weighted_price_quantile_from_segments(segments, 0.10) or latest
    min_p = float(min(p for p, _ in segments)) if segments else latest
    max_p = float(max(p for p, _ in segments)) if segments else latest

    rel_discount = (median - latest) / median if median > 0 else 0.0
    score_discount = _clamp(50 + rel_discount * 200, 0, 100)

    # Редкость: непрерывная оценка [10, 100] на основе ECDF (без ступенчатых скачков)
    score_rarity = compute_smooth_rarity_score(segments, latest)

    recent = prices[-3:] if len(prices) >= 3 else prices
    if len(recent) >= 3 and (recent[-1] < recent[-2] <= recent[-3] or recent[-1] <= recent[-2] < recent[-3]):
        score_momentum = 85
    elif len(recent) >= 2 and recent[-1] < recent[-2]:
        score_momentum = 70
    elif len(recent) >= 2 and recent[-1] > recent[-2]:
        score_momentum = 35
    else:
        score_momentum = 50

    score_stability = 50
    cv = time_weighted_price_volatility(work, time_col, price_col)
    if cv is not None:
        score_stability = _clamp(70 - cv * 120, 20, 85) if cv >= 0.01 else 50

    raw_deal_score = (
        score_discount * 0.40
        + score_rarity * 0.30
        + score_momentum * 0.20
        + score_stability * 0.10
    )
    confidence_weight = _clamp(samples / 20.0, 0.15, 1.0)
    deal_score = int(round(_clamp(50 + (raw_deal_score - 50) * confidence_weight, 0, 100)))

    if samples < 8:
        confidence = "Low"
    elif samples < 20:
        confidence = "Medium"
    else:
        confidence = "High"

    avg_delta_pct = round((latest - median) / median * 100.0, 2) if median > 0 else 0.0

    price_deal_score = deal_score
    deal_score, ta_weight = blend_tripadvisor_into_deal_score(
        deal_score,
        ta_rating,
        ta_review_count,
    )

    return {
        "deal_score": deal_score,
        "price_deal_score": price_deal_score,
        "ta_weight": round(ta_weight, 3),
        "avg_delta_pct": avg_delta_pct,
        "confidence": confidence,
    }


def compute_unified_deal_assessment(
    *,
    latest_price: float,
    typical_price: Optional[float],
    hist_df: Optional[pd.DataFrame] = None,
    samples_count: int = 0,
    ta_rating: Any = None,
    ta_review_count: Any = None,
    filter_type: str = "rolling",
    days_to_dep: Optional[int] = None,
    season_info: Optional[Dict[str, Any]] = None,
    upcoming_std_price: Optional[float] = None,
    upcoming_std_date: Optional[str] = None,
    change_48h_pct: Optional[float] = None,
    change_30d_pct: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Single source of truth for Deal Score, Verdict, and Filter-Specific Action Signals
    across Catalog, Live Search, and Hotel Passport.

    Key truthfulness guardrails:
    - Fewer than 3 historical samples -> neutral Warm-up (~50), never phantom hot deals.
    - Last-minute offer priced ABOVE an upcoming regular departure (>=5d) -> SURCHARGE / OVERPRICED.
    - Budget / low-TA hotels (< 3.5★) capped so cheap low quality is never sold as a 'Super Deal'.
    - Early booking (> 60d) never triggers fake 'seats running out urgently' FOMO.
    """
    latest = float(latest_price or 0.0)
    typ = float(typical_price) if (typical_price and typical_price > 0) else None
    has_history = samples_count >= 3 or (hist_df is not None and len(hist_df) >= 3)

    ta_val: Optional[float] = None
    try:
        if ta_rating is not None and float(ta_rating) > 0:
            ta_val = float(ta_rating)
    except (TypeError, ValueError):
        ta_val = None

    avg_delta_pct: Optional[float] = None
    if has_history and typ and typ > 0 and latest > 0:
        avg_delta_pct = round(((latest - typ) / typ) * 100.0, 1)

    # Check live upcoming regular departure comparison for last-minute
    spread_vs_std_pln: Optional[float] = None
    spread_vs_std_pct: Optional[float] = None
    is_lm_surcharge_vs_std = False
    is_lm_cheaper_vs_std = False
    if filter_type == "lastminute" and upcoming_std_price and upcoming_std_price > 0 and latest > 0:
        spread_vs_std_pln = round(latest - float(upcoming_std_price), 0)
        spread_vs_std_pct = round((spread_vs_std_pln / float(upcoming_std_price)) * 100.0, 1)
        if spread_vs_std_pln > 50:
            is_lm_surcharge_vs_std = True
        elif spread_vs_std_pln < -50:
            is_lm_cheaper_vs_std = True

    if not has_history:
        score = 50
        confidence = "Low"
        # Small TA nudge only; never claim BUY NOW without price history
        if ta_val is not None:
            score, _ = blend_tripadvisor_into_deal_score(score, ta_val, ta_review_count or 25)
        if is_lm_surcharge_vs_std:
            score = min(score, 42)
            verdict = "OVERPRICED"
            badge = "OVERPRICED"
            action_label = f"⚠️ Наценка (+{int(abs(spread_vs_std_pln))} zł vs регулярный)"
            recommendation = (
                f"Срочный вылет дороже ближайшего регулярного рейса ({upcoming_std_date or 'позже'}) "
                f"на {int(abs(spread_vs_std_pln))} zł."
            )
        else:
            verdict = "WAIT"
            badge = "FAIR_PRICE"
            action_label = "⏳ Мало истории"
            recommendation = (
                f"Зафиксировано мало замеров ({max(1, samples_count)}). "
                "Сравнение с нормой отключено до накопления истории."
            )
        return {
            "deal_score": int(score),
            "deal_badge": badge,
            "hopper_verdict": verdict,
            "action_label": action_label,
            "recommendation": recommendation,
            "avg_delta_pct": avg_delta_pct,
            "confidence": confidence,
            "spread_vs_std_pln": spread_vs_std_pln,
            "spread_vs_std_pct": spread_vs_std_pct,
        }

    # Base score from canonical plateau engine when hist_df is present
    if hist_df is not None and not hist_df.empty and len(hist_df) >= 3:
        base_metrics = compute_hotel_deal_metrics(
            hist_df,
            latest_price=latest,
            time_col="scraped_at",
            price_col="price",
            ta_rating=ta_val,
            ta_review_count=ta_review_count,
            typical_price=typ,
        )
        score = int(base_metrics.get("deal_score", 50))
        confidence = str(base_metrics.get("confidence", "Medium"))
        if avg_delta_pct is None and base_metrics.get("avg_delta_pct") is not None:
            avg_delta_pct = round(float(base_metrics["avg_delta_pct"]), 1)
    else:
        d = avg_delta_pct if avg_delta_pct is not None else 0.0
        raw = 50.0 - d * 2.0
        score = int(round(_clamp(raw, 25, 95)))
        if ta_val is not None:
            score, _ = blend_tripadvisor_into_deal_score(score, ta_val, ta_review_count or 25)
        confidence = "High" if samples_count >= 15 else "Medium"

    # Specialize score & verdict cleanly by filter_type
    s_label = (season_info or {}).get("label", "сезон")
    s_risk = (season_info or {}).get("price_drop_risk", "medium")
    d_abs = abs(round(avg_delta_pct or 0.0, 1))

    if filter_type == "lastminute":
        # Re-align score strictly to last-minute reality: real dump vs seasonal norm AND vs regular flight
        d = avg_delta_pct if avg_delta_pct is not None else 0.0
        if is_lm_surcharge_vs_std:
            # Surcharge over upcoming regular departure overrides any stale historical discount
            score = int(round(_clamp(42 - min(17, (spread_vs_std_pct or 0.0) * 0.5), 25, 43)))
            verdict = "OVERPRICED"
            badge = "OVERPRICED"
            action_label = f"⚠️ Регулярный дешевле (−{int(abs(spread_vs_std_pln))} zł)"
            recommendation = (
                f"Горящий вылет на {int(abs(spread_vs_std_pln))} zł дороже ближайшего стандартного рейса "
                f"({upcoming_std_date or 'через несколько дней'}). Покупать невыгодно."
            )
        elif d <= -15.0:
            score = int(round(_clamp(84 + min(14, (abs(d) - 15.0) * 0.7), 82, 98)))
            verdict = "BUY NOW"
            badge = "SUPER_DEAL" if score >= 88 else "GOOD_DEAL"
            action_label = f"🔥 Сброс −{d_abs:.0f}%"
            recommendation = (
                f"Реальный горящий дисконт −{d_abs:.0f}% к сезонной норме ({int(round(typ or latest))} zł)."
                + (
                    f" Также на {int(abs(spread_vs_std_pln))} zł дешевле обычного вылета ({upcoming_std_date})."
                    if is_lm_cheaper_vs_std and spread_vs_std_pln is not None
                    else ""
                )
            )
        elif d <= -8.0:
            score = int(round(_clamp(72 + (abs(d) - 8.0) * 1.4, 72, 83)))
            verdict = "BUY NOW" if score >= 80 else "WAIT"
            badge = "GOOD_DEAL" if score >= 80 else "FAIR_PRICE"
            action_label = f"⚡ Скидка −{d_abs:.0f}%"
            recommendation = (
                f"Цена на {d_abs:.0f}% ниже сезонной нормы ({int(round(typ or latest))} zł)."
            )
        elif d <= 5.0:
            score = int(round(_clamp(55 - d * 1.5, 46, 68)))
            verdict = "WAIT"
            badge = "FAIR_PRICE"
            action_label = "⚖️ Без скидки"
            recommendation = (
                f"Обычный тариф сезона (норма ~{int(round(typ or latest))} zł). Выраженного горящего сброса нет."
            )
        else:
            score = int(round(_clamp(44 - (d - 5.0) * 0.8, 25, 44)))
            verdict = "OVERPRICED"
            badge = "OVERPRICED"
            action_label = f"📈 Наценка +{d_abs:.0f}%"
            recommendation = (
                f"Наценка +{d_abs:.0f}% к сезонной норме ({int(round(typ or latest))} zł) на последние места перед вылетом."
            )
    elif filter_type == "early_booking":
        d = avg_delta_pct if avg_delta_pct is not None else 0.0
        c30 = change_30d_pct if change_30d_pct is not None else 0.0
        if (score >= 80 and d <= 0.0) or d <= -10.0:
            score = max(score, 80)
            verdict = "BUY NOW"
            badge = "GOOD_DEAL"
            action_label = "🟢 Выгодный EB"
            recommendation = f"Удачный тариф раннего бронирования (−{d_abs:.0f}% к медиане EB). Фиксация оправдана."
        elif (score < 45 and d >= 5.0) or d >= 10.0:
            score = min(score, 44)
            verdict = "OVERPRICED"
            badge = "OVERPRICED"
            action_label = f"🔴 Дорого для EB (+{d_abs:.0f}%)"
            recommendation = "Цена выше обычного старта раннего бронирования. Стоит подождать промо-коррекции."
        else:
            score = max(48, min(79, score))
            verdict = "WAIT"
            badge = "FAIR_PRICE"
            if c30 >= 3.0:
                action_label = f"📈 Рост +{c30:.0f}% за 30д"
                recommendation = "Базовый тариф раннего бронирования, заметен плавный рост от старта продаж."
            elif c30 <= -3.0:
                action_label = f"📉 Промо {c30:.0f}% за 30д"
                recommendation = "Цена снизилась за последний месяц, близко к выгодному уровню EB."
            else:
                action_label = "⚖️ Базовый EB"
                recommendation = "Спокойное плато раннего бронирования — резкой спешки нет."
    elif filter_type == "fixed_dates":
        d = avg_delta_pct if avg_delta_pct is not None else 0.0
        if (score >= 80 and d <= 0.0) or d <= -10.0:
            score = max(score, 80)
            verdict = "BUY NOW"
            badge = "SUPER_DEAL" if score >= 88 else "GOOD_DEAL"
            action_label = "🟢 Брать в окно"
            recommendation = f"Выгодная цена (−{d_abs:.0f}%) для фиксированных дат ({s_label}). На узких датах хорошие отели быстро уходят."
        elif (score < 45 and d >= 6.0) or d >= 12.0:
            score = min(score, 44)
            verdict = "OVERPRICED"
            badge = "OVERPRICED"
            action_label = f"🔴 Дорого (+{d_abs:.0f}%)"
            recommendation = "Тариф завышен относительно истории этого окна дат. Проверьте соседние даты вылета или BER."
        else:
            score = max(48, min(79, score))
            verdict = "WAIT"
            badge = "FAIR_PRICE"
            if s_risk in ("very_low", "low"):
                action_label = "⚠️ Риск Sold-Out"
                recommendation = f"Стандартная цена для пикового окна ({s_label}). Скидки маловероятны — следите за остатком отелей."
            else:
                action_label = "⚖️ Обычная цена"
                recommendation = "Цена в пределах нормы для выбранного окна дат."
    else:
        # 'rolling' standard window
        d = avg_delta_pct if avg_delta_pct is not None else 0.0
        if score >= 80 and d <= 0.0:
            verdict = "BUY NOW"
            badge = "SUPER_DEAL" if score >= 88 else "GOOD_DEAL"
            action_label = "🟢 Покупать"
            recommendation = f"Цена ниже сезонной нормы отеля (Δ {avg_delta_pct:+.1f}%). Удачная точка входа." if avg_delta_pct is not None else "Удачная точка входа по истории отеля."
        elif (score < 45 and d >= 5.0) or d >= 12.0:
            score = min(score, 44)
            verdict = "OVERPRICED"
            badge = "OVERPRICED"
            action_label = "🔴 Дорого"
            recommendation = f"Цена выше типичной нормы отеля (Δ {avg_delta_pct:+.1f}%). Лучше подождать снижения." if avg_delta_pct is not None else "Цена выше типичного уровня. Лучше подождать."
        else:
            score = max(48, min(79, score))
            verdict = "WAIT"
            badge = "FAIR_PRICE"
            action_label = "🟡 Следить"
            recommendation = f"Стандартная рыночная цена ({s_label}). Поставьте в Watchlist для отслеживания сбросов."

    # Quality Guardrail: never label < 3.5★ TripAdvisor as SUPER/GOOD BUY NOW
    if ta_val is not None and ta_val < 3.5:
        score = min(score, 62)
        if verdict == "BUY NOW":
            verdict = "WAIT"
            badge = "FAIR_PRICE"
            action_label = "🟡 Низкий TA"
            recommendation = f"Низкий рейтинг TripAdvisor ({ta_val:.1f}★) — низкая цена отражает скромный уровень сервиса."
    elif ta_val is not None and ta_val < 3.8 and score > 72:
        score = 72
        if verdict == "BUY NOW":
            verdict = "WAIT"
            badge = "FAIR_PRICE"

    return {
        "deal_score": int(score),
        "deal_badge": badge,
        "hopper_verdict": verdict,
        "action_label": action_label,
        "recommendation": recommendation,
        "avg_delta_pct": avg_delta_pct,
        "confidence": confidence,
        "spread_vs_std_pln": spread_vs_std_pln,
        "spread_vs_std_pct": spread_vs_std_pct,
    }
