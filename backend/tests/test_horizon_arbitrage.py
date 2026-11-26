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

