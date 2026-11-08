import asyncio
import logging
from typing import Optional
import httpx

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.watchlist_service import WatchlistService

logger = logging.getLogger("travel_monitor_2.scheduler")


class BackgroundScheduler:
    """Async background worker for scheduled Watchlist checks and Telegram push alerts."""

    def __init__(self, check_interval_seconds: int = 3600):
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Background Watchlist Scheduler started (interval: {self.check_interval_seconds}s)")

    async def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Background Watchlist Scheduler stopped.")

    async def _run_loop(self):
        while self._running:
            try:
                await self.run_check_cycle()
            except Exception as e:
                logger.error(f"Error during scheduler execution cycle: {e}")

            # Sleep until next interval
            try:
                await asyncio.sleep(self.check_interval_seconds)
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

