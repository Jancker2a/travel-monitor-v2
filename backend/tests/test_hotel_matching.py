import pytest

from app.services.hotel_entity_matcher import HotelEntityMatcher, calculate_hotel_similarity
from app.services.hotel_knowledge_service import HotelKnowledgeService


@pytest.mark.parametrize(
    "name_pl,name_de",
    [
        ("SRNTY Sun Ray X Serenity Alma Heights", "SRNTY Sun Ray"),
        ("SRNTY Sea Reef X Serenity Alpha Beach", "SRNTY Sea Reef"),
        ("Srnty Sea Reef (Ex. Serenity Alpha Beach", "SRNTY Sea Reef"),
        ("Srnty Sahl Hasheesh (Ex. Serenity Sky Ar", "SRNTY Sahl Hasheesh"),
        ("Barcelo Tiran Sharm", "Barceló Tiran Sharm"),
        ("Charmillion Gardens Aqua Park", "Charmillion Gardens Aquapark"),
        ("Gravity Hotel & Aquapark Hurghada (ex. Samra Bay Resort)", "Gravity Hotel & Aqua Park Hurghada"),
        ("Gravity Hotel and Aqua Park (ex. Samra B", "Gravity Hotel & Aqua Park Hurghada"),
        ("Iberotel Makadi Beach", "Iberotel Makadi Beach by JAZ"),
        ("Jaz Elite Palace (ex. Iberotel Palace)", "JAZ Elite Palace - Adults Only"),
        ("Pickalbatros Aqua Vista Resort", "Pickalbatros Aqua Vista Resort powered by Playitas"),
        ("Pickalbatros Citadel Sahl Hasheesh (ex. Citadel Azur Resort)", "Pickalbatros Citadel Resort"),
        ("Rixos Sharm el Sheikh", "Rixos Sharm El Sheikh Adults Only 18+"),
        ("Seagull Beach Resort (Hurghada)", "Sea Gull Beach Resort"),
        ("Steigenberger Al Dau Beach", "Steigenberger ALDAU Beach Hotel"),
        ("Titanic Beach Spa & Aqua Park", "Titanic Beach"),
        ("IC Green Palace", "IC Hotels Green Palace & Villas"),
        ("Limak Lara", "Limak Lara Deluxe Hotel & Resort"),
        ("Ramada Resort Lara", "Ramada Resort by Wyndham Lara"),
        ("Rixos Downtown (Antalya)", "Rixos Downtown Antalya - The Land of Legends Access"),
        ("Grecotel LuxMe The White (ex.Grecotel El Greco)", "Grecotel LUX®ME White"),
        ("ananea Rocrita Lifestyle Beach Resort (ex. Aldiana Kreta)", "ananea Rocrita"),
        ("Star Beach Village", "Star Beach Village & Waterpark"),
        ("Carolina Mare", "allsun Hotel Carolina Mare"),
    ],
)
def test_hotel_matcher_true_positives(name_pl: str, name_de: str):
    assert calculate_hotel_similarity(name_pl, name_de) >= 0.80


@pytest.mark.parametrize(
    "name_a,name_b",
    [
        ("PICKALBATROS AQUA PARK RESORT-SSH", "Pickalbatros Aqua Park Resort - Hurghada"),
        ("Mövenpick Waterpark Resort & Spa Soma Bay", "Mövenpick Resort & Spa El Gouna"),
        ("Sharm Grand Plaza", "Sharm Plaza Hotel"),
        ("Charmillion Club Resort", "Charmillion Club Aquapark"),
        ("ROYAL OLYMPIC HOTEL", "Olympic Star"),
        ("Fame Residence (Göynük)", "Fame Residence Lara & Spa"),
        ("Liberty Kusadasi (ex. Seven Seas Sealight Elite)", "Liberty Lara"),
        ("Long Beach (Avsallar)", "Long Beach Resort Hurghada"),
        ("Orange County (Kemer)", "Orange County Belek"),
        ("SWISS INN RESORT HURGHADA", "Swiss Inn Resort Dahab"),
        ("The Grand Hotel Sharm El Sheikh", "THE GRAND RESORT"),
        ("THE GRAND RESORT", "GRAND MAKADI"),
        ("Ramada Plaza By Wyndham Antalya", "Ramada Resort by Wyndham Lara"),
        ("Fort Arabesque - The West Bay", "Fort Arabesque - The Beach Resort"),
        ("Sunrise Royal Makadi Resort", "Sunrise Crystal Bay Resort"),
        ("Rixos Downtown Antalya - The Land of Legends Access", "Rixos Premium Belek - The Land of Legends Access"),
        ("Sunrise Holidays Resort", "SUNRISE Makadi Boutique Resort"),
        ("Gravity Sahl Hasheesh", "Gravity Hotel & Aqua Park Hurghada"),
        ("Apollo (Georgioupolis)", "Apollo Plakias"),
        ("Kakkos Beach", "Kakkos Bay"),
        ("Asterias Bay (Theologos)", "Asterias Village Resort"),
        ("Atlantis (Lambi)", "Atlantis Beach Hotel & Spa"),
        ("Giannoulis Santa Marina Beach Pearl", "Giannoulis Santa Marina Beach"),
        ("Otium Amphoras (ex Shores)", "Amphoras Blu"),
        ("Pickalbatros Blu Spa Resort Hurghada", "Pickalbatros Aqua Blu Resort - Hurghada"),
    ],
)
def test_hotel_matcher_zero_false_positives(name_a: str, name_b: str):
    matcher = HotelEntityMatcher(similarity_threshold=0.80)
    assert matcher.match_hotel(name_a, [name_b]) is None


