import logging
import os
import re
import html
import httpx
from typing import Dict, Any, Optional
from app.config import settings
from app.services.canonical_filters import resolve_filter_spec

logger = logging.getLogger("travel_monitor_2.telegram")


def sanitize_hotel_name(name: str) -> str:
    """Cleans up raw hotel display names, removing broken unclosed parens or trailing colons."""
    if not name:
        return "Отель"
    name = name.strip()
    # Remove unclosed trailing parentheses e.g. '(Ex. Lilly:' or '(ex.Roma Hos'
    name = re.sub(r"\s*\([^)]*$", "", name).strip()
    # Remove trailing colons, dashes or punctuation
    name = re.sub(r"[:,\-–—\s]+$", "", name).strip()
    return name or "Отель"


def format_departure_date(d_val: Any) -> str:
    """Formats departure date into friendly short Russian format, e.g. '22 дек'."""
    if not d_val:
        return ""
    months = {
        1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "мая", 6: "июн",
        7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек"
    }
    try:
        s = str(d_val).split("T")[0]
        if "-" in s:
            parts = s.split("-")
            m, d = int(parts[1]), int(parts[2])
            return f"{d} {months.get(m, str(m))}"
        return s
    except Exception:
        return str(d_val)


def clean_filter_title(t: Optional[str]) -> str:
    """Simplifies filter monitor titles for compact Telegram badge display."""
    if not t:
        return ""
    clean_k = str(t).strip().lower()
    spec = resolve_filter_spec(clean_k)
    if spec and "title" in spec:
        if clean_k.startswith("benchmark_") or clean_k.startswith("filter_") or clean_k.startswith("eb_"):
            t = spec["title"]
    t = str(t).replace(" • ", " ").replace(" ночей", "н").replace(" дней", "дн").strip()
    return t


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
        last_minute_deals: Optional[list] = None,
        max_offers: int = 5,
        is_test: bool = False,
    ) -> Dict[str, Any]:
        """Formats and delivers a comprehensive Daily Market Digest with clickable links and rich metadata."""
        token = cls.get_bot_token()
        title_prefix = "⚡ <b>ТЕСТОВЫЙ ЕЖЕДНЕВНЫЙ ДАЙДЖЕСТ</b>" if is_test else "🌅 <b>TRAVEL MONITOR 2.0 • УТРЕННИЙ ДАЙДЖЕСТ</b>"
        greeting = f"Привет, {user_name or 'Путешественник'}! 👋\nВот свежая сводка по вашим радарам и рынку туров:"

        sections = [f"{title_prefix}\n<i>{greeting}</i>\n"]

        def format_card(item: dict, kind: str) -> str:
            name = sanitize_hotel_name(item.get("hotel_name", "Отель"))
            stars = item.get("stars")
            stars_str = f" {stars}★" if stars else ""
            ta = item.get("ta_rating")
            ta_str = f" (TA {ta:.1f}★)" if ta and ta > 0 else ""

            url = item.get("offer_url") or "https://fly.pl/"
            safe_name = html.escape(name)
            title_line = f'• <a href="{url}"><b>{safe_name}{stars_str}</b></a>{ta_str}'

            country = item.get("country", "")
            region = item.get("region", "")
            loc = f"{country}, {region}" if region and region.lower() != country.lower() else country

            nights = item.get("duration_nights", 7) or 7
            adults = item.get("adults", 2) or 2
            children = item.get("children", 0) or 0

            # Guard / Canonical resolution for traveler composition (pax)
            filter_id_raw = str(item.get("filter_id") or "").lower()
            filter_title_raw = str(item.get("filter_title") or "").lower()
            url_raw = str(item.get("offer_url") or "").lower()

            spec = None
            if filter_id_raw:
                spec = resolve_filter_spec(filter_id_raw)
            if not spec and filter_title_raw:
                spec = resolve_filter_spec(filter_title_raw)

            if spec and "adults" in spec:
                adults = int(spec["adults"])
                children = int(spec.get("children", 0))
            elif any(k in filter_id_raw for k in ["1p", "cyprus_7_10", "cyprus_1p"]) or \
                 any(k in filter_title_raw for k in ["1 взр", "1p", "1 взрослый", "эталон"]) or \
                 "adults=1" in url_raw or "person%5d=1" in url_raw or "person=1" in url_raw:
                adults = 1
                children = 0
            elif "adults=2" in url_raw and "children=" not in url_raw and "child=" not in url_raw and "childage" not in url_raw and "2+1" not in filter_title_raw and "2+1" not in filter_id_raw:
                if children > 0 and ("1 реб" not in filter_title_raw and "+1" not in filter_title_raw):
                    children = 0

            pax = "1 взр." if adults == 1 and children == 0 else f"{adults} взр. + {children} реб." if children else f"{adults} взр."
            dep_date = format_departure_date(item.get("departure_date") or item.get("checkin_date"))
            airport = item.get("airport_code") or item.get("airport") or ""

            params = [loc, f"{nights} ночей", pax]
            if dep_date:
                params.append(f"вылет {dep_date}")
            if airport:
                params.append(f"({airport})")
            subline = "  📍 " + " • ".join(p for p in params if p)

            curr_price = item.get("current_price_pln") or item.get("price_pln") or 0.0
            price_str = f"{curr_price:,.0f} zł".replace(",", " ")
            ppn_str = f"{curr_price / max(1, nights):,.0f} zł/н".replace(",", " ")

            raw_title = item.get("filter_title")
            filter_label = clean_filter_title(raw_title)
            filter_line = f"\n  🎯 Фильтр: <i>{html.escape(filter_label)}</i>" if filter_label else ""

            if kind == "watchlist":
                prev = item.get("initial_price_pln")
                diff_str = ""
                if prev and prev > curr_price:
                    diff_str = f" (📉 <b>-{prev - curr_price:,.0f} zł</b>)".replace(",", " ")
                target = item.get("target_price_pln")
                target_str = f" • цель: {target:,.0f} zł".replace(",", " ") if target else ""
                score = item.get("deal_score")
                score_str = f" • Deal Score: <b>{score}</b>" if score else ""
                price_line = f"  💰 <b>{price_str}</b> ({ppn_str}){diff_str}{target_str}{score_str}"

            elif kind == "drop":
                prev_price = item.get("previous_price_pln", 0.0)
                prev_str = f"{prev_price:,.0f} zł".replace(",", " ")
                drop_pln = item.get("drop_pln") or (prev_price - curr_price)
                drop_pct = item.get("drop_pct") or ((prev_price - curr_price) / prev_price * 100 if prev_price else 0)
                drop_str = f"-{drop_pln:,.0f} zł / -{drop_pct:.1f}%".replace(",", " ")
                price_line = f"  💰 <s>{prev_str}</s> ➔ <b>{price_str}</b> (<b>{drop_str}</b> • {ppn_str})"

            elif kind == "hot_deal":
                score = item.get("deal_score") or 88
                price_line = f"  💰 <b>{price_str}</b> ({ppn_str}) • Deal Score: <b>{score}/100</b> 🔥"

            elif kind == "last_minute":
                score = item.get("deal_score") or 90
                h_verdict = item.get("horizon_verdict") or {}
                h_line = ""
                if h_verdict and h_verdict.get("type") == "REAL_DUMP":
                    saved = h_verdict.get("savings_vs_standard_pln") or 0
                    pct = h_verdict.get("savings_vs_standard_pct") or 0
                    h_line = f"\n  ⚖️ <i>Горизонты: на -{pct:.0f}% (-{saved:,.0f} zł) дешевле цены за месяц! Честный сброс!</i> 🔥".replace(",", " ")
                elif h_verdict and h_verdict.get("type") == "FAKE_LAST_MINUTE":
                    h_line = "\n  ⚖️ <i>Горизонты: стандартная цена без горящей скидки</i>"
                elif h_verdict and h_verdict.get("type") == "URGENT_SURCHARGE":
                    pct = abs(h_verdict.get("savings_vs_standard_pct") or 0)
                    h_line = f"\n  ⚠️ <i>Горизонты: наценка +{pct:.0f}% за срочность</i>"
                price_line = f"  ⚡ <b>{price_str}</b> ({ppn_str}) • срочный вылет {dep_date}! (Score: <b>{score}</b>) 🔥{h_line}"

            elif kind == "historic_low":
                price_line = f"  💰 <b>{price_str}</b> ({ppn_str}) — <i>абсолютный ценовой рекорд!</i> 🏆"
            else:
                price_line = f"  💰 <b>{price_str}</b> ({ppn_str})"

            return f"{title_line}\n{subline}\n{price_line}{filter_line}"

        # 0. Last Minute Flash Section (Urgent departures in 0..4 days)
        if last_minute_deals:
            sections.append("⚡ <b>Горящие вылеты (ближайшие 72–96 часов):</b>")
            for deal in last_minute_deals[:max_offers]:
                sections.append(format_card(deal, "last_minute"))
            sections.append("")

        # 1. Watchlist Section
        if watchlist_items:
            sections.append("🏨 <b>Ваш Watchlist (Избранное):</b>")
            for item in watchlist_items[:max_offers]:
                sections.append(format_card(item, "watchlist"))
            sections.append("")

        # 2. Top Drops Section
        if top_drops:
            sections.append("📉 <b>Топ падений за 24–48 часов:</b>")
            for drop in top_drops[:max_offers]:
                sections.append(format_card(drop, "drop"))
            sections.append("")

        # 3. Hot Deals Section
        if hot_deals:
            sections.append("🔥 <b>Лучшие Hot Deals:</b>")
            for deal in hot_deals[:max_offers]:
                sections.append(format_card(deal, "hot_deal"))
            sections.append("")

        # 4. Historic Lows
        if historic_lows:
            sections.append("🏆 <b>Рекордные исторические минимумы:</b>")
            for low in historic_lows[:max_offers]:
                sections.append(format_card(low, "historic_low"))
            sections.append("")

        if len(sections) == 1:
            sections.append("ℹ️ На рынке сейчас штиль: новых резких колебаний цен или горящих туров не зафиксировано.\n")

        sections.append("━━━━━━━━━━━━━━━━━━")
        sections.append('🌐 <a href="https://jancker2a.github.io/travel-monitoring/"><b>Открыть интерактивные радары и графики</b></a>')
        sections.append("⚙️ <i>Вы всегда можете изменить состав дайджеста и фильтры в профиле.</i>")
        full_text = "\n".join(sections)

        if not token:
            logger.warning(f"⚠️ [TELEGRAM_BOT_TOKEN MISSING]: Cannot deliver daily digest to {chat_id}. Ensure TELEGRAM_BOT_TOKEN is set in GitHub Secrets.")
            return {
                "success": bool(is_test),
                "simulated": True,
                "message": "Ежедневный дайджест сформирован в режиме симуляции (TELEGRAM_BOT_TOKEN не задан).",
                "chat_id": chat_id,
                "text": full_text,
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


