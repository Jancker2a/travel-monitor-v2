import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.hotel import Hotel
from app.models.cohort import OfferCohort
from app.models.price_snapshot import PriceSnapshot
from app.models.watchlist import WatchlistItem
from app.services.auth_service import AuthService
import uuid
from datetime import datetime, date


@pytest.mark.asyncio
async def test_update_watchlist_thresholds(setup_test_db):
    uid = uuid.uuid4().hex[:8]
    hotel_id = f"test_wl_hotel_{uid}"
    cohort_hash = f"c_hash_test_wl_{uid}"
    watch_id = f"w_test_item_{uid}"
    user_chat_id = f"user_test_chat_{uid}"

    async with setup_test_db() as session:
        # Create test hotel, cohort and watchlist item
        hotel = Hotel(
            hotel_id=hotel_id,
            display_name=f"Test Watchlist Hotel {uid}",
            country="Egypt",
            stars=5,
        )
        cohort = OfferCohort(
            cohort_hash=cohort_hash,
            hotel_id=hotel_id,
            destination_code="EG",
            checkin_date=date(2026, 12, 1),
            duration_nights=7,
            airport_code="WAW",
        )
        session.add(hotel)
        session.add(cohort)
        await session.flush()

        snap = PriceSnapshot(
            cohort_id=cohort.cohort_id,
            total_price_pln=5000.0,
            price_per_night_per_pax=350.0,
        )
        session.add(snap)

        item = WatchlistItem(
            watch_id=watch_id,
            user_chat_id=user_chat_id,
            cohort_hash=cohort_hash,
            target_price_pln=4500.0,
            alert_threshold_pct=5.0,
            min_deal_score=80,
            is_active=True,
        )
        session.add(item)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Update thresholds via PATCH
        patch_payload = {
            "target_price_pln": 4200.0,
            "alert_threshold_pct": 10.0,
            "min_deal_score": 85,
            "is_active": False,
        }
        resp = await client.patch(f"/api/v2/watchlist/{watch_id}", json=patch_payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["target_price_pln"] == 4200.0
        assert data["alert_threshold_pct"] == 10.0
        assert data["min_deal_score"] == 85
        assert data["is_active"] is False

        # 2. Get watchlist and verify fields are returned
        get_resp = await client.get(f"/api/v2/watchlist/{user_chat_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        found = next((i for i in get_data["items"] if i["watch_id"] == watch_id), None)
        assert found is not None
        assert found["target_price_pln"] == 4200.0
        assert found["alert_threshold_pct"] == 10.0
        assert found["is_active"] is False


@pytest.mark.asyncio
async def test_user_telegram_profile_and_test_notification():
    test_email = f"telegram_tester_{uuid.uuid4().hex[:6]}@travel.com"
    # Register/login user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg_resp = await client.post(
            "/api/v2/auth/register",
            json={
                "email": test_email,
                "password": "Password123!",
                "full_name": "Telegram Explorer",
                "telegram_chat_id": "999888777",
            },
        )
        assert reg_resp.status_code == 201, reg_resp.text
        token = reg_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Verify /me has telegram info
        me_resp = await client.get("/api/v2/auth/me", headers=headers)
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["telegram_chat_id"] == "999888777"
        assert me_data["telegram_notifications_enabled"] is True

        # Update Telegram settings via PATCH /me
        update_resp = await client.patch(
            "/api/v2/auth/me",
            headers=headers,
            json={
                "telegram_chat_id": "123456789",
                "telegram_notifications_enabled": False,
                "full_name": "Andrzej New",
            },
        )
        assert update_resp.status_code == 200
        up_data = update_resp.json()
        assert up_data["telegram_chat_id"] == "123456789"
        assert up_data["telegram_notifications_enabled"] is False
        assert up_data["full_name"] == "Andrzej New"

        # Test Telegram notification endpoint
        test_tg_resp = await client.post(
            "/api/v2/auth/test-telegram",
            headers=headers,
            json={"chat_id": "123456789"},
        )
        assert test_tg_resp.status_code == 200
        tg_res_data = test_tg_resp.json()
        assert tg_res_data["success"] is True
        assert tg_res_data["chat_id"] == "123456789"