def test_transitive_rename_resolution_and_knowledge_lookup():
    matcher = HotelEntityMatcher(similarity_threshold=0.80)

    # Serenity Alma Heights <-> SRNTY Sun Ray <-> Serenity Fun City
    variants = matcher.get_alias_variants("SRNTY Sun Ray X Serenity Alma Heights", country="Египет")
    joined = " | ".join(variants).lower()
    assert "srnty sun ray" in joined
    assert "serenity alma heights" in joined

    # Rebranded Check24 match against either historical or new name
    res = matcher.match_hotel(
        "SRNTY Sun Ray X Serenity Alma Heights",
        ["Serenity Alma Heights"],
        destination="Египет",
    )
    assert res is not None and res[0] == "Serenity Alma Heights" and res[1] >= 0.90

    # Knowledge service must resolve renamed hotel to legacy KB record
    mock_kb = {
        "Serenity Alma Heights (ex. Serenity Fun City)": {"ta_rating": 4.6},
        "Charmillion Club Aquapark": {"ta_rating": 4.2},
    }
    found = HotelKnowledgeService._match_entry("SRNTY Sun Ray X Serenity Alma Heights", mock_kb)
    assert found == {"ta_rating": 4.6}
    # Must NOT leak Charmillion Club Aquapark onto Charmillion Club Resort
    assert HotelKnowledgeService._match_entry("Charmillion Club Resort", mock_kb) is None


@pytest.mark.asyncio
async def test_live_scraper_deduplicates_renamed_operator_offers_keeping_cheapest(setup_test_db):
    from datetime import date, timedelta
    from sqlalchemy import select
    from app.models.cohort import OfferCohort
    from app.models.hotel import Hotel
    from app.models.price_snapshot import PriceSnapshot
    from app.schemas.search import SearchDates, SearchDuration, SearchRequest, SearchTravelers
    from app.services.live_scraper import LiveScraperService

    async with setup_test_db() as db:
        dep = date.today() + timedelta(days=10)
        ret = dep + timedelta(days=7)
        req = SearchRequest(
            destination="egypt",
            filter_id="egypt_7_10",
            dates=SearchDates(start_date_min=dep, start_date_max=dep + timedelta(days=3)),
            duration=SearchDuration(min_nights=7, max_nights=10),
            travelers=SearchTravelers(adults=2, children=1),
        )
        raw_offers = [
            {
                "hotel_name": "Serenity Alma Heights Ross Park Collection",
                "price": 7200.0,
                "checkin_date": dep,
                "checkout_date": ret,
                "duration_nights": 7,
                "departure_airport": "WAW",
                "stars": 5,
                "ta_rating": 4.5,
                "main_image_url": "",
                "offer_url": "https://fly.pl/wycieczka/egipt,hurghada,makadi-bay/serenity-fun-city/p1?operator=OREX",
                "operator": "OREX",
                "board_basis": "All Inclusive",
            },
            {
                "hotel_name": "SRNTY Sun Ray X Serenity Alma Heights",
                "price": 6450.0,
                "checkin_date": dep,
                "checkout_date": ret,
                "duration_nights": 7,
                "departure_airport": "WAW",
                "stars": 5,
                "ta_rating": 4.5,
                "main_image_url": "",
                "offer_url": "https://fly.pl/wycieczka/egipt,hurghada,makadi-bay/serenity-fun-city/p2?operator=EXIM",
                "operator": "EXIM",
                "board_basis": "All Inclusive",
            },
        ]

        items = await LiveScraperService.process_and_persist_offers(db, req, raw_offers)
        # Same hotel under two operator renamings MUST collapse to 1 item with the cheapest price (6450 PLN)
        assert len(items) == 1
        assert items[0].current_offer.total_price_pln == 6450.0
        assert items[0].current_offer.operator == "EXIM"
        assert "p2" in (items[0].current_offer.booking_url or "")

        hotels = (await db.execute(select(Hotel))).scalars().all()
        assert len(hotels) == 1
        cohorts = (await db.execute(select(OfferCohort))).scalars().all()
        assert len(cohorts) == 1
        assert cohorts[0].operator == "EXIM"
        snaps = (await db.execute(select(PriceSnapshot))).scalars().all()
        assert len(snaps) == 1
        assert snaps[0].total_price_pln == 6450.0
