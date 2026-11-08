import asyncio
import logging
from typing import Optional
import httpx

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.watchlist_service import WatchlistService
from app.services.normalized_crawler import NormalizedCrawlerService

logger = logging.getLogger("travel_monitor_2.scheduler")


class BackgroundScheduler:
    """Async background worker for scheduled Watchlist checks, Telegram alerts, and normalized crawling."""

    def __init__(self, check_interval_seconds: int = 3600, crawler_interval_seconds: int = 21600):
        self.check_interval_seconds = check_interval_seconds
        self.crawler_interval_seconds = crawler_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._crawler_task: Optional[asyncio.Task] = None

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self._crawler_task = asyncio.create_task(self._run_crawler_loop())
        logger.info(
            f"Background Scheduler started (watchlist interval: {self.check_interval_seconds}s, crawler interval: {self.crawler_interval_seconds}s)"
        )

    async def stop(self):
        self._running = False
        for t in [self._task, self._crawler_task]:
            if t and not t.done():
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
        logger.info("Background Scheduler stopped.")

    async def _run_loop(self):
        while self._running:
            try:
                await self.run_check_cycle()
            except Exception as e:
                logger.error(f"Error during scheduler execution cycle: {e}")

            try:
                await asyncio.sleep(self.check_interval_seconds)
            except asyncio.CancelledError:
                break

    async def _run_crawler_loop(self):
        """Periodic background pass to maintain normalized 1p 8n price benchmark database."""
        # Initial wait to let app startup smoothly
        await asyncio.sleep(10)
        while self._running:
            try:
                logger.info("Scheduler: starting periodic normalized crawler pass...")
                await NormalizedCrawlerService.run_crawler_cycle(max_offers_per_dest=30)
            except Exception as e:
                logger.error(f"Error during periodic normalized crawler pass: {e}")

            try:
                await asyncio.sleep(self.crawler_interval_seconds)
            except asyncio.CancelledError:
                break

    async def run_check_cycle(self) -> int:
        """Executes one pass over all active watchlists and dispatches alerts."""
        logger.info("Scheduler: starting active Watchlist evaluation cycle...")
        async with AsyncSessionLocal() as db:
            alerts = await WatchlistService.check_watchlist_triggers(db)

        if not alerts:
            logger.info("Scheduler: 0 alert triggers detected.")
            return 0

        logger.info(f"Scheduler: {len(alerts)} alerts triggered! Dispatching notifications...")
        for alert in alerts:
            await self._dispatch_telegram_alert(alert)

        return len(alerts)

    async def _dispatch_telegram_alert(self, alert):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token or token.startswith("dummy"):
            logger.info(f"[MOCK TG NOTIFICATION -> {alert.user_chat_id}]: {alert.hotel_name} dropped to {alert.current_price_pln:.0f} PLN")
            return

        tg_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": alert.user_chat_id,
            "text": alert.message_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(tg_url, json=payload)
                if resp.status_code == 200:
                    logger.info(f"Telegram alert sent successfully to {alert.user_chat_id}")
                else:
                    logger.warning(f"Telegram API responded with {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Failed to send Telegram alert to {alert.user_chat_id}: {e}")


scheduler = BackgroundScheduler(check_interval_seconds=3600)

