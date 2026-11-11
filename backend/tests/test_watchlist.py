import pytest
from datetime import date, datetime
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.hotel import Hotel
from app.models.cohort import OfferCohort
from app.models.price_snapshot import PriceSnapshot
from app.schemas.watchlist import WatchlistCreateRequest
from app.services.watchlist_service import WatchlistService


@pytest.mark.asyncio
async def test_watchlist_service_crud(setup_test_db):
    session_factory = setup_test_db
    async with session_factory() as session:
        # 1. Seed Hotel & Cohort
        hotel = Hotel(
            hotel_id="hilton-sharm-waterfalls",
            display_name="Hilton Sharks Bay Resort",
            country="Египет",
            stars=5,
        )
        session.add(hotel)

        cohort = OfferCohort(
            cohort_hash="cohort_test_1234567890abcdef",
            hotel_id="hilton-sharm-waterfalls",
            destination_code="egypt_sharm",
            checkin_date=date(2026, 12, 20),
            duration_nights=7,
            airport_code="WAW",
            offer_url="https://fly.pl/wycieczka/hilton-sharm/123",
        )
        session.add(cohort)
        await session.flush()

        # Snapshots: previous high price, then drop
        snap1 = PriceSnapshot(
            cohort_id=cohort.cohort_id,
            recorded_at=datetime(2026, 11, 1, 10, 0),
            total_price_pln=5500.0,
            price_per_night_per_pax=392.8,
        )
        snap2 = PriceSnapshot(
            cohort_id=cohort.cohort_id,
            recorded_at=datetime(2026, 11, 2, 10, 0),
            total_price_pln=4800.0,
            price_per_night_per_pax=342.8,
        )
        session.add_all([snap1, snap2])
        await session.commit()

        # 2. Add to Watchlist
        req = WatchlistCreateRequest(
            cohort_hash="cohort_test_1234567890abcdef",
            user_chat_id="tg_123456",
            target_price_pln=5000.0,
            notify_any_drop=True,
        )
        created = await WatchlistService.add_to_watchlist(session, req)
        assert created.user_chat_id == "tg_123456"
        assert created.latest_price_pln == 4800.0
        assert created.target_reached is True

        # 3. List Watchlist
        watchlist_res = await WatchlistService.get_user_watchlist(session, "tg_123456")
        assert watchlist_res.total == 1
        assert watchlist_res.items[0].hotel_name == "Hilton Sharks Bay Resort"

        # 4. Check Alert Triggers
        alerts = await WatchlistService.check_watchlist_triggers(session)
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.drop_amount_pln == 700.0
        assert alert.current_price_pln == 4800.0
        assert alert.target_reached is True
        assert "Hilton Sharks Bay Resort" in alert.message_text

        # 5. Hotel Passport
        passport = await WatchlistService.get_hotel_passport(session, "hilton-sharm-waterfalls")
        assert passport.display_name == "Hilton Sharks Bay Resort"
        assert passport.all_time_min_pln == 4800.0
        assert passport.all_time_max_pln == 5500.0
        assert len(passport.history_points) == 2

        # 6. Delete Watchlist
        deleted = await WatchlistService.delete_watchlist_item(session, created.watch_id, "tg_123456")
        assert deleted is True

        after_delete = await WatchlistService.get_user_watchlist(session, "tg_123456")
        assert after_delete.total == 0


@pytest.mark.asyncio
async def test_watchlist_api_endpoints(setup_test_db):
    session_factory = setup_test_db
    async with session_factory() as session:
        # Seed test data
        hotel = Hotel(hotel_id="rixos-premium-belek", display_name="Rixos Premium Belek", country="Турция", stars=5)
        cohort = OfferCohort(
            cohort_hash="rixos_hash_9876543210fedcba",
            hotel_id="rixos-premium-belek",
            destination_code="turkey",
            checkin_date=date(2026, 7, 10),
            duration_nights=7,
            airport_code="WAW",
        )
        session.add_all([hotel, cohort])
        await session.flush()
        snap = PriceSnapshot(
            cohort_id=cohort.cohort_id,
            recorded_at=datetime.utcnow(),
            total_price_pln=12500.0,
            price_per_night_per_pax=892.8,
        )
        session.add(snap)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # POST /api/v2/watchlist
        create_resp = await client.post(
            "/api/v2/watchlist",
            json={
                "cohort_hash": "rixos_hash_9876543210fedcba",
                "user_chat_id": "tg_99999",
                "target_price_pln": 11000.0,
                "notify_any_drop": True,
            },
        )
        assert create_resp.status_code == 200
        w_data = create_resp.json()
        assert w_data["hotel_name"] == "Rixos Premium Belek"
        watch_id = w_data["watch_id"]

        # GET /api/v2/watchlist/{user_chat_id}
        list_resp = await client.get("/api/v2/watchlist/tg_99999")
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] == 1

        # GET /api/v2/hotels/{hotel_id}/history
        hist_resp = await client.get("/api/v2/hotels/rixos-premium-belek/history")
        assert hist_resp.status_code == 200
        assert hist_resp.json()["display_name"] == "Rixos Premium Belek"
        assert len(hist_resp.json()["history_points"]) == 1

        # DELETE /api/v2/watchlist/{watch_id}
        del_resp = await client.delete(f"/api/v2/watchlist/{watch_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "ok"

        # GET /api/v2/hotels/{hotel_id}/history for a completely unknown hotel (Must NOT 404!)
        unknown_resp = await client.get(
            "/api/v2/hotels/brand-new-secret-palace/history?name=Brand%20New%20Secret%20Palace&stars=5&country=Египет&current_price=4500"
        )
        assert unknown_resp.status_code == 200
        un_data = unknown_resp.json()
        assert un_data["display_name"] == "Brand New Secret Palace"
        assert un_data["stars"] == 5
        assert un_data["country"] == "Египет"
        assert un_data["current_price_pln"] == 4500.0
        assert len(un_data["history_points"]) >= 1
        assert un_data["youtube_search_url"] is not None

