from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field


class SearchDates(BaseModel):
    start_date_min: date
    start_date_max: date


class SearchDuration(BaseModel):
    min_nights: int = Field(default=7, ge=1, le=30)
    max_nights: int = Field(default=10, ge=1, le=30)


class SearchTravelers(BaseModel):
    adults: int = Field(default=2, ge=1, le=10)
    children: int = Field(default=0, ge=0, le=6)
    children_ages: List[int] = Field(default_factory=list)


class SearchRequest(BaseModel):
    destination: str = Field(description="Country or region slug, e.g. 'egypt', 'turkey', 'greece'")
    dates: SearchDates
    duration: SearchDuration = Field(default_factory=SearchDuration)
    travelers: SearchTravelers = Field(default_factory=SearchTravelers)
    airports: List[str] = Field(default_factory=lambda: ["WAW", "KTW"])
    price_max_pln: Optional[float] = None
    force_live_refresh: bool = False


class OfferSummary(BaseModel):
    cohort_hash: str
    total_price_pln: float
    price_per_night_pax: float
    departure_date: date
    duration_nights: int
    airport: str
    operator: Optional[str] = None
    booking_url: Optional[str] = None


class HotelIntelligence(BaseModel):
    deal_score: int
    deal_badge: str
    hopper_verdict: str  # BUY NOW, WAIT, OVERPRICED
    hopper_confidence: float
    recommendation: str
    drop_48h_pct: float
    historic_min_pln: float
    typical_median_pln: float
    german_arbitrage_diff_pln: Optional[float] = None


class SearchHotelItem(BaseModel):
    hotel_id: str
    hotel_name: str
    stars: int
    region: Optional[str] = None
    country: str
    main_image_url: Optional[str] = None
    ta_rating: Optional[float] = None
    ta_reviews: Optional[int] = None
    specs: Optional[dict] = None
    current_offer: OfferSummary
    intelligence: HotelIntelligence
    history_sparkline: List[float] = Field(default_factory=list)
    normalized_benchmark_1p_8n: Optional[float] = None
    pure_hotel_night_pln: Optional[float] = None


class SearchResponse(BaseModel):
    search_id: str
    cached: bool
    total_found: int
    results: List[SearchHotelItem]

