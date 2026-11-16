import logging
import os
import httpx
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("travel_monitor_2.telegram")


class TelegramService:
    """Service for sending rich Telegram notifications, test alerts, and watchlist drops."""

    ARCHETYPES = {
        "LATE_DUMPER": {
            "title": "📉 LATE DUMPER (Отель-сбрасыватель)",
            "tip": "Часто делает резкие сбросы цен за 3–5 дней до вылета. Рекомендуется выжидать, если даты вылета гибкие.",
        },
        "ROCK_SOLID": {
            "title": "🛡️ ROCK SOLID (Устойчивая цена)",
            "tip": "Цены стабильны, скидки бывают крайне редко. При падении цены стоит бронировать сразу.",
        },
        "VOLATILE": {
            "title": "⚡ VOLATILE (Высокая волатильность)",
            "tip": "Частые колебания цен в чартерах. Окно выгодной цены может закрыться за считанные часы.",
        },
    }

    @classmethod
    def get_bot_token(cls) -> Optional[str]:
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if token and not token.startswith("dummy"):
            return token.strip()
        return None

    @classmethod
    def infer_archetype(cls, stars: int = 4, drop_pct: float = 0.0) -> str:
        """Infers behavioral archetype based on hotel classification and volatility."""
        if drop_pct >= 15.0:
            return "LATE_DUMPER"
        elif stars >= 5:
            return "ROCK_SOLID"
        return "VOLATILE"

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
            "🔔 <b>Пример умного AI-алерта при падении цены:</b>\n"
            "🏨 <b>Pickalbatros Palace Resort 5★</b>\n"
            "📍 Египет, Шарм-эль-Шейх • 🌊 1-я линия • 🔥 Подогрев\n"
            "✈️ Вылет: <b>2026-12-20</b> (7 ночей) • Варшава (WAW)\n"
            "💰 Цена: <s>8 450 zł</s> ➔ <b>6 950 zł</b> (<b>-1 500 zł / -18%</b>)\n"
            "⚖️ Сезонная норма: <b>7 800 zł</b> (на 11% выгоднее нормы сезона)\n"
            "🧬 Поведение: <b>🛡️ ROCK SOLID (Устойчивая цена)</b>\n"
            "💡 <i>Цены стабильны, скидки бывают крайне редко. При падении стоит бронировать сразу.</i>\n"
            "🎯 Deal Score: <b>92/100 🔥 Hot Deal!</b>\n"
            "🔮 Прогноз Hopper AI: 🟢 <b>ПОКУПАТЬ СЕЙЧАС</b> (рыночный минимум за 45 дней)\n\n"
            "✅ <i>Теперь бот будет присылать вам такие расширенные алерты с анализом сезонной нормы и поведения отеля!</i>"
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
        seasonal_norm: Optional[float] = None,
        archetype: Optional[str] = None,
        urgency_text: Optional[str] = None,
    ) -> bool:
        """Dispatches an actual price drop alert for a watched hotel."""
        token = cls.get_bot_token()
        if not token:
            logger.info(f"[MOCK WATCHLIST ALERT -> {chat_id}]: {hotel_name} dropped to {current_price:.0f} PLN")
            return True

        drop_diff = previous_price - current_price
        target_text = f"\n🎯 <b>Целевая цена достигнута:</b> {target_price:.0f} zł" if target_reached and target_price else ""

        norm_line = ""
        if seasonal_norm and seasonal_norm > 0:
            diff_pct = ((current_price - seasonal_norm) / seasonal_norm) * 100
            sign = "+" if diff_pct > 0 else ""
            norm_line = f"⚖️ Сезонная норма: <b>{seasonal_norm:,.0f} zł</b> ({sign}{diff_pct:.0f}% к норме сезона)\n".replace(",", " ")

        arch_key = archetype or cls.infer_archetype(stars=4, drop_pct=drop_pct)
        arch_data = cls.ARCHETYPES.get(arch_key, cls.ARCHETYPES["VOLATILE"])
        archetype_line = f"🧬 Поведение: <b>{arch_data['title']}</b>\n💡 <i>{arch_data['tip']}</i>\n"

        urgency_line = f"🔮 Прогноз Hopper AI: <b>{urgency_text}</b>\n" if urgency_text else ""

        text = (
            f"🔔 <b>СНИЖЕНИЕ ЦЕНЫ НА ОТЕЛЬ!</b>\n\n"
            f"🏨 <b>{hotel_name}</b>\n"
            f"📍 {country} • ✈️ {airport} ({duration_nights} ночей) • 📅 {dates}\n\n"
            f"💰 <s>{previous_price:.0f} zł</s> ➔ <b>{current_price:.0f} zł</b> (<b>-{drop_diff:.0f} zł / -{drop_pct:.1f}%</b>)\n"
            f"{norm_line}"
            f"{target_text}"
            f"{archetype_line}"
            f"🎯 Deal Score: <b>{deal_score}/100</b> ({deal_badge})\n"
            f"{urgency_line}"
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

    @classmethod
    async def send_dashboard_alert(
        cls,
        chat_id: str,
        monitor_title: str,
        hotel_name: str,
        country: str,
        current_price: float,
        previous_price: Optional[float] = None,
        drop_pct: Optional[float] = None,
        deal_score: int = 80,
        deal_badge: str = "Good Deal",
        dates: str = "Скоро",
        duration_nights: int = 7,
        airport: str = "WAW",
        is_historic_low: bool = False,
        booking_url: Optional[str] = None,
        is_test: bool = False,
        seasonal_norm: Optional[float] = None,
        archetype: Optional[str] = None,
        urgency_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sends an alert for a specific monitor/dashboard price drop."""
        token = cls.get_bot_token()
        prefix = "⚡ <b>ТЕСТОВЫЙ АЛЕРТ МОНИТОРИНГА</b>\n" if is_test else "🔔 <b>АЛЕРТ СНИЖЕНИЯ ЦЕНЫ!</b>\n"
        hist_low_text = "🏆 <b>РЕКОРД: Абсолютный исторический минимум!</b>\n" if is_historic_low else ""

        if previous_price and drop_pct:
            diff = previous_price - current_price
            price_text = f"💰 <s>{previous_price:,.0f} zł</s> ➔ <b>{current_price:,.0f} zł</b> (<b>-{diff:,.0f} zł / -{drop_pct:.1f}%</b>)\n".replace(",", " ")
        else:
            price_text = f"💰 Лучшая цена: <b>{current_price:,.0f} zł</b>\n".replace(",", " ")

        norm_line = ""
        if seasonal_norm and seasonal_norm > 0:
            diff_pct = ((current_price - seasonal_norm) / seasonal_norm) * 100
            sign = "+" if diff_pct > 0 else ""
            norm_line = f"⚖️ Сезонная норма: <b>{seasonal_norm:,.0f} zł</b> ({sign}{diff_pct:.0f}% к норме сезона)\n".replace(",", " ")

        arch_key = archetype or cls.infer_archetype(stars=4, drop_pct=drop_pct or 0.0)
        arch_data = cls.ARCHETYPES.get(arch_key, cls.ARCHETYPES["VOLATILE"])
        archetype_line = f"🧬 Поведение: <b>{arch_data['title']}</b>\n💡 <i>{arch_data['tip']}</i>\n"

        urgency_line = f"🔮 Прогноз Hopper AI: <b>{urgency_text}</b>\n" if urgency_text else ""

        text = (
            f"{prefix}"
            f"📡 Мониторинг: <b>{monitor_title}</b>\n\n"
            f"🏨 <b>{hotel_name}</b>\n"
            f"📍 {country} • ✈️ {airport} ({duration_nights} ночей) • 📅 {dates}\n\n"
            f"{price_text}"
            f"{norm_line}"
            f"{hist_low_text}"
            f"{archetype_line}"
            f"🎯 Deal Score: <b>{deal_score}/100</b> ({deal_badge})\n"
            f"{urgency_line}"
        )
        if booking_url:
            text += f"\n🔗 <a href='{booking_url}'>Посмотреть предложение на Fly.pl</a>"

        if not token:
            logger.info(f"[MOCK DASHBOARD ALERT -> {chat_id}]: {monitor_title} - {hotel_name} @ {current_price:.0f} PLN")
            return {
                "success": True,
                "simulated": True,
                "message": f"Тестовый алерт для мониторинга '{monitor_title}' сгенерирован (симуляция без токена бота).",
                "chat_id": chat_id,
            }

        tg_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": str(chat_id).strip(),
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(tg_url, json=payload)
                if resp.status_code == 200:
                    return {
                        "success": True,
                        "simulated": False,
                        "message": f"Алерт мониторинга '{monitor_title}' успешно отправлен в Telegram!",
                        "chat_id": chat_id,
                    }
                err_desc = resp.json().get("description", resp.text)
                return {
                    "success": False,
                    "simulated": False,
                    "message": f"Ошибка Telegram: {err_desc}",
                    "chat_id": chat_id,
                }
        except Exception as e:
            return {
                "success": False,
                "simulated": False,
                "message": f"Сетевая ошибка: {str(e)}",
                "chat_id": chat_id,
            }

    @classmethod
    async def send_daily_digest(
        cls,
        chat_id: str,
        user_name: Optional[str],
        watchlist_items: list,
        top_drops: list,
        hot_deals: list,
        historic_lows: list,
        max_offers: int = 5,
        is_test: bool = False,
    ) -> Dict[str, Any]:
        """Formats and delivers a comprehensive Daily Market Digest."""
        token = cls.get_bot_token()
        title_prefix = "⚡ <b>ТЕСТОВЫЙ ЕЖЕДНЕВНЫЙ ДАЙДЖЕСТ</b>" if is_test else "🌅 <b>TRAVEL MONITOR 2.0 • УТРЕННИЙ ДАЙДЖЕСТ</b>"
        greeting = f"Привет, {user_name or 'Путешественник'}! 👋\nВот свежая сводка по вашим радарам и рынку:"

        sections = [f"{title_prefix}\n{greeting}\n"]

        # 1. Watchlist Section
        if watchlist_items:
            sections.append("🏨 <b>Ваш Watchlist (Избранное):</b>")
            for item in watchlist_items[:max_offers]:
                name = item.get("hotel_name", "Отель")
                country = item.get("country", "")
                price = item.get("current_price_pln", 0)
                prev = item.get("initial_price_pln")
                diff_str = ""
                if prev and prev > price:
                    diff_str = f" (<b>-{prev - price:.0f} zł</b>)"
                score = item.get("deal_score", 0)
                sections.append(f"• <b>{name}</b> ({country}): <b>{price:,.0f} zł</b>{diff_str} • Score {score}".replace(",", " "))
            sections.append("")

        # 2. Top Drops Section
        if top_drops:
            sections.append("📉 <b>Топ падений за сутки:</b>")
            for drop in top_drops[:max_offers]:
                name = drop.get("hotel_name", "Отель")
                curr = drop.get("current_price_pln", 0)
                prev = drop.get("previous_price_pln", 0)
                diff = prev - curr if prev else 0
                pct = drop.get("drop_pct", 0)
                sections.append(f"• <b>{name}</b>: <s>{prev:,.0f} zł</s> ➔ <b>{curr:,.0f} zł</b> (<b>-{diff:,.0f} zł / -{pct:.1f}%</b>)".replace(",", " "))
            sections.append("")

        # 3. Hot Deals Section
        if hot_deals:
            sections.append("🔥 <b>Лучшие Hot Deals:</b>")
            for deal in hot_deals[:max_offers]:
                name = deal.get("hotel_name", "Отель")
                price = deal.get("price_pln", 0)
                score = deal.get("deal_score", 0)
                country = deal.get("country", "")
                sections.append(f"• <b>{name}</b> ({country}): <b>{price:,.0f} zł</b> • Score <b>{score}/100</b>".replace(",", " "))
            sections.append("")

        # 4. Historic Lows
        if historic_lows:
            sections.append("🏆 <b>Рекордные исторические минимумы:</b>")
            for low in historic_lows[:max_offers]:
                name = low.get("hotel_name", "Отель")
                price = low.get("price_pln", 0)
                sections.append(f"• <b>{name}</b>: рекордная цена <b>{price:,.0f} zł</b>!".replace(",", " "))
            sections.append("")

        if len(sections) == 1:
            sections.append("ℹ️ На рынке сейчас штиль: новых резких колебаний цен или горящих туров не зафиксировано.\n")

        sections.append("⚙️ <i>Вы всегда можете изменить время и состав дайджеста в настройках профиля.</i>")
        full_text = "\n".join(sections)

        if not token:
            logger.warning(f"⚠️ [TELEGRAM_BOT_TOKEN MISSING]: Cannot deliver daily digest to {chat_id}. Ensure TELEGRAM_BOT_TOKEN is set in GitHub Secrets.")
            return {
                "success": bool(is_test),
                "simulated": True,
                "message": "Ежедневный дайджест сформирован в режиме симуляции (TELEGRAM_BOT_TOKEN не задан).",
                "chat_id": chat_id,
            }

        tg_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": str(chat_id).strip(),
            "text": full_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(tg_url, json=payload)
                if resp.status_code == 200:
                    return {
                        "success": True,
                        "simulated": False,
                        "message": "Ежедневный дайджест успешно доставлен в ваш Telegram!",
                        "chat_id": chat_id,
                    }
                err_desc = resp.json().get("description", resp.text)
                return {
                    "success": False,
                    "simulated": False,
                    "message": f"Ошибка Telegram: {err_desc}",
                    "chat_id": chat_id,
                }
        except Exception as e:
            return {
                "success": False,
                "simulated": False,
                "message": f"Сетевая ошибка: {str(e)}",
                "chat_id": chat_id,
            }


