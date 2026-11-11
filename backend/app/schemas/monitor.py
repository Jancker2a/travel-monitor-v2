from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class FlyUrlParseRequest(BaseModel):
    url: str = Field(..., description="Full search URL from fly.pl")


class FlyUrlParseResponse(BaseModel):
    is_valid: bool
    parsed_title: str
    destination: Optional[str] = None
    region: Optional[str] = None
    departure_airports: List[str] = Field(default_factory=list)
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    duration_min: Optional[int] = None
    duration_max: Optional[int] = None
    adults: int = 2
    children: int = 0
    catering: Optional[str] = None
    stars: Optional[int] = None
    structured_search_request: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class UserMonitorCreate(BaseModel):
    title: str = Field(..., max_length=128)
    source_type: str = Field("CUSTOM_FILTER", description="CUSTOM_FILTER or FLY_URL")
    fly_source_url: Optional[str] = None
    filter_params: Dict[str, Any] = Field(..., description="Dictionary of search parameters matching SearchRequest")
    check_interval_hours: int = Field(3, ge=1, le=24, description="Hourly frequency of checking prices")
    min_drop_pct: float = Field(5.0, ge=1.0, le=50.0, description="Minimum drop percentage to trigger alert")
    max_budget_pln: Optional[float] = Field(None, ge=100.0)
    notify_telegram: bool = True
    notify_email: bool = False


class UserMonitorUpdate(BaseModel):
    title: Optional[str] = None
    check_interval_hours: Optional[int] = Field(None, ge=1, le=24)
    min_drop_pct: Optional[float] = Field(None, ge=1.0, le=50.0)
    max_budget_pln: Optional[float] = None
    notify_telegram: Optional[bool] = None
    notify_email: Optional[bool] = None
    is_active: Optional[bool] = None


class UserMonitorResponse(BaseModel):
    id: str
    user_id: str
    title: str
    source_type: str
    fly_source_url: Optional[str] = None
    filter_params: Dict[str, Any]
    check_interval_hours: int
    min_drop_pct: float
    max_budget_pln: Optional[float] = None
    notify_telegram: bool
    notify_email: bool
    is_active: bool
    status: str
    last_checked_at: Optional[datetime] = None
    last_offers_count: int = 0
    last_min_price_pln: Optional[float] = None
    last_error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
