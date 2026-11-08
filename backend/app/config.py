from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    APP_NAME: str = "Travel Monitor 2.0"
    APP_ENV: str = "development"
    DATABASE_URL: str = f"sqlite+aiosqlite:///{ROOT_DIR / 'travel_monitor_v2.db'}"
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    SECRET_KEY: str = "development-secret-key-change-in-production-2026"
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    
    # Live Crawler settings
    SCRAPER_TIMEOUT_SECONDS: float = 12.0
    CACHE_SEARCH_TTL_SECONDS: int = 7200  # 2 hours

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.is_file() else ".env",
        extra="ignore"
    )


settings = Settings()

