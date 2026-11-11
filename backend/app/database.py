import os
import glob
import gzip
import shutil
import logging
from pathlib import Path
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

logger = logging.getLogger("travel_monitor_2")

# Auto-decompress database archive if db file does not exist but chunks do
ROOT_DIR = Path(__file__).resolve().parents[2]
db_file = ROOT_DIR / "travel_monitor_v2.db"
parts = sorted(glob.glob(str(ROOT_DIR / "travel_monitor_v2.db.gz.*")))
if not db_file.exists() and parts:
    try:
        logger.info(f"Unpacking {len(parts)} database archive chunks into {db_file}...")
        combined_gz = ROOT_DIR / "travel_monitor_v2.combined.gz"
        with open(combined_gz, "wb") as out_f:
            for p in parts:
                with open(p, "rb") as pf:
                    shutil.copyfileobj(pf, out_f)
        with gzip.open(combined_gz, "rb") as gz_in, open(db_file, "wb") as out_f:
            shutil.copyfileobj(gz_in, out_f)
        if combined_gz.exists():
            combined_gz.unlink()
        logger.info("Database unpacked successfully.")
    except Exception as unpack_err:
        logger.error(f"Error unpacking database archive: {unpack_err}")

import urllib.parse

# Database engine initialization
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

connect_args = {}
engine_kwargs = {
    "echo": (settings.APP_ENV == "development"),
    "pool_pre_ping": True,
}

if "sqlite" in db_url:
    connect_args["check_same_thread"] = False
else:
    # Handle asyncpg URL query params: asyncpg rejects 'sslmode' / 'channel_binding' in query strings
    if "asyncpg" in db_url:
        parsed = urllib.parse.urlsplit(db_url)
        params = urllib.parse.parse_qs(parsed.query)
        sslmode_val = params.pop("sslmode", [None])[0] or params.pop("ssl", [None])[0]
        params.pop("channel_binding", None)
        new_query = urllib.parse.urlencode(params, doseq=True)
        db_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))

        # Enable SSL for cloud PostgreSQL (Neon, Supabase, AWS, etc.)
        if sslmode_val in ("require", "verify-ca", "verify-full", "prefer", "true", "True") or "neon.tech" in db_url:
            connect_args["ssl"] = "require"

    # PostgreSQL / Neon / Supabase connection pool tuning
    connect_args["statement_cache_size"] = 0
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(
    db_url,
    connect_args=connect_args,
    **engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining async DB sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

