"""
Unit tests for HorizonArbitrageService (Early Booking vs Standard vs Last Minute).
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from app.models.hotel import Hotel
from app.models.cohort import OfferCohort
from app.models.price_snapshot import PriceSnapshot
from app.services.horizon_arbitrage_service import HorizonArbitrageService


@pytest.mark.asyncio
async def test_horizon_arbitrage_calculation(setup_test_db):
    session_factory = setup_test_db
    async with session_factory() as session:
        # Seed test hotel
        hotel = Hotel(
            hotel_id="test-horizon-resort",
            display_name="Test Horizon Resort 5★",
            country="Египет",
            stars=5,
        )
        session.add(hotel)
        await session.commit()

        # Seed Standard cohort & snapshot (recorded 25 days before departure)
        today = date.today()
        dep_date_std = today + timedelta(days=25)
        cohort_std = OfferCohort(
            cohort_hash="hash_std_001",
            hotel_id="test-horizon-resort",
            destination_code="egypt",
            checkin_date=dep_date_std,
            checkout_date=dep_date_std + timedelta(days=7),
            duration_nights=7,
            airport_code="WAW",
            board_basis="All Inclusive",
            adults=2,
            children=1,
            offer_url="https://fly.pl/wycieczka/test-std",
        )
        session.add(cohort_std)
        await session.commit()
        await session.refresh(cohort_std)

        snap_std = PriceSnapshot(
            cohort_id=cohort_std.cohort_id,
            total_price_pln=6500.0,
            price_per_night_per_pax=6500.0 / 21,
            recorded_at=datetime.now(timezone.utc),
        )
        session.add(snap_std)

        # Seed Last-Minute cohort & snapshot (recorded 2 days before departure)
        dep_date_lm = today + timedelta(days=2)
        cohort_lm = OfferCohort(
            cohort_hash="hash_lm_001",
            hotel_id="test-horizon-resort",
            destination_code="egypt",
            checkin_date=dep_date_lm,
            checkout_date=dep_date_lm + timedelta(days=7),
            duration_nights=7,
            airport_code="WAW",
            board_basis="All Inclusive",
            adults=2,
            children=1,
            offer_url="https://fly.pl/wycieczka/test-lm",
        )
        session.add(cohort_lm)
        await session.commit()
        await session.refresh(cohort_lm)

        snap_lm = PriceSnapshot(
            cohort_id=cohort_lm.cohort_id,
            total_price_pln=4800.0,
            price_per_night_per_pax=4800.0 / 21,
            recorded_at=datetime.now(timezone.utc),
        )
        session.add(snap_lm)
        await session.commit()

        # 1. Test Last Minute view (current price 4800 PLN vs 6500 PLN std)
        res_lm = await HorizonArbitrageService.get_hotel_horizon_arbitrage(
            db=session,
            hotel_id="test-horizon-resort",
            adults=2,
            children=1,
            duration_nights=7,
            checkin_date=dep_date_lm,
            current_price=4800.0,
        )
        assert res_lm["available"] is True
        assert res_lm["verdict"]["perspective"] == "LAST_MINUTE"
        assert res_lm["verdict"]["type"] == "REAL_DUMP"
        assert res_lm["verdict"]["savings_vs_standard_pln"] == 1700.0
        assert res_lm["verdict"]["savings_vs_standard_pct"] == 26.2

        # 2. Test Regular / Early view (current price 6500 PLN, evaluates LM history)
        res_reg = await HorizonArbitrageService.get_hotel_horizon_arbitrage(
            db=session,
            hotel_id="test-horizon-resort",
            adults=2,
            children=1,
            duration_nights=7,
            checkin_date=today + timedelta(days=90),
            current_price=6500.0,
        )
        assert res_reg["available"] is True
        assert res_reg["verdict"]["perspective"] == "REGULAR_OR_EARLY"
        assert res_reg["verdict"]["type"] == "REGULAR_DUMPER"
        assert "Отель-сбросник" in res_reg["verdict"]["badge"]
        # Future departure (>7d out) must NOT show unrelated current-week LM vs regular direct_comparison
        assert res_reg["direct_comparison"] is None

        # 3. Airport isolation: requesting WAW when an LM/STD existed in GDN/KTW excludes unrelated airports
        cohort_gdn = OfferCohort(
            cohort_hash="hash_gdn_001",
            hotel_id="test-horizon-resort",
            destination_code="egypt",
            checkin_date=today + timedelta(days=1),
            checkout_date=today + timedelta(days=8),
            duration_nights=7,
            airport_code="GDN",
            board_basis="All Inclusive",
            adults=2,
            children=1,
            offer_url="https://fly.pl/wycieczka/test-gdn",
        )
        session.add(cohort_gdn)
        await session.commit()
        await session.refresh(cohort_gdn)
        session.add(PriceSnapshot(
            cohort_id=cohort_gdn.cohort_id,
            total_price_pln=3999.0,
            price_per_night_per_pax=3999.0 / 21,
            recorded_at=datetime.now(timezone.utc),
        ))
        await session.commit()

        res_waw = await HorizonArbitrageService.get_hotel_horizon_arbitrage(
            db=session,
            hotel_id="test-horizon-resort",
            adults=2,
            children=1,
            duration_nights=7,
            checkin_date=dep_date_lm,
            current_price=4800.0,
            airports=["WAW", "WMI", "RDO"],
        )
        assert res_waw["available"] is True
        # Minimum LM price from WAW must remain 4800, not polluted by GDN 3999
        assert res_waw["horizons"]["last_minute"]["min_price_pln"] == 4800.0
        assert res_waw["direct_comparison"] is not None
        assert res_waw["direct_comparison"]["standard_offer"]["airport"] == "WAW"


@pytest.mark.asyncio
async def test_horizon_arbitrage_uses_real_latest_prices_no_rescaling_and_excludes_stale_lm(setup_test_db):
    """Ensures 7n prices are NEVER scaled 6/7 to fabricate fake 5878 PLN deals,
    stale snapshots (>48h) or near-term <=4d departures are excluded from standard offers,
    and updated higher latest prices supersede old low snapshots on the same cohort.
    """
    session_factory = setup_test_db
    async with session_factory() as session:
        hotel = Hotel(
            hotel_id="test-real-price-resort",
            display_name="Test Real Price Resort",
            country="Египет",
            stars=4,
        )
        session.add(hotel)
        await session.commit()

        today = date.today()
        dep_4d = today + timedelta(days=4)

        # 1. Stale 3-day-old snapshot for 7n on a departure that is NOW 4 days away
        c_stale_lm = OfferCohort(
            cohort_hash="hash_stale_lm",
            filter_id="lastminute_egypt_0_4",
            hotel_id="test-real-price-resort",
            destination_code="egypt",
            checkin_date=dep_4d,
            checkout_date=dep_4d + timedelta(days=7),
            duration_nights=7,
            airport_code="KTW",
            board_basis="All Inclusive",
            adults=2,
            children=1,
            offer_url="https://fly.pl/wycieczka/stale-7n",
        )
        session.add(c_stale_lm)
        await session.flush()
        session.add(PriceSnapshot(
            cohort_id=c_stale_lm.cohort_id,
            filter_id="lastminute_egypt_0_4",
            total_price_pln=6858.0,
            price_per_night_per_pax=326.0,
            recorded_at=datetime.now(timezone.utc) - timedelta(days=3),
        ))

        # 2. Fresh regular cohort (7d out, 7n): yesterday 7000 -> today rose to 7600
        dep_7d = today + timedelta(days=7)
        c_reg = OfferCohort(
            cohort_hash="hash_fresh_reg",
            filter_id="7_10_days",
            hotel_id="test-real-price-resort",
            destination_code="egypt",
            checkin_date=dep_7d,
            checkout_date=dep_7d + timedelta(days=7),
            duration_nights=7,
            airport_code="WAW",
            board_basis="All Inclusive",
            adults=2,
            children=1,
            offer_url="https://fly.pl/wycieczka/fresh-reg-7n",
        )
        session.add(c_reg)
        await session.flush()
        session.add(PriceSnapshot(
            cohort_id=c_reg.cohort_id,
            filter_id="7_10_days",
            total_price_pln=7000.0,
            price_per_night_per_pax=333.0,
            recorded_at=datetime.now(timezone.utc) - timedelta(hours=24),
        ))
        session.add(PriceSnapshot(
            cohort_id=c_reg.cohort_id,
            filter_id="7_10_days",
            total_price_pln=7600.0,
            price_per_night_per_pax=362.0,
            recorded_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        ))
        await session.commit()

        # Viewing current 6-night LM at 6137 PLN:
        res = await HorizonArbitrageService.get_hotel_horizon_arbitrage(
            db=session,
            hotel_id="test-real-price-resort",
            adults=2,
            children=1,
            duration_nights=6,
            checkin_date=dep_4d,
            current_price=6137.0,
        )
        assert res["available"] is True
        dc = res["direct_comparison"]
        assert dc is not None
        # Standard offer must be the LATEST REAL price (7600 PLN) on dep_7d,
        # NOT 6858 * 6/7 = 5878 and NOT yesterday's 7000!
        assert dc["standard_offer"]["price_pln"] == 7600.0
        assert dc["standard_offer"]["checkin_date"] == str(dep_7d)
        assert dc["is_hot_cheaper"] is True
        assert dc["is_std_cheaper"] is False


