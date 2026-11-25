import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.security import get_password_hash, create_access_token
from app.main import app
from app.models.cohort import OfferCohort, compute_cohort_hash
from app.models.hotel import Hotel
from app.models.price_snapshot import PriceSnapshot
from app.models.user import User
from app.models.watchlist import WatchlistItem
from app.services.watchlist_service import WatchlistService


@pytest.mark.asyncio
async def test_seasonality_outlook_endpoint_and_party_isolation(setup_test_db):
    """Verifies seasonality-outlook computes real DB anchors, monthly stats, and separates party sizes."""
    from app.services import analytics_service
    analytics_service._SEASONALITY_CACHE.clear()

    today = date.today()
    june_dep = (today + timedelta(days=45)).replace(day=15)
    july_dep = (june_dep + timedelta(days=32)).replace(day=15)
    now_dt = datetime.now(timezone.utc)

    async with setup_test_db() as db:
        hotel = Hotel(
            hotel_id="fh_hotel_tr_1",
            display_name="Grand Hunter Resort",
            country="Turkey",
            region="Antalya",
            stars=5,
            ta_rating=4.5,
        )
        db.add(hotel)
        await db.flush()

        # 2 adults cohorts across two months (cheaper first month, higher second month)
        c1_hash = compute_cohort_hash("fh_hotel_tr_1", june_dep, 7, "WAW", adults=2, filter_id="test_fh")
        c2_hash = compute_cohort_hash("fh_hotel_tr_1", july_dep, 7, "KTW", adults=2, filter_id="test_fh")
        # 2 adults + 1 child cohort with higher price (must NOT leak into 2 adults query)
        c_fam_hash = compute_cohort_hash("fh_hotel_tr_1", june_dep, 7, "WAW", adults=2, board_basis="UAI", filter_id="test_fh")

        c1 = OfferCohort(
            cohort_hash=c1_hash,
            filter_id="test_fh",
            hotel_id="fh_hotel_tr_1",
            destination_code="Turkey",
            checkin_date=june_dep,
            duration_nights=7,
            airport_code="WAW",
            adults=2,
            children=0,
        )
        c2 = OfferCohort(
            cohort_hash=c2_hash,
            filter_id="test_fh",
            hotel_id="fh_hotel_tr_1",
            destination_code="Turkey",
            checkin_date=july_dep,
            duration_nights=7,
            airport_code="KTW",
            adults=2,
            children=0,
        )
        c_fam = OfferCohort(
            cohort_hash=c_fam_hash,
            filter_id="test_fh",
            hotel_id="fh_hotel_tr_1",
            destination_code="Turkey",
            checkin_date=june_dep,
            duration_nights=7,
            airport_code="WAW",
            adults=2,
            children=1,
        )
        db.add_all([c1, c2, c_fam])
        await db.flush()

        snaps = [
            PriceSnapshot(cohort_id=c1.cohort_id, filter_id="test_fh", recorded_at=now_dt - timedelta(days=3), total_price_pln=5200.0, price_per_night_per_pax=371.0),
            PriceSnapshot(cohort_id=c1.cohort_id, filter_id="test_fh", recorded_at=now_dt - timedelta(days=2), total_price_pln=5000.0, price_per_night_per_pax=357.0),
            PriceSnapshot(cohort_id=c1.cohort_id, filter_id="test_fh", recorded_at=now_dt - timedelta(days=1), total_price_pln=4600.0, price_per_night_per_pax=328.0),
            PriceSnapshot(cohort_id=c2.cohort_id, filter_id="test_fh", recorded_at=now_dt - timedelta(days=3), total_price_pln=7800.0, price_per_night_per_pax=557.0),
            PriceSnapshot(cohort_id=c2.cohort_id, filter_id="test_fh", recorded_at=now_dt - timedelta(days=2), total_price_pln=7600.0, price_per_night_per_pax=542.0),
            PriceSnapshot(cohort_id=c2.cohort_id, filter_id="test_fh", recorded_at=now_dt - timedelta(days=1), total_price_pln=7400.0, price_per_night_per_pax=528.0),
            # Family snapshots should not mix with 2+0
            PriceSnapshot(cohort_id=c_fam.cohort_id, filter_id="test_fh", recorded_at=now_dt - timedelta(days=1), total_price_pln=14900.0, price_per_night_per_pax=709.0),
        ]
        db.add_all(snaps)
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v2/analytics/seasonality-outlook?destination=turkey&adults=2&children=0")
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_data"] is True
        assert body["party_label"] == "2 взр"
        assert body["anchors"]["snipe_record_pln"] == 4600.0
        assert body["anchors"]["seasonal_median_pln"] < 10000.0
        assert len(body["months"]) >= 2
        assert body["hunt_odds"]["cheapest_month"] == june_dep.strftime("%Y-%m")

        # Family request has < 5 snapshots -> honest insufficient data rather than falling back to 2+0
        resp_fam = await ac.get("/api/v2/analytics/seasonality-outlook?destination=turkey&adults=2&children=1")
        assert resp_fam.status_code == 200
        assert resp_fam.json()["has_data"] is False


