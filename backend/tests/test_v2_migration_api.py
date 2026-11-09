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
