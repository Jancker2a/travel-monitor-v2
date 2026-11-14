import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import Base
from app.models.user import User
from app.core.security import get_password_hash, create_access_token


@pytest.mark.asyncio
async def test_dashboard_alert_subscription_flow(setup_test_db):
    """Verifies get, update, and test alert flow for any monitor/dashboard."""
    email = f"dash_{uuid.uuid4().hex[:6]}@example.com"
    pwd = "Password123!"
    hashed = get_password_hash(pwd)

    user = User(
        id=uuid.uuid4().hex,
        email=email,
        hashed_password=hashed,
        full_name="Dashboard Tester",
        telegram_chat_id="123456789",
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
        # 1. Get default subscription for turkey_7_10
        res = await ac.get("/api/v2/monitors/alerts/turkey_7_10?title=Турция+7-10", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["monitor_id"] == "turkey_7_10"
        assert data["is_active"] is False

        # 2. Save custom alert settings for this monitor
        put_payload = {
            "is_active": True,
            "notify_mode": "INSTANT",
            "min_drop_pct": 12.5,
            "min_drop_pln": 500.0,
            "min_deal_score": 85,
            "max_budget_pln": 6500.0,
            "only_historic_low": True,
            "min_ta_rating": 4.5,
            "preferred_airports": "WAW,KTW",
            "monitor_title": "Турция 7-10 дней (2 взр + 1 реб)",
        }
        res_put = await ac.put("/api/v2/monitors/alerts/turkey_7_10", json=put_payload, headers=headers)
        assert res_put.status_code == 200
        saved = res_put.json()
        assert saved["is_active"] is True
        assert saved["min_drop_pct"] == 12.5
        assert saved["min_drop_pln"] == 500.0
        assert saved["min_deal_score"] == 85
        assert saved["max_budget_pln"] == 6500.0
        assert saved["only_historic_low"] is True
        assert saved["preferred_airports"] == "WAW,KTW"

        # 3. List all subscriptions
        res_list = await ac.get("/api/v2/monitors/alerts", headers=headers)
        assert res_list.status_code == 200
        subs = res_list.json()
        assert len(subs) >= 1
        assert any(s["monitor_id"] == "turkey_7_10" for s in subs)

        # 4. Test monitor alert
        res_test = await ac.post("/api/v2/monitors/alerts/turkey_7_10/test?title=Турция+7-10", headers=headers)
        assert res_test.status_code == 200
        test_out = res_test.json()
        assert "success" in test_out


@pytest.mark.asyncio
async def test_daily_digest_preferences_and_test(setup_test_db):
    """Verifies update of daily digest preferences and dispatching test digest."""
    email = f"digest_{uuid.uuid4().hex[:6]}@example.com"
    pwd = "Password123!"
    hashed = get_password_hash(pwd)

    user = User(
        id=uuid.uuid4().hex,
        email=email,
        hashed_password=hashed,
        full_name="Digest Explorer",
        telegram_chat_id="99887766",
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
        # 1. Update digest preferences
        patch_payload = {
            "digest_enabled": True,
            "digest_time": "08:30",
            "digest_days": "WEEKDAYS",
            "digest_include_watchlist": True,
            "digest_include_top_drops": True,
            "digest_include_hot_deals": True,
            "digest_include_historic_lows": True,
            "digest_min_deal_score": 85,
            "digest_max_offers": 10,
            "digest_only_if_changes": True,
            "quiet_hours_enabled": True,
            "quiet_hours_start": 22,
            "quiet_hours_end": 7,
        }
        res_patch = await ac.patch("/api/v2/auth/me", json=patch_payload, headers=headers)
        assert res_patch.status_code == 200
        me = res_patch.json()
        assert me["digest_enabled"] is True
        assert me["digest_time"] == "08:30"
        assert me["digest_days"] == "WEEKDAYS"
        assert me["digest_min_deal_score"] == 85
        assert me["digest_max_offers"] == 10
        assert me["quiet_hours_start"] == 22

        # 2. Send test daily digest
        res_test = await ac.post("/api/v2/auth/test-digest", headers=headers)
        assert res_test.status_code == 200
        digest_out = res_test.json()
        assert digest_out["success"] is True

