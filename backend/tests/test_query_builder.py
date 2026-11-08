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
        self.assertIn("destinationLocation=1%3A1", url)
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


if __name__ == "__main__":
    unittest.main()

