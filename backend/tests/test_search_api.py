import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from tests.test_live_scraper import SAMPLE_HTML


@pytest.mark.asyncio
async def test_search_api_endpoint(setup_test_db):
    # Mock live HTML fetch to return SAMPLE_HTML
    with patch(
        "app.services.live_scraper.LiveScraperService.fetch_page_html",
        return_value=SAMPLE_HTML,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v2/search",
                json={
                    "destination": "egypt",
                    "dates": {
                        "start_date_min": "2026-11-15",
                        "start_date_max": "2026-11-25",
                    },
                    "duration": {
                        "min_nights": 7,
                        "max_nights": 10,
                    },
                    "travelers": {
                        "adults": 2,
                        "children": 0,
                    },
                    "airports": ["WAW", "KTW"],
                    "force_live_refresh": True,
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["cached"] is False
            assert data["total_found"] == 2
            assert len(data["results"]) == 2

            hotel1 = data["results"][0]
            assert hotel1["hotel_name"] == "Pickalbatros Aqua Blu Resort"
            assert hotel1["stars"] == 5
            assert hotel1["current_offer"]["total_price_pln"] == 4250.0
            assert hotel1["intelligence"]["hopper_verdict"] in ["BUY NOW", "WAIT", "OVERPRICED"]
            assert isinstance(hotel1["history_sparkline"], list)
