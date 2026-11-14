from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserProfileResponse,
    RefreshTokenRequest,
    AdminStatusResponse,
    ClaimAdminRequest,
    UserUpdateRequest,
    TestTelegramRequest,
    TestTelegramResponse,
)
from app.services.auth_service import (
    AuthService,
    get_current_user,
)
from app.services.telegram_service import TelegramService

router = APIRouter(prefix="/api/v2/auth", tags=["Authentication & Security"])


@router.get("/admin-status", response_model=AdminStatusResponse)
async def get_admin_status(db: AsyncSession = Depends(get_db)):
    """Checks whether the system has an onboarded administrator."""
    return await AuthService.get_admin_status(db)


@router.post("/claim-admin", response_model=UserProfileResponse)
async def claim_admin(
    req: Optional[ClaimAdminRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Allows current user to claim or assume ADMIN role if uninitialized or with secret key."""
    admin_key = req.admin_key if req else None
    return await AuthService.claim_admin(db, current_user, admin_key=admin_key)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Registers a new user account and returns JWT credentials."""
    return await AuthService.register(db, req)


@router.post("/login", response_model=TokenResponse)
async def login(req: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticates user with email & password, returning JWT access & refresh tokens."""
    return await AuthService.login(db, req)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Issues new access and refresh tokens using valid refresh token."""
    return await AuthService.refresh_token(db, req.refresh_token)


@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Returns profile and roles of currently authenticated user."""
    return UserProfileResponse.model_validate(current_user)


@router.patch("/me", response_model=UserProfileResponse)
async def update_me(
    req: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Updates user profile information and Telegram alert configuration."""
    if req.full_name is not None:
        current_user.full_name = req.full_name.strip()
    if req.telegram_chat_id is not None:
        cleaned_chat = req.telegram_chat_id.strip()
        current_user.telegram_chat_id = cleaned_chat if cleaned_chat else None
    if req.telegram_notifications_enabled is not None:
        current_user.telegram_notifications_enabled = req.telegram_notifications_enabled

    await db.commit()
    await db.refresh(current_user)
    return UserProfileResponse.model_validate(current_user)


@router.post("/test-telegram", response_model=TestTelegramResponse)
async def test_telegram_connection(
    req: TestTelegramRequest,
    current_user: User = Depends(get_current_user),
):
    """Sends a sample rich notification card to test Telegram integration."""
    target_chat = (req.chat_id or current_user.telegram_chat_id or "").strip()
    if not target_chat:
        return TestTelegramResponse(
            success=False,
            message="Chat ID не указан. Введите ваш Telegram Chat ID перед отправкой теста.",
            chat_id=None,
            simulated=False,
        )

    user_name = current_user.full_name or current_user.email.split("@")[0]
    res = await TelegramService.send_test_notification(chat_id=target_chat, user_name=user_name)
    return TestTelegramResponse(**res)


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logs out current user session."""
    return {"ok": True, "message": "Сессия успешно завершена"}

