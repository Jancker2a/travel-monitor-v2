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


@pytest.mark.asyncio
async def test_catalog_cache_invalidates_on_newer_snapshot_and_filters_stale_ghosts(setup_test_db):
    from datetime import date, datetime, timedelta, timezone
    from app.models.hotel import Hotel
    from app.models.cohort import OfferCohort
    from app.models.price_snapshot import PriceSnapshot
    from app.services.catalog_service import CatalogService, _CATALOG_CACHE

    _CATALOG_CACHE.clear()
    session_factory = setup_test_db
    fid = "test_cache_sync_filter"
    now = datetime.now(timezone.utc)
    dep = date.today() + timedelta(days=2)

    async with session_factory() as db:
        # 5 current hotels from latest scrape (now - 10m) + 1 ghost hotel from 4 hours ago
        for idx in range(6):
            hid = f"test-cache-hotel-{idx}"
            db.add(Hotel(hotel_id=hid, display_name=f"Cache Hotel {idx}", country="Египет", stars=5))
            await db.flush()
            c = OfferCohort(
                cohort_hash=f"cache_coh_{idx}",
                filter_id=fid,
                hotel_id=hid,
                destination_code="egypt",
                checkin_date=dep,
                checkout_date=dep + timedelta(days=7),
                duration_nights=7,
                airport_code="WAW",
                board_basis="All Inclusive",
                adults=2,
                children=1,
            )
            db.add(c)
            await db.flush()
            rec_time = (now - timedelta(hours=4)) if idx == 5 else (now - timedelta(minutes=10))
            db.add(PriceSnapshot(
                cohort_id=c.cohort_id,
                filter_id=fid,
                total_price_pln=5000.0 + idx * 100,
                price_per_night_per_pax=250.0,
                recorded_at=rec_time,
            ))
        await db.commit()

        first = await CatalogService.get_filter_hotels(db, fid, max_price=0)
        # Ghost from 4h ago must NOT inflate the live batch of 5 hotels
        assert first["total_hotels"] == 5
        assert "test-cache-hotel-5" not in {h["hotel_id"] for h in first["hotels"]}

        # Now insert a newer snapshot (simulating cron completing on another process)
        latest_c = OfferCohort(
            cohort_hash="cache_coh_latest",
            filter_id=fid,
            hotel_id="test-cache-hotel-0",
            destination_code="egypt",
            checkin_date=dep,
            checkout_date=dep + timedelta(days=7),
            duration_nights=7,
            airport_code="WAW",
            board_basis="All Inclusive",
            adults=2,
            children=1,
        )
        db.add(latest_c)
        await db.flush()
        newer_ts = now - timedelta(minutes=1)
        db.add(PriceSnapshot(
            cohort_id=latest_c.cohort_id,
            filter_id=fid,
            total_price_pln=4800.0,
            price_per_night_per_pax=240.0,
            recorded_at=newer_ts,
        ))
        await db.commit()

        second = await CatalogService.get_filter_hotels(db, fid, max_price=0)
        assert second["last_updated_at"] != first["last_updated_at"]
        h0 = next(h for h in second["hotels"] if h["hotel_id"] == "test-cache-hotel-0")
        assert h0["current_min_price"] == 4800.0



