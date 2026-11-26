from datetime import date, timedelta
from app.services.search_intelligence import (
    get_destination_season_info,
    evaluate_search_intelligence,
)


def test_season_info_detection():
    # New Year in Egypt
    ny_info = get_destination_season_info("egypt", date(2026, 12, 28))
    assert ny_info["season"] == "holiday_superpeak"
    assert ny_info["price_drop_risk"] == "very_low"

    # July in Turkey
    turkey_summer = get_destination_season_info("turkey", date(2026, 7, 15))
    assert turkey_summer["season"] == "peak"

    # Winter in Turkey (off-season)
    turkey_winter = get_destination_season_info("turkey", date(2026, 1, 20))
    assert turkey_winter["season"] == "low"
    assert turkey_winter["price_drop_risk"] == "high"


def test_evaluate_intelligence_with_history():
    # Hotel with historical rate around 300 zł/night
    hist = [
        {"price": 4000.0, "adults": 1, "children": 0, "duration_nights": 8},
        {"price": 4100.0, "adults": 1, "children": 0, "duration_nights": 8},
        {"price": 3950.0, "adults": 1, "children": 0, "duration_nights": 8},
    ]

    # Current offer dropped significantly (2,800 zł)
    dep_date = date.today() + timedelta(days=15)
    intel = evaluate_search_intelligence(
        destination="turkey",
        departure_date=dep_date,
        duration_nights=8,
        adults=1,
        children=0,
        total_price_pln=2800.0,
        stars=5,
        ta_rating=4.7,
        hist_snapshots=hist,
    )
    assert intel.deal_score >= 80
    assert intel.hopper_verdict == "BUY NOW"
    assert "Выгодная цена" in intel.recommendation or "локальное" in intel.recommendation or "Отличный" in intel.recommendation


def test_no_fake_superdeal_on_party_mismatch():
    # Historical data was for 2+1 adults (16,000 zł)
    hist_2p1 = [
        {"price": 16000.0, "adults": 2, "children": 1, "duration_nights": 10},
        {"price": 15500.0, "adults": 2, "children": 1, "duration_nights": 10},
    ]

    # Current offer is for 1 adult in low season at standard 2,200 zł (not a discount!)
    dep_date = date.today() + timedelta(days=40)
    intel = evaluate_search_intelligence(
        destination="turkey",
        departure_date=dep_date,
        duration_nights=8,
        adults=1,
        children=0,
        total_price_pln=2200.0,
        stars=4,
        ta_rating=4.1,
        hist_snapshots=hist_2p1,
    )
    # MUST NOT be 95 Hot SUPER_DEAL
    assert intel.deal_score < 80
    assert intel.hopper_verdict in ("WAIT", "OVERPRICED")


def test_delta_vs_typical_and_real_48h_drop():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    # 0. Sparse history (< 3 snapshots): delta_vs_typical_pct must be None, verdict WAIT
    sparse_hist = [
        {"price": 3000.0, "adults": 1, "children": 0, "duration_nights": 8},
    ]
    sparse_intel = evaluate_search_intelligence(
        destination="egypt",
        departure_date=date.today() + timedelta(days=20),
        duration_nights=8,
        adults=1,
        children=0,
        total_price_pln=2500.0,
        stars=4,
        ta_rating=4.2,
        hist_snapshots=sparse_hist,
    )
    assert sparse_intel.delta_vs_typical_pct is None
    assert sparse_intel.typical_median_pln is None
    assert sparse_intel.hopper_verdict == "WAIT"

    # 1. Mature history (>= 3 snapshots): drop_48h_pct must be None, delta_vs_typical_pct must be accurate
    hist = [
        {"price": 3000.0, "adults": 1, "children": 0, "duration_nights": 8},
        {"price": 3100.0, "adults": 1, "children": 0, "duration_nights": 8},
        {"price": 3050.0, "adults": 1, "children": 0, "duration_nights": 8},
    ]
    intel = evaluate_search_intelligence(
        destination="egypt",
        departure_date=date.today() + timedelta(days=20),
        duration_nights=8,
        adults=1,
        children=0,
        total_price_pln=2500.0,
        stars=4,
        ta_rating=4.2,
        hist_snapshots=hist,
    )
    assert intel.drop_48h_pct is None  # No recorded_at in snapshots -> no fake 48h drop
    assert intel.delta_vs_typical_pct is not None
    assert intel.delta_vs_typical_pct < 0  # 2500 vs ~3050 is ~-18%

    # 2. With 48h snapshot: drop_48h_pct must reflect real drop
    snap_48h_ago = now - timedelta(hours=48)
    hist_with_time = [
        {"price": 3000.0, "adults": 1, "children": 0, "duration_nights": 8, "recorded_at": snap_48h_ago.isoformat()},
        {"price": 3100.0, "adults": 1, "children": 0, "duration_nights": 8, "recorded_at": snap_48h_ago.isoformat()},
        {"price": 3050.0, "adults": 1, "children": 0, "duration_nights": 8, "recorded_at": snap_48h_ago.isoformat()},
    ]
    intel_48h = evaluate_search_intelligence(
        destination="egypt",
        departure_date=date.today() + timedelta(days=20),
        duration_nights=8,
        adults=1,
        children=0,
        total_price_pln=2400.0,
        stars=4,
        ta_rating=4.2,
        hist_snapshots=hist_with_time,
    )
    assert intel_48h.drop_48h_pct is not None
    # 2400 vs 3000 is -20.0%
    assert intel_48h.drop_48h_pct == -20.0


def test_post_ny_jan7_uses_winter_baseline_without_cross_season_inflation():
    # Post-New Year Jan 7 must NOT be classified as holiday_superpeak
    jan7_info = get_destination_season_info("egypt", date(2027, 1, 7))
    assert jan7_info["season"] != "holiday_superpeak"

    # Mixed history: summer expensive wakacje + winter Nov/Dec offers
    hist = [
        {"price": 11053.0, "adults": 2, "children": 1, "duration_nights": 7, "departure_date": "2027-07-29"},
        {"price": 10060.0, "adults": 2, "children": 1, "duration_nights": 7, "departure_date": "2027-08-29"},
        {"price": 11261.0, "adults": 2, "children": 1, "duration_nights": 7, "departure_date": "2027-10-03"},
        {"price": 7439.0, "adults": 2, "children": 1, "duration_nights": 7, "departure_date": "2026-12-06"},
        {"price": 7904.0, "adults": 2, "children": 1, "duration_nights": 7, "departure_date": "2026-12-13"},
        {"price": 8311.0, "adults": 2, "children": 1, "duration_nights": 7, "departure_date": "2026-11-26"},
    ]
    intel = evaluate_search_intelligence(
        destination="egypt",
        departure_date=date(2027, 1, 7),
        duration_nights=7,
        adults=2,
        children=1,
        total_price_pln=8492.0,
        stars=5,
        ta_rating=4.7,
        hist_snapshots=hist,
    )
    # Benchmark must reflect real winter level (~7900-8300 PLN), NOT ~12500 PLN
    assert intel.typical_median_pln is not None
    assert intel.typical_median_pln < 9200.0
    assert intel.hopper_verdict != "BUY NOW"
    assert intel.deal_score < 80



