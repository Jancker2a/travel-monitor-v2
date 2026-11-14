from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Unique user email address")
    password: str = Field(..., min_length=8, description="Password (at least 8 characters)")
    full_name: Optional[str] = Field(None, max_length=128)
    telegram_chat_id: Optional[str] = Field(None, description="Telegram Chat ID for notifications")


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: Optional[str] = None
    role: str = "USER"
    telegram_chat_id: Optional[str] = None
    telegram_notifications_enabled: bool = True
    is_active: bool = True
    created_at: Optional[datetime] = None

    # Daily Digest Preferences
    digest_enabled: bool = True
    digest_time: str = "09:00"
    digest_days: str = "ALL"
    digest_include_watchlist: bool = True
    digest_include_top_drops: bool = True
    digest_include_hot_deals: bool = True
    digest_include_historic_lows: bool = True
    digest_min_deal_score: int = 80
    digest_max_offers: int = 5
    digest_only_if_changes: bool = True

    # Quiet Hours
    quiet_hours_enabled: bool = True
    quiet_hours_start: int = 23
    quiet_hours_end: int = 8


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, max_length=128)
    telegram_chat_id: Optional[str] = Field(None, description="Telegram Chat ID or username")
    telegram_notifications_enabled: Optional[bool] = None

    # Daily Digest Preferences
    digest_enabled: Optional[bool] = None
    digest_time: Optional[str] = None
    digest_days: Optional[str] = None
    digest_include_watchlist: Optional[bool] = None
    digest_include_top_drops: Optional[bool] = None
    digest_include_hot_deals: Optional[bool] = None
    digest_include_historic_lows: Optional[bool] = None
    digest_min_deal_score: Optional[int] = None
    digest_max_offers: Optional[int] = None
    digest_only_if_changes: Optional[bool] = None

    # Quiet Hours
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None



class TestTelegramRequest(BaseModel):
    chat_id: Optional[str] = Field(None, description="Optional override of Telegram Chat ID")


class TestTelegramResponse(BaseModel):
    success: bool
    message: str
    chat_id: Optional[str] = None
    simulated: bool = False


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: UserProfileResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class AdminStatusResponse(BaseModel):
    has_admin: bool
    admin_email: Optional[str] = None


class ClaimAdminRequest(BaseModel):
    admin_key: Optional[str] = None

