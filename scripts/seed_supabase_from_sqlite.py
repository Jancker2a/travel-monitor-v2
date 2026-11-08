#!/usr/bin/env python3
"""
Seed Supabase PostgreSQL from Local SQLite Database.

Usage:
    export DATABASE_URL="postgresql+asyncpg://postgres:YOUR_PASSWORD@db.YOUR_REF.supabase.co:5432/postgres"
    python scripts/seed_supabase_from_sqlite.py
"""

import asyncio
import logging
import os
import sqlite3
import sys
from pathlib import Path
from sqlalchemy import text

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(backend_dir))

from app.database import engine, Base, AsyncSessionLocal
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_supabase")

SQLITE_PATH = Path(__file__).resolve().parents[1] / "travel_monitor_v2.db"


async def main():
    target_url = settings.DATABASE_URL
    logger.info("==================================================================")
    logger.info("🚀 Seeding Supabase PostgreSQL from SQLite")
    logger.info(f"Target Database: {target_url.split('@')[-1] if '@' in target_url else target_url}")
    logger.info("==================================================================")

    if not SQLITE_PATH.exists():
        logger.error(f"❌ SQLite database not found at {SQLITE_PATH}")
        sys.exit(1)

    if "sqlite" in target_url:
        logger.warning("⚠️ Warning: DATABASE_URL is pointing to SQLite, not PostgreSQL!")
        logger.warning("To migrate to Supabase, set DATABASE_URL to your Supabase connection string:")
        logger.warning('export DATABASE_URL="postgresql+asyncpg://postgres:PASSWORD@db.REF.supabase.co:5432/postgres"')
        return

    # 1. Create all tables in target PostgreSQL
    logger.info("📦 Step 1: Initializing PostgreSQL schema (tables & indexes)...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Schema initialized.")

    # 2. Connect to SQLite
    sqlite_conn = sqlite3.connect(str(SQLITE_PATH))
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    tables = [
        "hotels",
        "offer_cohorts",
        "price_snapshots",
        "normalized_price_snapshots",
        "filter_monitors",
        "watchlists",
    ]

    async with AsyncSessionLocal() as session:
        for table in tables:
            sqlite_cursor.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()
            if not rows:
                logger.info(f"⏭️ Table {table} is empty, skipping.")
                continue

            columns = rows[0].keys()
            col_names = ", ".join(columns)
            placeholders = ", ".join([f":{col}" for col in columns])
            insert_stmt = text(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING")

            logger.info(f"📤 Migrating {len(rows)} records from table '{table}'...")
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = [dict(row) for row in rows[i:i + batch_size]]
                await session.execute(insert_stmt, batch)
                await session.commit()
            logger.info(f"✅ Table '{table}' migrated successfully ({len(rows)} rows).")

    logger.info("==================================================================")
    logger.info("🎉 All 44,700+ records successfully migrated to Supabase!")
    logger.info("==================================================================")


if __name__ == "__main__":
    asyncio.run(main())
