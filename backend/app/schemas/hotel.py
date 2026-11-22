from datetime import datetime, date
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


class HotelHistoryPoint(BaseModel):
    recorded_at: datetime
    total_price_pln: float
    price_per_night_per_pax: float
    departure_date: date
    duration_nights: int
    airport: str
    normalized_price_1p_8n: Optional[float] = None
    pure_hotel_night_rate: Optional[float] = None
    scaled_tour_price: Optional[float] = None
    adults: Optional[int] = 2
    children: Optional[int] = 0


class HotelPassportResponse(BaseModel):
    hotel_id: str
    display_name: str
    country: str
    region: str
    stars: int
    ta_rating: Optional[float] = None
    ta_reviews: Optional[int] = None
    main_image_url: Optional[str] = None
    all_time_min_pln: float
    all_time_max_pln: float
    typical_median_pln: float
    current_price_pln: float = 0.0
    active_cohorts_count: int
    deal_score: int = 70
    deal_badge: str = "GOOD_DEAL"
    hopper_verdict: str = "BUY NOW"

    data_maturity_tier: int = 1
    maturity_explanation: Optional[str] = None
    user_query_scope: Optional[Dict[str, Any]] = None

    # Rich V1 Knowledge Base Profile & AI Dossier
    gallery_photos: List[str] = Field(default_factory=list)
    tripadvisor_url: Optional[str] = None
    google_reviews_url: Optional[str] = None
    youtube_search_url: Optional[str] = None

    beach_line: int = 1
    beach_type: str = "песчано-галечный пляж"
    sea_entry: str = "пологий вход"
    has_aquapark: bool = False
    has_heated_pools: bool = False
    food_concept: str = "All Inclusive"

    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    verdict: str = ""
    suitable_for: str = ""

    ai_action_signal: str = ""
    ai_price_summary: str = ""
    ai_hotel_summary: str = ""
    seasonal_norm_pln: Optional[float] = None
    ai_insight: Optional[Dict[str, Any]] = None

    infra_rich: Optional[Dict[str, Any]] = None
    german_arbitrage: Optional[Dict[str, Any]] = None
    horizon_arbitrage: Optional[Dict[str, Any]] = None
    available_packages: List[Dict[str, Any]] = Field(default_factory=list)
    other_filters: List[Dict[str, Any]] = Field(default_factory=list)

    history_points: List[HotelHistoryPoint] = Field(default_factory=list)
