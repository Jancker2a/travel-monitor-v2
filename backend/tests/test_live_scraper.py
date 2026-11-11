import pytest
from datetime import date
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
from app.schemas.search import SearchRequest, SearchDates, SearchDuration, SearchTravelers
from app.services.live_scraper import (
    LiveScraperService,
    slugify,
    parse_departure_date,
    parse_duration_nights,
)

SAMPLE_HTML = """
<div class="card-offer-search" data-priceperall="4 250 zł" data-operator="CORAL">
    <h2 property="schema:name">Pickalbatros Aqua Blu Resort</h2>
    <div rel="schema:image" resource="https://fly.pl/images/albatros.jpg"></div>
    <div property="schema:url" content="/wycieczka/egipt/hurghada/pickalbatros-aqua-blu/12345"></div>
    <div class="stars-5" data-stars="5"></div>
    <div class="airport-info">Warszawa (WAW)</div>
    <div class="offer-dates">15.11.2026 - 22.11.2026 (8 dni / 7 nocy)</div>
    <img src="https://www.tripadvisor.com/img/cdsi/img2/ratings/traveler/4.5-37146-5.svg" />
    <span class="board-badge">All Inclusive</span>
</div>
<div class="card-offer-search" data-priceperall="3 190 zł" data-operator="ITAKA">
    <h2 property="schema:name">Jaz Aquaviva</h2>
    <div rel="schema:image" resource="https://fly.pl/images/aquaviva.jpg"></div>
    <div property="schema:url" content="/wycieczka/egipt/hurghada/jaz-aquaviva/67890"></div>
    <div class="stars-5" data-stars="5"></div>
    <div class="airport-info">Katowice (KTW)</div>
    <div class="offer-dates">16.11.2026 - 23.11.2026 (8 dni / 7 nocy)</div>
    <span class="bubble_40"></span>
    <span class="board-badge">All Inclusive</span>
</div>
"""


def test_slugify():
    assert slugify("Pickalbatros Aqua Blu Resort & Spa") == "pickalbatros-aqua-blu-resort-spa"
    assert slugify("Hotel 123 (ex. Sunrise)") == "hotel-123-ex-sunrise"


def test_parse_departure_date():
    d1, d2 = parse_departure_date("15.11.2026 - 22.11.2026")
    assert d1 == date(2026, 11, 15)
    assert d2 == date(2026, 11, 22)

    # Inverted MM.DD format
    d1, d2 = parse_departure_date("12.26.2026 - 04.01.2027")
    assert d1 == date(2026, 12, 26)
    assert d2 == date(2027, 1, 4)


def test_parse_duration_nights():
    assert parse_duration_nights("8 dni") == 7
    assert parse_duration_nights("7 nocy") == 7
    assert parse_duration_nights("10") == 10


def test_parse_offers_html():
    offers = LiveScraperService.parse_offers_html(SAMPLE_HTML)
    assert len(offers) == 2

    first = offers[0]
    assert first["hotel_name"] == "Pickalbatros Aqua Blu Resort"
    assert first["price"] == 4250.0
    assert first["checkin_date"] == date(2026, 11, 15)
    assert first["duration_nights"] == 7
    assert first["stars"] == 5
    assert first["ta_rating"] == 4.5
    assert first["main_image_url"] == "https://fly.pl/images/albatros.jpg"
    assert "12345" in first["offer_url"]

    second = offers[1]
    assert second["hotel_name"] == "Jaz Aquaviva"
    assert second["price"] == 3190.0
    assert second["ta_rating"] == 4.0


@pytest.mark.asyncio
async def test_process_and_persist_offers():
    # Setup clean in-memory async SQLite
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        req = SearchRequest(
            destination="egypt",
            dates=SearchDates(
                start_date_min=date(2026, 11, 15),
                start_date_max=date(2026, 11, 25),
            ),
            duration=SearchDuration(min_nights=7, max_nights=10),
            travelers=SearchTravelers(adults=2, children=0),
        )

        offers = LiveScraperService.parse_offers_html(SAMPLE_HTML)
        results = await LiveScraperService.process_and_persist_offers(session, req, offers)

        assert len(results) == 2
        item = results[0]
        assert item.hotel_name == "Pickalbatros Aqua Blu Resort"
        assert item.current_offer.total_price_pln == 4250.0
        assert item.current_offer.price_per_night_pax == round(4250.0 / (7 * 2), 2)
        assert item.intelligence.deal_badge in ["SUPER_DEAL", "GOOD_DEAL", "FAIR_PRICE"]
        assert len(item.history_sparkline) >= 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_fetch_offers_children_and_catering_mapping():
    # Verify that childrenAges and catering are converted to Fly.pl API array formats
    from unittest.mock import patch, MagicMock
    import httpx

    target_url = (
        "https://fly.pl/szukaj-wycieczek/?destinationLocation=11%3A&adults=2"
        "&startDateMin=20-12-2026&startDateMax=31-12-2026"
        "&children=1&childrenAges=6&catering=all_inclusive"
    )

    captured_params = {}

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            nonlocal captured_params
            captured_params = dict(params or {})
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"status": "OK", "data": {"offers": []}}
            return resp

    with patch("httpx.AsyncClient", MockAsyncClient):
        await LiveScraperService.fetch_offers_via_api(target_url, max_offers=10)

    assert "children[0]" in captured_params
    # Child birthdate should be in ISO format YYYY-MM-DD
    assert len(captured_params["children[0]"]) == 10
    assert captured_params["children[0]"].startswith("2020-")
    assert captured_params.get("catering[0]") == "all_inclusive"
    assert captured_params.get("destinationLocation[0]") == "11"


