from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "Travel Monitor 2.0"
    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://tm_admin:tm_secret_2026@localhost:5432/travel_monitor_v2"
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    SECRET_KEY: str = "development-secret-key-change-in-production-2026"
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    
    # Live Crawler settings
    SCRAPER_TIMEOUT_SECONDS: float = 12.0
    CACHE_SEARCH_TTL_SECONDS: int = 7200  # 2 hours

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

