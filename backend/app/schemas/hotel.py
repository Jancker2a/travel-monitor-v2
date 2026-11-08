from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field


class HotelHistoryPoint(BaseModel):
    recorded_at: datetime
    total_price_pln: float
    price_per_night_per_pax: float
    departure_date: date
    duration_nights: int
    airport: str


class HotelPassportResponse(BaseModel):
    hotel_id: str
    display_name: str
    country: str
    region: str
    stars: int
    ta_rating: Optional[float] = None
    ta_reviews: int = 0
    main_image_url: Optional[str] = None
    all_time_min_pln: float
    all_time_max_pln: float
    typical_median_pln: float
    active_cohorts_count: int
    history_points: List[HotelHistoryPoint] = Field(default_factory=list)

