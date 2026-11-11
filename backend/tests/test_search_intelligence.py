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
