#!/usr/bin/env python3
"""
CI / Production Hourly Cron Runner for Travel Monitor 2.0.

Executed periodically by GitHub Actions (cron: "17 * * * *") or systemd/cron:
1. Scrapes active curated & custom filter monitors into travel_monitor_v2.db
2. Crawls normalized standard benchmarks (1 adult / 8 nights, today+20d)
3. Evaluates user Watchlists and dispatches Telegram price drop alerts
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

# Ensure backend and repo root are on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.services.filter_monitor_service import FilterMonitorService
from app.services.site_rebuilder import SiteRebuilderService
from app.services.normalized_crawler import NormalizedCrawlerService
from app.services.watchlist_service import WatchlistService
from app.services.dashboard_alert_service import DashboardAlertService
from app.services.scheduler import scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("travel_monitor_2.cron")


async def sync_database_sequences():
    """Ensures PostgreSQL sequences match MAX(id) to avoid duplicate key errors."""
    try:
        async with AsyncSessionLocal() as session:
            bind = session.bind or session.get_bind()
            dialect = getattr(bind, "name", "")
            if not dialect and hasattr(bind, "dialect"):
                dialect = bind.dialect.name
            if "postgresql" in str(dialect).lower():
                logger.info("🔧 [PostgreSQL] Synchronizing primary key sequences with MAX(id)...")
                for table, col in [("normalized_price_snapshots", "id"), ("price_snapshots", "id"), ("offer_cohorts", "cohort_id")]:
                    try:
                        await session.execute(text(f"""
                            SELECT setval(
                                pg_get_serial_sequence('{table}', '{col}'),
                                COALESCE((SELECT MAX({col}) FROM {table}), 0) + 1,
                                false
                            );
                        """))
                        await session.commit()
                        logger.info(f"✅ Sequence synchronized for '{table}'.")
                    except Exception as e:
                        logger.warning(f"Sequence sync skipped for '{table}': {e}")
                        await session.rollback()
    except Exception as e:
        logger.warning(f"Sequence sync pre-check skipped: {e}")


async def main():
    start_time = datetime.now(timezone.utc)
    logger.info("==================================================================")
    logger.info(f"🚀 [TRAVEL MONITOR 2.0] Hourly Cron Execution Started at {start_time.isoformat()}")
    logger.info("==================================================================")

    # 0. Sync DB Sequences (PostgreSQL safety)
    await sync_database_sequences()

    # 0.5 Ingest latest canonical V1 data from Git repository into PostgreSQL
    logger.info(">>> STEP 0.5: Ingesting latest canonical V1 data from Git into PostgreSQL...")
    try:
        from scripts.sync_v1_main_to_pg import run_sync
        await run_sync()
        logger.info("✅ V1 -> PostgreSQL synchronization completed successfully.")
    except Exception as e:
        logger.error(f"⚠️ V1 sync skipped or encountered non-fatal error: {e}", exc_info=True)

    # 1. Run Hourly Filter Monitors
    logger.info(">>> STEP 1: Running Hourly Filter Monitors...")
    try:
        monitor_results = await FilterMonitorService.run_all_hourly_monitors()
        logger.info(f"✅ Filter Monitors completed: {len(monitor_results)} filters processed.")
    except Exception as e:
        logger.error(f"❌ Error in Filter Monitors: {e}", exc_info=True)

    # 2. Rebuild Dashboards and Hotel Series for Server & UI
    logger.info(">>> STEP 2: Rebuilding Static HTML Dashboards & Hotel Series...")
    try:
        async with AsyncSessionLocal() as db:
            rebuild_res = await SiteRebuilderService.rebuild_all(db)
            logger.info(f"✅ Dashboard Rebuild completed: {len(rebuild_res.get('updated_dashboards', []))} dashboards refreshed.")
    except Exception as e:
        logger.error(f"❌ Error during dashboard rebuild: {e}", exc_info=True)

    # 3. Run Normalized Benchmark Crawler (1p / 8n, today+20d)
    logger.info(">>> STEP 3: Running Normalized Benchmark Crawler...")
    try:
        crawler_result = await NormalizedCrawlerService.run_crawler_cycle(max_offers_per_dest=25)
        logger.info(f"✅ Normalized Crawler completed: {crawler_result.get('total_collected', 0)} snapshots collected.")
    except Exception as e:
        logger.error(f"❌ Error in Normalized Crawler: {e}", exc_info=True)

    # 4. Check Watchlist Price Drop Triggers & Dispatch Telegram Alerts
    logger.info(">>> STEP 4: Evaluating Watchlists & Telegram Alerts...")
    try:
        async with AsyncSessionLocal() as db:
            alerts = await WatchlistService.check_watchlist_triggers(db)
            if alerts:
                logger.info(f"🔔 {len(alerts)} price drop triggers detected. Dispatching alerts...")
                for a in alerts:
                    await scheduler._dispatch_telegram_alert(a)
            else:
                logger.info("ℹ️ No new price drops below target thresholds.")
    except Exception as e:
        logger.error(f"❌ Error in Watchlist evaluation: {e}", exc_info=True)

    # 5. Dispatch Morning Daily Digest to Telegram Subscribers
    logger.info(">>> STEP 5: Evaluating & Dispatching Daily Digests to Telegram Subscribers...")
    try:
        force_digest = os.environ.get("FORCE_DIGEST", "false").lower() in ("true", "1", "yes")
        async with AsyncSessionLocal() as db:
            digest_results = await DashboardAlertService.dispatch_daily_digests(db, force=force_digest)
            logger.info(f"✅ Daily Digest run completed: {len(digest_results)} processed.")
    except Exception as e:
        logger.error(f"❌ Error in Daily Digest dispatch: {e}", exc_info=True)

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info("==================================================================")
    logger.info(f"🏁 [TRAVEL MONITOR 2.0] Hourly Cron Completed successfully in {duration:.1f}s")
    logger.info("==================================================================")


if __name__ == "__main__":
    asyncio.run(main())

