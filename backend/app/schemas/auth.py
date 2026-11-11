from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Unique user email address")
    password: str = Field(..., min_length=8, description="Password (at least 8 characters)")
    full_name: Optional[str] = Field(None, max_length=128)
    telegram_chat_id: Optional[str] = Field(None, description="Telegram Chat ID for notifications")


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    role: str = "USER"
    telegram_chat_id: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


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

