import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger("travel_monitor_2.cost_decomposer")

# Typical roundtrip charter flight + transfer cost per seat by destination (PLN)
DESTINATION_FLIGHT_BENCHMARKS: Dict[str, float] = {
    "turkey": 1300.0,
    "egypt": 1400.0,
    "greece": 1200.0,
    "cyprus": 1100.0,
    "spain": 1150.0,
    "default": 1300.0,
}


class CostDecomposer:
    """Decomposed Tour Cost Model:
    Separates fixed flight/charter costs from variable per-night hotel costs,
    accounting for duration weighting and subsidized child hotel rates.
    
    P_total = P_flight_total + P_hotel_total
    where:
      P_flight_total = (adults + children) * flight_seat_cost
      P_hotel_total  = P_total - P_flight_total
      
    Child hotel rate factor (alpha):
      1st child: hotel is often free/subsidized (alpha ≈ 0.15 - 0.25)
      2nd child: discounted room upgrade (alpha ≈ 0.50)
    """

    @classmethod
    def get_flight_benchmark(cls, destination: str) -> float:
        dest_clean = destination.lower()
        for key, val in DESTINATION_FLIGHT_BENCHMARKS.items():
            if key in dest_clean:
                return val
        return DESTINATION_FLIGHT_BENCHMARKS["default"]

    @classmethod
    def decompose(
        cls,
        total_price_pln: float,
        duration_nights: int,
        adults: int = 2,
        children: int = 0,
        destination: str = "turkey",
    ) -> Dict[str, float]:
        nights = max(1, duration_nights)
        adults = max(1, adults)
        children = max(0, children)

        flight_seat_cost = cls.get_flight_benchmark(destination)
        
        # Flight seats: every person (adult & child > 2yo) occupies 1 seat
        total_pax = adults + children
        estimated_flight_total = total_pax * flight_seat_cost

        # Guard against edge-cases where total package is less than flight benchmark (e.g. extreme last-minute dumping)
        if estimated_flight_total >= total_price_pln * 0.75:
            # Flight cannot realistically exceed 75% of package; scale flight proportionally
            estimated_flight_total = round(total_price_pln * 0.50, 2)
            flight_seat_cost = round(estimated_flight_total / total_pax, 2)

        estimated_hotel_total = max(100.0, total_price_pln - estimated_flight_total)

        # Child hotel weight: 1st child is often 0-25% of adult hotel rate, 2nd child 50%
        effective_hotel_pax = float(adults)
        if children >= 1:
            effective_hotel_pax += 0.20  # 1st child pays mainly flight, hotel is near-free
        if children >= 2:
            effective_hotel_pax += 0.50 * (children - 1)

        # Pure daily hotel room rate & per-adult-equivalent per-night rate
        daily_hotel_room_cost = estimated_hotel_total / nights
        pure_hotel_night_per_adult = daily_hotel_room_cost / effective_hotel_pax

        # Weight of flight in overall package
        flight_weight_pct = (estimated_flight_total / total_price_pln) * 100

        return {
            "total_price_pln": total_price_pln,
            "duration_nights": nights,
            "flight_seat_cost": flight_seat_cost,
            "estimated_flight_total": round(estimated_flight_total, 2),
            "estimated_hotel_total": round(estimated_hotel_total, 2),
            "flight_weight_pct": round(flight_weight_pct, 1),
            "hotel_weight_pct": round(100.0 - flight_weight_pct, 1),
            "daily_hotel_room_cost": round(daily_hotel_room_cost, 2),
            "pure_hotel_night_per_adult": round(pure_hotel_night_per_adult, 2),
        }

    @classmethod
    def compare_to_standard_benchmark(
        cls,
        custom_offer: Dict[str, Any],
        trunk_median_pure_rate: float,
    ) -> Dict[str, Any]:
        """Compares a custom tour (e.g. 10 nights, 2+1) against trunk benchmark (7 nights, 2 adults)
        using the normalized pure hotel night rate.
        """
        curr_pure_rate = custom_offer.get("pure_hotel_night_per_adult", 0.0)
        if trunk_median_pure_rate <= 0 or curr_pure_rate <= 0:
            return {"diff_pct": 0.0, "status": "FAIR", "explanation": "Базовый уровень тарифа"}

        diff_pct = ((curr_pure_rate - trunk_median_pure_rate) / trunk_median_pure_rate) * 100

        if diff_pct <= -12.0:
            status = "EXCELLENT"
            expl = f"Отель отдает проживание со скидкой {abs(diff_pct):.0f}% к сезонному уровню"
        elif diff_pct <= 4.0:
            status = "GOOD"
            expl = f"Справедливый тариф отеля с учетом вычета фиксированного перелета"
        else:
            status = "HIGH"
            expl = f"Завышенный тариф на проживание (+{diff_pct:.0f}% от медианы)"

        return {
            "diff_pct": round(diff_pct, 1),
            "status": status,
            "explanation": expl,
            "curr_pure_rate": curr_pure_rate,
            "benchmark_pure_rate": trunk_median_pure_rate,
        }
