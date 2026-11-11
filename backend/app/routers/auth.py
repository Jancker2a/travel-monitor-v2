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
)
from app.services.auth_service import (
    AuthService,
    get_current_user,
)

router = APIRouter(prefix="/api/v2/auth", tags=["Authentication & Security"])


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


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logs out current user session."""
    return {"ok": True, "message": "Сессия успешно завершена"}
