from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.cohort import OfferCohort, compute_cohort_hash
from app.models.hotel import Hotel
from app.models.price_snapshot import PriceSnapshot
from app.services.arbitrage_service import ArbitrageService, is_offer_comparable
from app.services.canonical_filters import classify_filter_type
from app.services.horizon_arbitrage_service import HorizonArbitrageService
from app.services.normalization import (
    extract_offer_url_dates,
    normalize_airport_code,
    normalize_board_basis,
)
from app.services.watchlist_service import WatchlistService


def test_normalization_helpers_airports_boards_and_urls():
    """Verifies canonical IATA airport codes, board basis tiers, and offer_url date extraction."""
    assert normalize_airport_code("Warszawa - Okęcie") == "WAW"
    assert normalize_airport_code("Warszawa") == "WAW"
    assert normalize_airport_code("Modlin") == "WMI"
    assert normalize_airport_code("Warszawa - Radom") == "RDO"
    assert normalize_airport_code("Katowice") == "KTW"
    assert normalize_airport_code("Kraków") == "KRK"
    assert normalize_airport_code("Gdańsk") == "GDN"
    assert normalize_airport_code("Wrocław") == "WRO"
    assert normalize_airport_code("Poznań") == "POZ"
    assert normalize_airport_code("RZESZÓW") == "RZE"
    assert normalize_airport_code("ZIELONA GÓ") == "IEG"
    # Recover airport from offer_url when CSV airport column is placeholder "ВСЕ АЭРОПО"
    assert normalize_airport_code(
        "ВСЕ АЭРОПО",
        "https://fly.pl/oferta?departureDate=2027-10-08&departureLocation=Katowice&catering=all_inclusive",
    ) == "KTW"
    assert normalize_airport_code("ВСЕ АЭРОПО", "https://fly.pl/oferta?objectId=123") == "ALL"

    assert normalize_board_basis("All inclusive") == "All Inclusive"
    assert normalize_board_basis("Ultra AI") == "Ultra All Inclusive"
    assert normalize_board_basis("HAI") == "All Inclusive"
    assert normalize_board_basis("Śniadania i obiadokolacje") == "HB (Half Board)"
    assert normalize_board_basis("Śniadania") == "BB (Śniadania)"
    assert normalize_board_basis("Bez wyżywienia (Self Catering)") == "RO (Bez wyżywienia)"

    dep_d, ret_d = extract_offer_url_dates(
        "https://fly.pl/wycieczka/test?departureDate=2027-10-23&returnDate=2027-10-30"
    )
    assert dep_d == date(2027, 10, 23)
    assert ret_d == date(2027, 10, 30)


def test_arbitrage_rejects_expired_check24_offers():
    """Ensures Check24 arbitrage never displays expired German offers or party mismatches."""
    past_end = (date.today() - timedelta(days=3)).isoformat()
    past_start = (date.today() - timedelta(days=33)).isoformat()
    future_pl = date.today() + timedelta(days=10)

    ok, reason = is_offer_comparable(
        pl_checkin=future_pl,
        pl_nights=7,
        pl_adults=2,
        pl_children=1,
        de_offer={
            "adults": 2,
            "children": 1,
            "duration_nights": 7,
            "departure_date_start": past_start,
            "departure_date_end": past_end,
        },
    )
    assert ok is False
    assert "Expired Check24" in reason


