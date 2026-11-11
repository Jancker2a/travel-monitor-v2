import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from app.config import settings

# Argon2 is the primary recommendation by OWASP, with bcrypt fallback
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v2/auth/login",
    auto_error=False
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against hashed value."""
    if not plain_password or not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generates strong Argon2id/bcrypt hash for user password."""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Creates JWT access token with expiration and user payload."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Creates long-lived refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    })
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates JWT token signature and expiration."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.PyJWTError:
        return None

