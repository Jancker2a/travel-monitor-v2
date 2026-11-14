from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class DashboardSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    monitor_id: str
    monitor_title: str
    is_active: bool = True
    notify_mode: str = "INSTANT"  # INSTANT, DIGEST_ONLY
    min_drop_pct: float = 5.0
    min_drop_pln: Optional[float] = None
    min_deal_score: int = 80
    max_budget_pln: Optional[float] = None
    only_historic_low: bool = False
    min_ta_rating: Optional[float] = None
    preferred_airports: Optional[str] = None  # e.g. "WAW,KTW"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DashboardSubscriptionUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    notify_mode: Optional[str] = Field(None, description="INSTANT or DIGEST_ONLY")
    min_drop_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    min_drop_pln: Optional[float] = Field(None, ge=0.0)
    min_deal_score: Optional[int] = Field(None, ge=0, le=100)
    max_budget_pln: Optional[float] = Field(None, ge=0.0)
    only_historic_low: Optional[bool] = None
    min_ta_rating: Optional[float] = Field(None, ge=1.0, le=5.0)
    preferred_airports: Optional[str] = None
    monitor_title: Optional[str] = None


class DashboardSubscriptionTestResponse(BaseModel):
    success: bool
    message: str
    offer_found: bool = False
    hotel_name: Optional[str] = None
    price_pln: Optional[float] = None
    simulated: bool = False