@pytest.mark.asyncio
async def test_watchlist_trigger_lead_time_and_pause_filters(setup_test_db):
    """Ensures paused items and too-close departures (< min_days_to_dep) never fire noisy alerts."""
    today = date.today()
    now_dt = datetime.now(timezone.utc)

    async with setup_test_db() as db:
        hotel = Hotel(
            hotel_id="fh_wl_hotel",
            display_name="Anti Noise Villas",
            country="Egypt",
            region="Hurghada",
            stars=5,
        )
        db.add(hotel)
        await db.flush()

        # 1. Too close departure (2 days ahead), user wants min 7 days lead time
        dep_soon = today + timedelta(days=2)
        c_soon = OfferCohort(
            cohort_hash=compute_cohort_hash("fh_wl_hotel", dep_soon, 7, "WAW", adults=2),
            hotel_id="fh_wl_hotel",
            destination_code="Egypt",
            checkin_date=dep_soon,
            duration_nights=7,
            airport_code="WAW",
        )
        # 2. Future departure (15 days ahead), active, satisfies min 7 days & dropped 15%
        dep_future = today + timedelta(days=15)
        c_future = OfferCohort(
            cohort_hash=compute_cohort_hash("fh_wl_hotel", dep_future, 7, "KTW", adults=2),
            hotel_id="fh_wl_hotel",
            destination_code="Egypt",
            checkin_date=dep_future,
            duration_nights=7,
            airport_code="KTW",
        )
        # 3. Paused future item
        dep_paused = today + timedelta(days=20)
        c_paused = OfferCohort(
            cohort_hash=compute_cohort_hash("fh_wl_hotel", dep_paused, 7, "WRO", adults=2),
            hotel_id="fh_wl_hotel",
            destination_code="Egypt",
            checkin_date=dep_paused,
            duration_nights=7,
            airport_code="WRO",
        )
        db.add_all([c_soon, c_future, c_paused])
        await db.flush()

        db.add_all([
            PriceSnapshot(cohort_id=c_soon.cohort_id, recorded_at=now_dt - timedelta(hours=3), total_price_pln=7000.0, price_per_night_per_pax=500.0),
            PriceSnapshot(cohort_id=c_soon.cohort_id, recorded_at=now_dt, total_price_pln=5500.0, price_per_night_per_pax=392.0),

            PriceSnapshot(cohort_id=c_future.cohort_id, recorded_at=now_dt - timedelta(hours=3), total_price_pln=8000.0, price_per_night_per_pax=571.0),
            PriceSnapshot(cohort_id=c_future.cohort_id, recorded_at=now_dt, total_price_pln=6400.0, price_per_night_per_pax=457.0),

            PriceSnapshot(cohort_id=c_paused.cohort_id, recorded_at=now_dt - timedelta(hours=3), total_price_pln=9000.0, price_per_night_per_pax=642.0),
            PriceSnapshot(cohort_id=c_paused.cohort_id, recorded_at=now_dt, total_price_pln=6000.0, price_per_night_per_pax=428.0),
        ])

        w_soon = WatchlistItem(
            watch_id=uuid.uuid4().hex[:32],
            user_chat_id="chat_fh_1",
            cohort_hash=c_soon.cohort_hash,
            alert_threshold_pct=5.0,
            min_days_to_dep=7,
            is_active=True,
        )
        w_future = WatchlistItem(
            watch_id=uuid.uuid4().hex[:32],
            user_chat_id="chat_fh_1",
            cohort_hash=c_future.cohort_hash,
            alert_threshold_pct=10.0,
            min_days_to_dep=7,
            is_active=True,
        )
        w_paused = WatchlistItem(
            watch_id=uuid.uuid4().hex[:32],
            user_chat_id="chat_fh_1",
            cohort_hash=c_paused.cohort_hash,
            alert_threshold_pct=5.0,
            min_days_to_dep=0,
            is_active=False,
        )
        db.add_all([w_soon, w_future, w_paused])
        await db.commit()

        alerts = await WatchlistService.check_watchlist_triggers(db)
        triggered_ids = {a.watch_id for a in alerts}
        assert w_soon.watch_id not in triggered_ids
        assert w_paused.watch_id not in triggered_ids
        assert w_future.watch_id in triggered_ids


@pytest.mark.asyncio
async def test_dashboard_subscription_future_hunter_flags(setup_test_db):
    """Verifies min_days_to_dep, only_cheaper_than_std, whitelist_only persist via monitor alerts API."""
    email = f"fh_{uuid.uuid4().hex[:6]}@example.com"
    user = User(
        id=uuid.uuid4().hex,
        email=email,
        hashed_password=get_password_hash("Password123!"),
        full_name="Hunter",
        telegram_chat_id="555111222",
        telegram_notifications_enabled=True,
        is_active=True,
    )
    async with setup_test_db() as db:
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res_put = await ac.put(
            "/api/v2/monitors/alerts/turkey_7_10",
            json={
                "is_active": True,
                "notify_mode": "INSTANT",
                "min_drop_pct": 10.0,
                "min_deal_score": 80,
                "only_historic_low": False,
                "min_days_to_dep": 5,
                "only_cheaper_than_std": True,
                "whitelist_only": True,
                "monitor_title": "Turkey Hunt",
            },
            headers=headers,
        )
        assert res_put.status_code == 200
        saved = res_put.json()
        assert saved["min_days_to_dep"] == 5
        assert saved["only_cheaper_than_std"] is True
        assert saved["whitelist_only"] is True

        res_get = await ac.get("/api/v2/monitors/alerts/turkey_7_10", headers=headers)
        assert res_get.status_code == 200
        fetched = res_get.json()
        assert fetched["min_days_to_dep"] == 5
        assert fetched["only_cheaper_than_std"] is True
        assert fetched["whitelist_only"] is True
