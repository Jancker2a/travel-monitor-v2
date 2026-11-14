from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import date, datetime


class HotelCatalogCard(BaseModel):
    hotel_id: str
    display_name: str
    country: str
    region: Optional[str] = None
    stars: int
    ta_rating: Optional[float] = None
    ta_reviews: int = 0
    main_image_url: Optional[str] = None
    current_min_price: float
    typical_median_price: float
    historical_min_price: float
    historical_max_price: float
    delta_vs_typical_pct: float
    change_24h_pct: float = 0.0
    change_48h_pct: float = 0.0
    change_7d_pct: float = 0.0
    deal_score: int = 50
    deal_confidence: str = "Medium"
    badges: List[str] = Field(default_factory=list)
    beach_line: Optional[int] = 1
    beach_type: Optional[str] = None
    has_aquapark: Optional[bool] = False
    has_heated_pools: Optional[bool] = False
    cheapest_checkin_date: Optional[Union[str, date]] = None
    cheapest_duration_nights: int = 7
    cheapest_airport_code: str = "WAW"
    cheapest_offer_url: Optional[str] = None
    cohort_hash: Optional[str] = None
    last_updated: Union[str, datetime]


class HotelCatalogResponse(BaseModel):
    filter_id: str
    total_hotels: int
    hotels: List[HotelCatalogCard]
    last_updated_at: Optional[Union[str, datetime]] = None

