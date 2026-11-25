import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_top10_timeline_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v2/filters/7_10_days/top10-timeline?range=30d")
        assert response.status_code == 200
        data = response.json()
        assert data["filter_id"] == "7_10_days"
        assert "points_count" in data
        assert "timeline" in data
        assert "stats" in data


@pytest.mark.asyncio
async def test_hotels_catalog_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v2/filters/7_10_days/hotels?sort_by=price")
        assert response.status_code == 200
        data = response.json()
        assert data["filter_id"] == "7_10_days"
        assert "total_hotels" in data
        assert isinstance(data["hotels"], list)


@pytest.mark.asyncio
async def test_market_oracle_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v2/filters/7_10_days/oracle")
        assert response.status_code == 200
        data = response.json()
        assert data["filter_id"] == "7_10_days"
        assert "headline" in data
        assert "strategic_directive" in data


@pytest.mark.asyncio
async def test_filter_departures_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v2/filters/egypt_7_10/departures")
        assert response.status_code == 200
        data = response.json()
        assert data["filter_id"] == "egypt_7_10"
        assert isinstance(data["active_departures"], list)
        assert isinstance(data["hot_history"], list)
        assert "stats" in data

        # Analytics endpoint
        resp_an = await ac.get("/api/v2/filters/7_10_days/analytics")
        assert resp_an.status_code == 200
        an_data = resp_an.json()
        assert an_data["filter_id"] == "7_10_days"
        assert an_data["filter_type"] in ("lastminute", "early_booking", "fixed_dates", "rolling")
        assert "overview" in an_data
        assert "calendar_dates" in an_data
        assert "price_changes" in an_data
        assert "timing_stats" in an_data

        # Arbitrage status endpoint
        resp_arb = await ac.get("/api/v2/arbitrage/status")
        assert resp_arb.status_code == 200
        arb_data = resp_arb.json()
        assert "total_offers" in arb_data
        assert "is_stale" in arb_data


