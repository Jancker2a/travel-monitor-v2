import unittest
from datetime import date
from app.schemas.search import SearchRequest, SearchDates, SearchDuration, SearchTravelers
from app.services.query_builder import UniversalQueryBuilder
from app.models.cohort import compute_cohort_hash


class TestUniversalQueryBuilder(unittest.TestCase):
    def test_build_flypl_url_standard(self):
        req = SearchRequest(
            destination="egypt_sharm",
            dates=SearchDates(
                start_date_min=date(2026, 12, 20),
                start_date_max=date(2026, 12, 28),
            ),
            duration=SearchDuration(min_nights=7, max_nights=10),
            travelers=SearchTravelers(adults=2, children=1, children_ages=[7]),
            airports=["WAW", "KTW"],
            price_max_pln=9500,
        )
        url = UniversalQueryBuilder.build_flypl_url(req)
        self.assertIn("destinationLocation=11_154", url)
        self.assertIn("departureLocation=Warszawa%2CKatowice", url)
        self.assertIn("startDateMin=20-12-2026", url)
        self.assertIn("adults=2", url)
        self.assertIn("children=1", url)
        self.assertIn("childrenAges=7", url)
        self.assertIn("priceTo=9500", url)

    def test_cohort_hash_determinism(self):
        h1 = compute_cohort_hash(
            hotel_id="pickalbatros-aqua-park",
            checkin_date=date(2026, 12, 20),
            duration_nights=7,
            airport_code="WAW",
            adults=2,
            board_basis="All Inclusive",
        )
        h2 = compute_cohort_hash(
            hotel_id="PICKALBATROS-AQUA-PARK",
            checkin_date=date(2026, 12, 20),
            duration_nights=7,
            airport_code="waw",
            adults=2,
            board_basis="all inclusive",
        )
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 32)

    def test_build_flypl_url_full_flypl_parity(self):
        req = SearchRequest(
            destination="turkey",
            region="turkey_antalya",
            dates=SearchDates(
                start_date_min=date(2026, 12, 1),
                start_date_max=date(2026, 12, 8),
            ),
            duration=SearchDuration(min_nights=7, max_nights=8),
            travelers=SearchTravelers(adults=1, children=0),
            airports=["WAW", "KTW", "BER"],
            catering="all_inclusive",
            stars_min=4,
            price_min_pln=1000,
            price_max_pln=8000,
            order_by="price",
        )
        url = UniversalQueryBuilder.build_flypl_url(req)
        self.assertIn("destinationLocation=39_3", url)
        self.assertIn("departureLocation=Warszawa%2CKatowice%2CBerlin", url)
        self.assertIn("startDateMin=01-12-2026", url)
        self.assertIn("startDateMax=08-12-2026", url)
        self.assertIn("adults=1", url)
        self.assertIn("catering=all_inclusive", url)
        self.assertIn("categoryRating=40", url)
        self.assertIn("priceFrom=1000", url)
        self.assertIn("priceTo=8000", url)
        self.assertIn("order=price", url)



if __name__ == "__main__":
    unittest.main()

