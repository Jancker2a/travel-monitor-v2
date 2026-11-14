import logging
import httpx
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("travel_monitor_2.telegram")


class TelegramService:
    """Service for sending rich Telegram notifications, test alerts, and watchlist drops."""

    @classmethod
    def get_bot_token(cls) -> Optional[str]:
        token = settings.TELEGRAM_BOT_TOKEN
        if token and not token.startswith("dummy"):
            return token.strip()
        return None

    @classmethod
    async def send_test_notification(
        cls,
        chat_id: str,
        user_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sends an authentic preview/test alert to the specified Telegram chat.
        Verifies bot token and chat ID connectivity.
        """
        cleaned_chat_id = str(chat_id).strip()
        if not cleaned_chat_id:
            return {
                "success": False,
                "message": "Chat ID не указан. Пожалуйста, введите ваш Telegram Chat ID.",
                "chat_id": "",
                "simulated": False,
            }

        token = cls.get_bot_token()
        text_message = (
            "🚀 <b>Travel Monitor 2.0 • Тестовое уведомление</b>\n\n"
            f"Привет, {user_name or 'Путешественник'}! 👋\n"
            "Ваш Telegram успешно подключен к персональному мониторингу цен на туры.\n\n"
            "🔔 <b>Пример карточки отеля при падении цены:</b>\n"
            "🏨 <b>Pickalbatros Palace Resort 5★</b>\n"
            "📍 Египет, Шарм-эль-Шейх • 🌊 1-я линия • 🔥 Подогрев\n"
            "✈️ Вылет: <b>2026-12-20</b> (7 ночей) • Варшава (WAW)\n"
            "💰 Цена: <s>8 450 zł</s> ➔ <b>6 950 zł</b> (<b>-1 500 zł / -18%</b>)\n"
            "🎯 Deal Score: <b>92/100 🔥 Hot Deal!</b>\n"
            "🔮 Прогноз Хоппера: 🟢 <b>ПОКУПАТЬ СЕЙЧАС</b> (рыночный минимум)\n\n"
            "✅ <i>Теперь бот будет присылать вам такие алерты сразу при срабатывании порогов ваших отелей из Watchlist!</i>"
        )

        if not token:
            logger.info(f"[MOCK TG TEST] Token not set. Target chat_id: {cleaned_chat_id}")
            return {
                "success": True,
                "simulated": True,
                "message": (
                    f"Chat ID '{cleaned_chat_id}' сохранён! "
                    "Внимание: токен бота на сервере пока в тестовом режиме (TELEGRAM_BOT_TOKEN). "
                    "Уведомления готовы к отправке при добавлении токена."
                ),
                "chat_id": cleaned_chat_id,
            }

        tg_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": cleaned_chat_id,
            "text": text_message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(tg_url, json=payload)
                data = resp.json() if resp.status_code == 200 else {}
                
                if resp.status_code == 200 and data.get("ok"):
                    logger.info(f"Test Telegram alert delivered to {cleaned_chat_id}")
                    return {
                        "success": True,
                        "simulated": False,
                        "message": "Тестовое уведомление успешно доставлено в ваш Telegram!",
                        "chat_id": cleaned_chat_id,
                    }

                # Handle Telegram API errors
                err_desc = resp.json().get("description", resp.text) if resp.status_code != 200 else "Unknown error"
                logger.warning(f"Telegram API error for chat {cleaned_chat_id}: {err_desc}")
                
                if "chat not found" in err_desc.lower():
                    friendly_err = (
                        "Chat ID не найден. Убедитесь, что вы открыли диалог с ботом "
                        "и нажали /start перед проверкой."
                    )
                elif "bot was blocked by the user" in err_desc.lower():
                    friendly_err = "Бот заблокирован в вашем Telegram. Пожалуйста, разблокируйте его."
                else:
                    friendly_err = f"Ошибка Telegram API: {err_desc}"

                return {
                    "success": False,
                    "simulated": False,
                    "message": friendly_err,
                    "chat_id": cleaned_chat_id,
                }
        except Exception as e:
            logger.error(f"Network error sending Telegram test alert to {cleaned_chat_id}: {e}")
            return {
                "success": False,
                "simulated": False,
                "message": f"Ошибка сети при обращении к Telegram API: {str(e)}",
                "chat_id": cleaned_chat_id,
            }

    @classmethod
    async def send_watchlist_alert(
        cls,
        chat_id: str,
        hotel_name: str,
        country: str,
        current_price: float,
        previous_price: float,
        drop_pct: float,
        dates: str,
        duration_nights: int,
        airport: str,
        deal_score: int,
        deal_badge: str,
        booking_url: Optional[str] = None,
        target_reached: bool = False,
        target_price: Optional[float] = None,
    ) -> bool:
        """Dispatches an actual price drop alert for a watched hotel."""
        token = cls.get_bot_token()
        if not token:
            logger.info(f"[MOCK WATCHLIST ALERT -> {chat_id}]: {hotel_name} dropped to {current_price:.0f} PLN")
            return True

        drop_diff = previous_price - current_price
        target_text = f"\n🎯 <b>Целевая цена достигнута:</b> {target_price:.0f} zł" if target_reached and target_price else ""

        text = (
            f"🔔 <b>СНИЖЕНИЕ ЦЕНЫ НА ОТЕЛЬ!</b>\n\n"
            f"🏨 <b>{hotel_name}</b>\n"
            f"📍 {country} • ✈️ {airport} ({duration_nights} ночей) • 📅 {dates}\n\n"
            f"💰 <s>{previous_price:.0f} zł</s> ➔ <b>{current_price:.0f} zł</b> (<b>-{drop_diff:.0f} zł / -{drop_pct:.1f}%</b>)"
            f"{target_text}\n"
            f"🎯 Deal Score: <b>{deal_score}/100</b> ({deal_badge})\n"
        )
        if booking_url:
            text += f"\n🔗 <a href='{booking_url}'>Посмотреть предложение на Fly.pl</a>"

        tg_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(tg_url, json=payload)
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Error dispatching watchlist alert to {chat_id}: {e}")
            return False
