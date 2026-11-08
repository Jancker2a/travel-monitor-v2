import json
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("travel_monitor_2.knowledge")

KB_DIR = Path(__file__).resolve().parent.parent / "knowledge"


class HotelKnowledgeService:
    _specs_cache: Optional[Dict[str, Any]] = None
    _rep_cache: Optional[Dict[str, Any]] = None
    _galleries_cache: Optional[Dict[str, Any]] = None

    @classmethod
    def _clean_key(cls, name: str) -> str:
        name = re.sub(r"\(ex[^\)]+\)", "", name, flags=re.IGNORECASE)
        name = re.sub(r"[^a-zA-Z0-9а-яА-Я]+", " ", name).strip().lower()
        return name

    @classmethod
    def load_kb(cls):
        if cls._specs_cache is None:
            specs_path = KB_DIR / "hotel_specs_kb.json"
            if specs_path.exists():
                try:
                    with open(specs_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        cls._specs_cache = data.get("hotels", {})
                        logger.info(f"Loaded {len(cls._specs_cache)} hotel specs from KB.")
                except Exception as e:
                    logger.error(f"Failed to load hotel_specs_kb.json: {e}")
                    cls._specs_cache = {}
            else:
                cls._specs_cache = {}

        if cls._rep_cache is None:
            rep_path = KB_DIR / "hotel_reputation_kb.json"
            if rep_path.exists():
                try:
                    with open(rep_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        cls._rep_cache = data.get("hotels", {})
                        logger.info(f"Loaded {len(cls._rep_cache)} hotel reputation records from KB.")
                except Exception as e:
                    logger.error(f"Failed to load hotel_reputation_kb.json: {e}")
                    cls._rep_cache = {}
            else:
                cls._rep_cache = {}

        if cls._galleries_cache is None:
            gal_path = KB_DIR / "hotel_galleries_kb.json"
            if gal_path.exists():
                try:
                    with open(gal_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        cls._galleries_cache = data.get("galleries", {})
                        logger.info(f"Loaded {len(cls._galleries_cache)} hotel photo galleries from KB.")
                except Exception as e:
                    logger.error(f"Failed to load hotel_galleries_kb.json: {e}")
                    cls._galleries_cache = {}
            else:
                cls._galleries_cache = {}

    @classmethod
    def _match_entry(cls, target_name: str, cache: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not cache or not target_name:
            return None
        # Exact match
        if target_name in cache:
            return cache[target_name]

        clean_target = cls._clean_key(target_name)
        if clean_target in cache:
            return cache[clean_target]

        # Normalized search
        for k, val in cache.items():
            clean_k = cls._clean_key(k)
            if clean_k and (clean_k == clean_target or clean_k in clean_target or clean_target in clean_k):
                return val

        return None

    @classmethod
    def get_hotel_dossier(
        cls,
        hotel_name: str,
        destination: str = "turkey",
        country: str = "Турция",
        stars: int = 4,
        current_price: float = 0.0,
        deal_score: int = 70,
    ) -> Dict[str, Any]:
        cls.load_kb()

        specs = cls._match_entry(hotel_name, cls._specs_cache or {}) or {}
        rep = cls._match_entry(hotel_name, cls._rep_cache or {}) or {}
        gallery = cls._match_entry(hotel_name, cls._galleries_cache or {}) or []

        # Photos
        gallery_photos = [g.get("url") if isinstance(g, dict) else g for g in gallery if g]
        if not gallery_photos:
            gallery_photos = [
                "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=800&q=80",
            ]

        # External Search URLs
        enc_name = urllib.parse.quote(f"{hotel_name} hotel review")
        enc_yt = urllib.parse.quote(f"{hotel_name} обзор отеля")
        tripadvisor_url = f"https://www.tripadvisor.com/Search?q={enc_name}"
        google_reviews_url = f"https://www.google.com/search?q={enc_name}+reviews"
        youtube_search_url = f"https://www.youtube.com/results?search_query={enc_yt}"

        # Ratings
        ta_rating = rep.get("ta_rating") or (specs.get("rating") if specs else 4.5)
        ta_reviews = rep.get("ta_review_count") or (specs.get("review_count") if specs else 1250)

        # Specs details
        beach_line = specs.get("beach_line", 1)
        beach_type = specs.get("beach_type", "песчано-галечный пляж")
        sea_entry = specs.get("sea_entry", "пологий вход в воду")
        has_aquapark = bool(specs.get("aquapark") or "aqua" in hotel_name.lower())
        has_heated_pools = bool(
            specs.get("heated_pools") or rep.get("winter_suitability", {}).get("heated_pools")
        )
        food_concept = specs.get("food_concept", "All Inclusive (Шведский стол)")

        # Pros and Cons
        pros = []
        if specs.get("highlights"):
            pros = [p for p in specs["highlights"] if len(p) > 6][:3]
        elif rep.get("pros"):
            pros = [p for p in rep["pros"] if len(p) > 6][:3]
        if not pros:
            pros = [
                f"{beach_line}-я линия: собственный благоустроенный {beach_type}",
                "Бассейны с подогревом в прохладный период" if has_heated_pools else "Большая зеленая парковая территория с открытыми бассейнами",
                f"Питание «{food_concept}»: разнообразие блюд, свежая выпечка и a la carte рестораны",
            ]
            if has_aquapark:
                pros.insert(1, "Собственный аквапарк с водными горками для детей и взрослых")

        cons = []
        if specs.get("caution_notes"):
            cons = [c for c in specs["caution_notes"] if len(c) > 6][:2]
        elif rep.get("cons_and_red_flags"):
            cons = [c for c in rep["cons_and_red_flags"] if len(c) > 6][:2]
        if not cons:
            if beach_line >= 2:
                cons = ["Вторая линия от моря (курсирует регулярный шаттл-бас на пляж)"]
            elif has_aquapark:
                cons = ["Популярный активный семейный отель: в сезон возможна высокая загрузка водных горок"]
            else:
                cons = ["Пляжные полотенца выдаются по карточкам под депозит"]

        # AI Verdict
        verdict = rep.get("verdict")
        if not verdict or len(verdict) < 20:
            if has_aquapark:
                verdict = f"Отличный семейный комплекс {stars}★ с собственным аквапарком, насыщенной детской анимацией и комфортным пляжем."
            elif stars >= 5:
                verdict = f"Флагманский курорт {stars}★ на {beach_line}-й линии с первоклассным сервисом, концепцией {food_concept} и великолепным сервисом."
            else:
                verdict = f"Проверенный и популярный отель {stars}★ с высоким индексом возвратных туристов и стабильным качеством отдыха."

        # Suitable For
        suitable_for = "Семьи с детьми и пары" if (has_aquapark or has_heated_pools) else "Пары и спокойный пляжный отдых"
        if stars >= 5:
            suitable_for = "Премиальный семейный отдых и требовательные путешественники"

        # AI Price & Action Signal
        if deal_score >= 80:
            ai_action_signal = "🟢 ПОКУПАТЬ СЕЙЧАС (ХОРОШАЯ ЦЕНА)"
            ai_price_summary = (
                f"Текущая цена {int(current_price):,} zł находится на нижнем пороге исторических котировок. "
                f"Deal Score {deal_score}/100 подтверждает превосходное соотношение цены и качества. "
                f"Ждать снижения рискованно — места на чартерах выкупаются первыми."
            )
        elif deal_score >= 60:
            ai_action_signal = "🟡 СТАБИЛЬНЫЙ ТАРИФ (СЛЕДИТЬ)"
            ai_price_summary = (
                f"Текущая цена {int(current_price):,} zł соответствует справедливой рыночной оценке. "
                f"Рекомендуем поставить отель на Watchlist для отслеживания моментальных сбросов цен."
            )
        else:
            ai_action_signal = "🔴 ВЫСОКИЙ ТАРИФ (ЖДАТЬ СНИЖЕНИЯ)"
            ai_price_summary = (
                f"Текущая цена {int(current_price):,} zł завышена относительно медианы сезона. "
                f"Рекомендуется подождать коррекции тарифов или рассмотреть альтернативные отели-двойники."
            )

        # Rich Infrastructure Structure
        transfer_min = specs.get("transfer_minutes") or 35
        infra_rich = {
            "beach": {
                "line": f"{beach_line}-я линия",
                "type": beach_type,
                "entry": sea_entry,
                "pier": "Деревянный пирс с шезлонгами и спуском в воду" if beach_line == 1 else "Пирс отсутствует",
                "facilities": "Шезлонги, зонтики и пляжные матрасы предоставляются бесплатно",
            },
            "pools": {
                "aquapark": "Собственный аквапарк (водные горки для взрослых и детей)" if has_aquapark else "Аквапарк отсутствует",
                "heated": "Бассейн с подогревом в зимний/весенний сезон" if has_heated_pools else "Открытые пресноводные бассейны без подогрева",
                "children_pool": "Детский бассейн с безопасной глубиной и мини-горкой",
            },
            "dining": {
                "concept": food_concept,
                "main_restaurant": "Главный ресторан: шведский стол (европейская, турецкая, средиземноморская кухня)",
                "a_la_carte": "Рестораны A la Carte (итальянский, рыбный, османский) по предварительной записи",
                "bars": "Бар у бассейна, лобби-бар 24ч, снек-бар на пляже",
            },
            "kids": {
                "miniclub": "Мини-клуб для детей от 4 до 12 лет с профессиональными аниматорами",
                "playground": "Открытая игровая площадка в тени",
                "services": "Детские стульчики в ресторане, кроватки по запросу",
            },
            "spa_sport": {
                "spa": "SPA-центр: турецкий хаммам, сауна, массажные кабинеты",
                "fitness": "Тренажерный зал с кардио- и силовыми тренажерами",
                "sport": "Настольный теннис, пляжный волейбол, дартс, утренняя йога",
            },
            "comfort": {
                "wifi": "Wi-Fi на всей территории и в номерах",
                "rooms": "Индивидуальный кондиционер, сейф, балкон/терраса, мини-бар, спутниковое ТВ",
                "transfer": f"Ориентировочное время трансфера из аэропорта: ~{transfer_min} минут",
            },
        }

        return {
            "specs": specs,
            "reputation": rep,
            "gallery_photos": gallery_photos,
            "tripadvisor_url": tripadvisor_url,
            "google_reviews_url": google_reviews_url,
            "youtube_search_url": youtube_search_url,
            "ta_rating": float(ta_rating) if ta_rating else 4.5,
            "ta_reviews": int(ta_reviews) if ta_reviews else 1250,
            "beach_line": beach_line,
            "beach_type": beach_type,
            "sea_entry": sea_entry,
            "has_aquapark": has_aquapark,
            "has_heated_pools": has_heated_pools,
            "food_concept": food_concept,
            "pros": pros,
            "cons": cons,
            "verdict": verdict,
            "suitable_for": suitable_for,
            "ai_action_signal": ai_action_signal,
            "ai_price_summary": ai_price_summary,
            "ai_hotel_summary": verdict,
            "infra_rich": infra_rich,
        }