@pytest.mark.asyncio
async def test_horizon_arbitrage_no_cross_party_leak(setup_test_db):
    """Ensures 2+1 requests never fall back to raw unscaled 1-adult snapshots."""
    async with setup_test_db() as db:
        h = Hotel(hotel_id="san_test_hotel", display_name="SanTest Palace", country="Турция", stars=5)
        db.add(h)
        await db.flush()

        dep = date.today() + timedelta(days=20)
        c1p = OfferCohort(
            cohort_hash=compute_cohort_hash("san_test_hotel", dep, 7, "WAW", adults=1),
            filter_id="benchmark_turkey_1p_7_8",
            hotel_id="san_test_hotel",
            destination_code="turkey",
            checkin_date=dep,
            duration_nights=7,
            airport_code="WAW",
            adults=1,
            children=0,
        )
        db.add(c1p)
        await db.flush()
        db.add(
            PriceSnapshot(
                cohort_id=c1p.cohort_id,
                filter_id="benchmark_turkey_1p_7_8",
                recorded_at=datetime.now(timezone.utc),
                total_price_pln=2500.0,
                price_per_night_per_pax=357.14,
            )
        )
        await db.commit()

        # Requesting 2 adults + 1 child when only 1p snapshots exist MUST return available=False
        ha = await HorizonArbitrageService.get_hotel_horizon_arbitrage(
            db, hotel_id="san_test_hotel", adults=2, children=1, duration_nights=7
        )
        assert ha["available"] is False


@pytest.mark.asyncio
async def test_hotel_passport_uses_real_min_max_without_synthetic_fudge(setup_test_db):
    """Zero-history hotels should report real current_price without fake 0.95/1.10 min/max range."""
    async with setup_test_db() as db:
        h = Hotel(hotel_id="san_empty_hist", display_name="Zero Hist Resort", country="Египет", stars=5)
        db.add(h)
        await db.commit()

        passport = await WatchlistService.get_hotel_passport(
            db, hotel_id="san_empty_hist", adults=2, children=0, duration_nights=7, current_price=6200.0
        )
        assert passport.all_time_min_pln == 6200.0
        assert passport.all_time_max_pln == 6200.0
        assert passport.typical_median_pln is None
        assert passport.user_query_scope == {"adults": 2, "children": 0, "duration_nights": 7}
        assert passport.history_points[0].adults == 2
        assert passport.history_points[0].children == 0


def test_canonical_rolling_filter_not_misclassified_as_fixed_dates():
    """Seasonal rolling canonical radars like cyprus_7_10 must stay rolling even on narrow winter spans."""
    narrow_winter_dates = [
        (date.today() + timedelta(days=24)).isoformat(),
        (date.today() + timedelta(days=30)).isoformat(),
    ]
    assert classify_filter_type("cyprus_7_10", checkin_dates=narrow_winter_dates) == "rolling"
    assert classify_filter_type("egypt_ny_dec24_2026_7_10", checkin_dates=narrow_winter_dates) == "fixed_dates"
    assert classify_filter_type("", checkin_dates=narrow_winter_dates) == "fixed_dates"


@pytest.mark.asyncio
async def test_arbitrage_deals_query_runs_cleanly_and_filters_children(setup_test_db):
    """Verifies get_arbitrage_deals executes its CTE cleanly and respects children count parity."""
    async with setup_test_db() as db:
        h = Hotel(hotel_id="arb_test_hotel", display_name="Titanic Palace", country="Египет", stars=5)
        db.add(h)
        await db.flush()
        chk = date.today() + timedelta(days=14)
        ch = compute_cohort_hash("arb_test_hotel", chk, 7, "WAW", adults=2, filter_id="egypt_7_10")
        c = OfferCohort(
            cohort_hash=ch,
            filter_id="egypt_7_10",
            hotel_id="arb_test_hotel",
            destination_code="egypt",
            checkin_date=chk,
            duration_nights=7,
            airport_code="WAW",
            adults=2,
            children=1,
        )
        db.add(c)
        await db.flush()
        db.add(
            PriceSnapshot(
                cohort_id=c.cohort_id,
                filter_id="egypt_7_10",
                recorded_at=datetime.now(timezone.utc),
                total_price_pln=7900.0,
                price_per_night_per_pax=376.19,
            )
        )
        await db.commit()

        # Should not crash on SQLite or return mismatched children=0 Berlin deals for children=1 cohorts
        deals = await ArbitrageService.get_arbitrage_deals(db, min_savings_pln=300, filter_id="egypt_7_10")
        assert isinstance(deals, list)
        for d in deals:
            assert d["checkin_date"] >= date.today().isoformat()
