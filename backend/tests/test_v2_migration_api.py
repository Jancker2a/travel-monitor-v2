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
        # Test Egypt
        response = await ac.get("/api/v2/filters/egypt_7_10/departures")
        assert response.status_code == 200
        data = response.json()
        assert data["filter_id"] == "egypt_7_10"
        assert len(data["hot_history"]) == 99
        assert len(data["active_departures"]) > 0
        assert "Египет" in data["hot_history"][0]["departure"]

        # Test Turkey
        response_tr = await ac.get("/api/v2/filters/turkey_7_10/departures")
        assert response_tr.status_code == 200
        data_tr = response_tr.json()
        assert data_tr["filter_id"] == "turkey_7_10"
        assert len(data_tr["hot_history"]) == 208
        assert "Турция" in data_tr["hot_history"][0]["departure"]


