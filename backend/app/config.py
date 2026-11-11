from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    APP_NAME: str = "Travel Monitor 2.0"
    APP_ENV: str = "development"
    DATABASE_URL: str = f"sqlite+aiosqlite:///{ROOT_DIR / 'travel_monitor_v2.db'}"
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    SECRET_KEY: str = "development-secret-key-change-in-production-2026"
    JWT_SECRET_KEY: str = "development-jwt-secret-key-super-entropy-change-in-prod-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours access token
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    
    # Live Crawler settings
    SCRAPER_TIMEOUT_SECONDS: float = 12.0
    CACHE_SEARCH_TTL_SECONDS: int = 7200  # 2 hours
    ENABLE_BACKGROUND_SCHEDULER: bool = False  # Disabled on web servers; scraping is handled by GitHub Actions cron

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def sanitize_db_url(cls, v):
        if not v or not str(v).strip():
            return f"sqlite+aiosqlite:///{ROOT_DIR / 'travel_monitor_v2.db'}"
        return str(v).strip()

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.is_file() else ".env",
        extra="ignore"
    )


settings = Settings()

