import unittest
from app.services.cost_decomposer import CostDecomposer


class TestCostDecomposer(unittest.TestCase):
    def test_duration_weighting_7_vs_14_nights(self):
        # Case A: 7 nights for 2 adults in Turkey at 6,000 PLN
        # Flight is 2 * 1300 = 2600 PLN (43.3% of total)
        # Hotel is 3400 PLN / 7 nights / 2 pax = 242.86 PLN/night/adult
        dec_7 = CostDecomposer.decompose(
            total_price_pln=6000.0,
            duration_nights=7,
            adults=2,
            children=0,
            destination="turkey",
        )
        self.assertEqual(dec_7["flight_seat_cost"], 1300.0)
        self.assertEqual(dec_7["estimated_flight_total"], 2600.0)
        self.assertEqual(dec_7["estimated_hotel_total"], 3400.0)
        self.assertEqual(dec_7["flight_weight_pct"], 43.3)
        self.assertAlmostEqual(dec_7["pure_hotel_night_per_adult"], 242.86, places=1)

        # Case B: 14 nights for 2 adults in same hotel at 9,400 PLN
        # Flight remains 2600 PLN, but now only 27.7% of total!
        # Hotel is 6800 PLN / 14 nights / 2 pax = 242.86 PLN/night/adult!
        dec_14 = CostDecomposer.decompose(
            total_price_pln=9400.0,
            duration_nights=14,
            adults=2,
            children=0,
            destination="turkey",
        )
        self.assertEqual(dec_14["estimated_flight_total"], 2600.0)
        self.assertEqual(dec_14["flight_weight_pct"], 27.7)
        # Both durations yield the EXACT same pure daily hotel rate!
        self.assertAlmostEqual(dec_7["pure_hotel_night_per_adult"], dec_14["pure_hotel_night_per_adult"], places=1)

    def test_child_discount_weighting_2_plus_1(self):
        # Family with 1 child (2+1): 3 flight seats = 3900 PLN
        # Total package: 7,500 PLN (7 nights)
        dec_family = CostDecomposer.decompose(
            total_price_pln=7500.0,
            duration_nights=7,
            adults=2,
            children=1,
            destination="turkey",
        )
        self.assertEqual(dec_family["estimated_flight_total"], 3900.0)
        self.assertEqual(dec_family["estimated_hotel_total"], 3600.0)
        # Hotel daily cost for room
        self.assertAlmostEqual(dec_family["daily_hotel_room_cost"], 514.29, places=1)

    def test_benchmark_comparison(self):
        dec_custom = CostDecomposer.decompose(
            total_price_pln=7000.0,
            duration_nights=10,
            adults=2,
            children=0,
            destination="turkey",
        )
        # Benchmark trunk pure rate: 250 PLN/night/adult
        comp = CostDecomposer.compare_to_standard_benchmark(dec_custom, trunk_median_pure_rate=250.0)
        self.assertIn("diff_pct", comp)
        self.assertIn("status", comp)
        self.assertIn("explanation", comp)

