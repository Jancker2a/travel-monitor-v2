from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field


class WatchlistCreateRequest(BaseModel):
    cohort_hash: str = Field(description="32-char SHA256 deterministic hash of the tour cohort")
    user_chat_id: str = Field(description="User identifier or Telegram chat ID")
    target_price_pln: Optional[float] = Field(default=None, description="Notify when price <= target")
    notify_any_drop: bool = Field(default=True, description="Notify on any price drop even if above target")


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
    latest_price_pln: float
    deal_score: int
    deal_badge: str
    hopper_verdict: str
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

