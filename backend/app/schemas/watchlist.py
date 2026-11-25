from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field


class WatchlistCreateRequest(BaseModel):
    cohort_hash: str = Field(description="32-char SHA256 deterministic hash of the tour cohort")
    user_chat_id: str = Field(description="User identifier or Telegram chat ID")
    target_price_pln: Optional[float] = Field(default=None, description="Notify when price <= target")
    notify_any_drop: bool = Field(default=True, description="Notify on any price drop even if above target")
    alert_threshold_pct: Optional[float] = Field(default=5.0, description="Minimum drop pct to alert (e.g. 5, 10, 15)")
    min_deal_score: Optional[int] = Field(default=None, description="Minimum Deal Score required to notify (e.g. 75, 85)")
    min_days_to_dep: Optional[int] = Field(default=0, ge=0, le=90, description="Minimum days before departure to notify")
    is_active: bool = Field(default=True, description="Active status of monitoring")


class WatchlistUpdateRequest(BaseModel):
    target_price_pln: Optional[float] = Field(default=None, description="Notify when price <= target")
    notify_any_drop: Optional[bool] = Field(default=None, description="Notify on any price drop even if above target")
    alert_threshold_pct: Optional[float] = Field(default=None, description="Minimum drop pct to alert")
    min_deal_score: Optional[int] = Field(default=None, description="Minimum Deal Score required to notify")
    min_days_to_dep: Optional[int] = Field(default=None, ge=0, le=90, description="Minimum days before departure")
    is_active: Optional[bool] = Field(default=None, description="Active status of monitoring")


class WatchlistItemResponse(BaseModel):
    watch_id: str
    user_chat_id: str
    cohort_hash: str
    hotel_id: str
    hotel_name: str
    country: str
    departure_date: date
    duration_nights: int
    airport: str
    target_price_pln: Optional[float] = None
    alert_threshold_pct: Optional[float] = 5.0
    min_deal_score: Optional[int] = None
    min_days_to_dep: Optional[int] = 0
    is_active: bool = True
    latest_price_pln: float
    typical_median_pln: Optional[float] = None
    historical_min_pln: Optional[float] = None
    deal_score: int
    deal_badge: str
    hopper_verdict: str
    delta_vs_typical_pct: Optional[float] = None
    drop_48h_pct: Optional[float] = None
    target_reached: bool
    booking_url: Optional[str] = None
    created_at: datetime
    last_notified_at: Optional[datetime] = None


class WatchlistListResponse(BaseModel):
    total: int
    items: List[WatchlistItemResponse]


class WatchlistAlertPayload(BaseModel):
    watch_id: str
    user_chat_id: str
    hotel_name: str
    country: str
    previous_price_pln: float
    current_price_pln: float
    drop_amount_pln: float
    drop_pct: float
    target_reached: bool
    target_price_pln: Optional[float] = None
    booking_url: Optional[str] = None
    message_text: str

