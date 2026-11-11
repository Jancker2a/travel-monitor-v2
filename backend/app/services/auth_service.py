import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import Depends, HTTPException, status
from app.database import get_db
from app.models.user import User
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    oauth2_scheme,
)
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserProfileResponse,
)
from app.config import settings

logger = logging.getLogger("travel_monitor_2")


class AuthService:
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        normalized = email.strip().lower()
        stmt = select(User).where(User.email == normalized)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def get_admin_status(cls, db: AsyncSession) -> dict:
        stmt = select(func.count(User.id)).where(User.role == "ADMIN", User.is_active == True)
        admin_count = (await db.execute(stmt)).scalar() or 0
        admin_email = None
        if admin_count > 0:
            email_stmt = select(User.email).where(User.role == "ADMIN", User.is_active == True).limit(1)
            admin_email = (await db.execute(email_stmt)).scalar()
        return {
            "has_admin": admin_count > 0,
            "admin_email": admin_email,
        }

    @classmethod
    async def claim_admin(cls, db: AsyncSession, current_user: User, admin_key: Optional[str] = None) -> UserProfileResponse:
        admin_status = await cls.get_admin_status(db)
        if admin_status["has_admin"]:
            # If an admin already exists, allow second admin only with SECRET_KEY
            if not admin_key or admin_key != settings.SECRET_KEY:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Администратор системы уже назначен. Для добавления требуется секретный ключ.",
                )

        current_user.role = "ADMIN"
        await db.commit()
        await db.refresh(current_user)
        logger.info(f"User {current_user.email} successfully claimed ADMIN role!")
        return UserProfileResponse.model_validate(current_user)

    @classmethod
    async def register(cls, db: AsyncSession, req: UserRegisterRequest) -> TokenResponse:
        existing = await cls.get_user_by_email(db, req.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже зарегистрирован",
            )
        
        # Determine role: first registered user becomes ADMIN, or if matches ADMIN_EMAIL
        admin_status = await cls.get_admin_status(db)
        assigned_role = "USER"
        if not admin_status["has_admin"]:
            assigned_role = "ADMIN"
            logger.info(f"First user onboarding: granting ADMIN role to {req.email}")
        elif getattr(settings, "ADMIN_EMAIL", None) and req.email.strip().lower() == settings.ADMIN_EMAIL.strip().lower():
            assigned_role = "ADMIN"

        hashed = get_password_hash(req.password)
        new_user = User(
            email=req.email.strip().lower(),
            hashed_password=hashed,
            full_name=req.full_name,
            telegram_chat_id=req.telegram_chat_id,
            is_active=True,
            role=assigned_role,
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        logger.info(f"Registered new user: {new_user.email} with role {new_user.role} (id: {new_user.id})")
        return cls._generate_token_response(new_user)

    @classmethod
    async def login(cls, db: AsyncSession, req: UserLoginRequest) -> TokenResponse:
        user = await cls.get_user_by_email(db, req.email)
        if not user or not verify_password(req.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный адрес электронной почты или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Аккаунт деактивирован администратором",
            )
        
        # If user email matches ADMIN_EMAIL and role isn't ADMIN, auto-promote
        if getattr(settings, "ADMIN_EMAIL", None) and user.email.lower() == settings.ADMIN_EMAIL.lower() and user.role != "ADMIN":
            user.role = "ADMIN"

        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)

        logger.info(f"User login successful: {user.email} (role: {user.role})")
        return cls._generate_token_response(user)

    @classmethod
    async def refresh_token(cls, db: AsyncSession, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный или истёкший токен обновления",
            )
        
        user_id = payload.get("sub")
        user = await cls.get_user_by_id(db, user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден или заблокирован",
            )
        
        return cls._generate_token_response(user)

    @staticmethod
    def _generate_token_response(user: User) -> TokenResponse:
        payload = {"sub": user.id, "email": user.email, "role": user.role}
        access_token = create_access_token(payload)
        refresh_token = create_refresh_token(payload)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserProfileResponse.model_validate(user),
        )


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Strict dependency requiring authenticated user."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация для выполнения действия",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или истёкший токен сессии",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    user = await AuthService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользовательский аккаунт заблокирован",
        )
    return user


async def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Optional dependency that returns User if token is present, else None."""
    if not token:
        return None
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return await AuthService.get_user_by_id(db, user_id)

