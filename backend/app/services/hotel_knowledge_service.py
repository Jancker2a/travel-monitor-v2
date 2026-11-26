import json
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.services.hotel_entity_matcher import (
    HotelEntityMatcher,
    _canonicalize_for_key,
    calculate_hotel_similarity,
    fold_unicode,
)

logger = logging.getLogger("travel_monitor_2.knowledge")

KB_DIR = Path(__file__).resolve().parent.parent / "knowledge"
_KB_MATCHER: Optional[HotelEntityMatcher] = None


def _get_kb_matcher() -> HotelEntityMatcher:
    global _KB_MATCHER
    if _KB_MATCHER is None:
        _KB_MATCHER = HotelEntityMatcher(similarity_threshold=0.82)
    return _KB_MATCHER


class HotelKnowledgeService:
    _specs_cache: Optional[Dict[str, Any]] = None
    _rep_cache: Optional[Dict[str, Any]] = None
    _galleries_cache: Optional[Dict[str, Any]] = None
    _images_cache: Optional[Dict[str, Any]] = None
    _clean_index_cache: Dict[int, Tuple[Dict[str, str], List[str]]] = {}

    @classmethod
    def _clean_key(cls, name: str) -> str:
        name = re.sub(r"\(ex[^\)]*(?:\)|$)", "", fold_unicode(name), flags=re.IGNORECASE)
        name = re.split(r"\b(?:egipt|turcja|grecja|cypr|bulgaria|hiszpania)\b", name, flags=re.IGNORECASE)[0]
        name = re.sub(r"[^a-z0-9а-я]+", " ", name).strip().lower()
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

        if cls._images_cache is None:
            img_path = KB_DIR / "hotel_images_kb.json"
            if img_path.exists():
                try:
                    with open(img_path, "r", encoding="utf-8") as f:
                        cls._images_cache = json.load(f)
                        logger.info(f"Loaded {len(cls._images_cache)} hotel images from KB.")
                except Exception as e:
                    logger.error(f"Failed to load hotel_images_kb.json: {e}")
                    cls._images_cache = {}
            else:
                cls._images_cache = {}

    @classmethod
    def _get_cache_index(cls, cache: Dict[str, Any]) -> Tuple[Dict[str, str], List[str]]:
        cid = id(cache)
        if cid in cls._clean_index_cache:
            return cls._clean_index_cache[cid]
        clean_map: Dict[str, str] = {}
        keys_list = list(cache.keys())
        for k in keys_list:
            ck = cls._clean_key(k)
            if ck and ck not in clean_map:
                clean_map[ck] = k
            canon_k = _canonicalize_for_key(k)
            if canon_k and canon_k not in clean_map:
                clean_map[canon_k] = k
        cls._clean_index_cache[cid] = (clean_map, keys_list)
        return clean_map, keys_list

    @classmethod
    def _match_entry(cls, target_name: str, cache: Dict[str, Any]) -> Optional[Any]:
        if not cache or not target_name:
            return None
        if target_name in cache:
            return cache[target_name]

        matcher = _get_kb_matcher()
        clean_map, keys_list = cls._get_cache_index(cache)
        variants = matcher.get_alias_variants(target_name)

        # 1. Exact / canonical normalized lookup across ALL rename aliases
        for v in variants:
            if v in cache:
                return cache[v]
            cv = cls._clean_key(v)
            if cv in clean_map:
                return cache[clean_map[cv]]
            canon_v = _canonicalize_for_key(v)
            if canon_v in clean_map:
                return cache[clean_map[canon_v]]

        # 2. High-precision entity matcher across aliases (geo & sub-property guarded)
        res = matcher.match_hotel(target_name, keys_list)
        if res:
            return cache.get(res[0])

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
        main_image_url: Optional[str] = None,
        db_specs: Optional[Dict[str, Any]] = None,
        db_reputation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        cls.load_kb()

        specs_raw = db_specs or cls._match_entry(hotel_name, cls._specs_cache or {}) or {}
        specs = specs_raw.get("specs", specs_raw) if isinstance(specs_raw, dict) else {}
        passport = specs.get("passport", {}) if isinstance(specs, dict) else {}
        rep = db_reputation or cls._match_entry(hotel_name, cls._rep_cache or {}) or {}
        gallery = cls._match_entry(hotel_name, cls._galleries_cache or {}) or []

        # Resolve primary image (passed from DB or matched from hotel_images_kb.json)
        resolved_main_img = main_image_url
        if not resolved_main_img:
            matched_img = cls._match_entry(hotel_name, cls._images_cache or {})
            if isinstance(matched_img, str) and matched_img:
                resolved_main_img = matched_img

        # Photos: prefer passport or specs gallery_photos if available
        raw_photos = passport.get("gallery_photos") or specs.get("gallery_photos") or gallery
        gallery_photos = [g.get("url") if isinstance(g, dict) else g for g in raw_photos if g]
        # Never inject or keep generic Unsplash fallback photos
        gallery_photos = [
            g for g in gallery_photos
            if isinstance(g, str)
            and not g.startswith("https://images.unsplash.com/photo-1566073771259")
            and not g.startswith("https://images.unsplash.com/photo-1582719478250")
            and not g.startswith("https://images.unsplash.com/photo-1571896349842")
            and not g.startswith("https://images.unsplash.com/photo-1540555700478")
        ]

        if resolved_main_img and resolved_main_img not in gallery_photos:
            gallery_photos = [resolved_main_img] + gallery_photos

        # External Search URLs
        enc_name = urllib.parse.quote(f"{hotel_name} hotel review")
        enc_yt = urllib.parse.quote(f"{hotel_name} обзор отеля")
        tripadvisor_url = f"https://www.tripadvisor.com/Search?q={enc_name}"
        google_reviews_url = f"https://www.google.com/search?q={enc_name}+reviews"
        youtube_search_url = f"https://www.youtube.com/results?search_query={enc_yt}"

        # Ratings
        ta_rating = (
            passport.get("ta_rating")
            or specs.get("tripadvisor_rating")
            or rep.get("ta_rating")
            or (specs.get("rating") if specs else None)
        )
        ta_reviews = (
            passport.get("ta_reviews")
            or specs.get("tripadvisor_reviews")
            or rep.get("ta_review_count")
            or (specs.get("review_count") if specs else None)
        )

        # Specs details
        beach_line = passport.get("beach_line") or specs.get("beach_line", 1)
        beach_type = passport.get("beach_type") or specs.get("beach_type", "песчано-галечный пляж")
        sea_entry = passport.get("sea_entry") or specs.get("sea_entry", "пологий вход в воду")
        has_aquapark = (
            passport.get("has_aquapark")
            if "has_aquapark" in passport
            else bool(
                specs.get("aquapark")
                or re.search(r"\b(aqua|aquapark|waterpark|water|slide|neverland|splash|fun city|аква)\b", hotel_name, re.I)
            )
        )
        has_heated_pools = (
            passport.get("has_heated_pools")
            if "has_heated_pools" in passport
            else bool(
                specs.get("heated_pools_winter")
                or specs.get("heated_pools")
                or rep.get("winter_suitability", {}).get("heated_pools")
            )
        )
        food_concept = passport.get("food_concept") or specs.get("food_concept", "All Inclusive (Шведский стол)")

        # Pros and Cons
        pros = []
        if passport.get("pros"):
            pros = [p for p in passport["pros"] if len(p) > 6][:3]
        elif specs.get("highlights"):
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
        if passport.get("cons"):
            cons = [c for c in passport["cons"] if len(c) > 6][:2]
        elif specs.get("caution_notes"):
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
        verdict = passport.get("verdict") or rep.get("verdict")
        if not verdict or len(verdict) < 20:
            if has_aquapark:
                verdict = f"Отличный семейный комплекс {stars}★ с собственным аквапарком, насыщенной детской анимацией и комфортным пляжем."
            elif stars >= 5:
                verdict = f"Флагманский курорт {stars}★ на {beach_line}-й линии с первоклассным сервисом, концепцией {food_concept} и великолепным сервисом."
            else:
                verdict = f"Проверенный и популярный отель {stars}★ с высоким индексом возвратных туристов и стабильным качеством отдыха."

        # Suitable For
        suitable_for = (
            passport.get("suitable_for")
            or rep.get("suitable_for")
            or ("Семьи с детьми и пары" if (has_aquapark or has_heated_pools) else "Пары и спокойный пляжный отдых")
        )
        if stars >= 5 and not passport.get("suitable_for"):
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

        # Rich Infrastructure Structure: prefer verified infra_rich from passport or specs
        infra_rich = passport.get("infra_rich") or specs.get("infrastructure")
        if not infra_rich or not isinstance(infra_rich, dict):
            transfer_min = specs.get("transfer_minutes") or 35
            infra_rich = {
                "beach": {
                    "line": f"{beach_line}-я линия",
                    "type": beach_type,
                    "entry": sea_entry,
                    "pier": "Деревянный пирс с шезлонгами и спуском в воду" if beach_line == 1 else "Пирс отсутствует",
                    "equipment": "Шезлонги, зонтики и пляжные матрасы предоставляются бесплатно",
                },
                "pools": {
                    "pools_count": "Несколько открытых бассейнов с пресной водой",
                    "aquapark": "Собственный аквапарк (водные горки для взрослых и детей)" if has_aquapark else "Аквапарк отсутствует",
                    "heated": "Бассейн с подогревом в зимний/весенний сезон" if has_heated_pools else "Открытые пресноводные бассейны без подогрева",
                    "children_pool": "Детский бассейн с безопасной глубиной и мини-горкой",
                },
                "food": {
                    "concept": food_concept,
                    "main_buffet": "Главный ресторан: шведский стол (европейская, восточная кухня)",
                    "alacarte": "Рестораны A la Carte по предварительной записи",
                    "bars": "Бар у бассейна, лобби-бар, снек-бар",
                },
                "kids": {
                    "club": "Мини-клуб для детей от 4 до 12 лет с аниматорами",
                    "pool": "Мелкий детский бассейн",
                    "playground": "Открытая игровая площадка",
                },
                "sport_spa": {
                    "spa": "SPA-центр: турецкий хаммам, сауна, массажные кабинеты",
                    "fitness": "Тренажерный зал с кардио- и силовыми тренажерами",
                    "watersports": "Снорклинг, прокат снаряжения, водные виды спорта",
                },
                "comfort": {
                    "wifi": "Wi-Fi на всей территории и в номерах",
                    "room_amenities": "Индивидуальный кондиционер, сейф, балкон/терраса, мини-бар, спутниковое ТВ",
                    "distance": f"Ориентировочное время трансфера из аэропорта: ~{transfer_min} минут",
                },
            }

        # Sanity validation on infra_rich:
        if isinstance(infra_rich, dict):
            pools_block = dict(infra_rich.get("pools", {}) if isinstance(infra_rich.get("pools"), dict) else {})
            aq_text = str(pools_block.get("aquapark", ""))

            # Strict Aquapark Sanity:
            # If the hotel has an aquapark, never display canned "2 водные горки" or "отсутствуют"
            if has_aquapark:
                if "2 водные горки" in aq_text or "отсутствуют" in aq_text.lower():
                    slides_cnt = specs.get("slides_total") or 8
                    pools_block["aquapark"] = f"Собственный аквапарк ({slides_cnt} водных горок для взрослых и детей)"
                    infra_rich["pools"] = pools_block

            # Strict Beach Line Sanity:
            # If hotel is on 2nd or 3rd line, beach description must never state "1-я линия"
            beach_block = dict(infra_rich.get("beach", {}) if isinstance(infra_rich.get("beach"), dict) else {})
            if beach_block:
                if beach_line >= 2 and "1-я линия" in str(beach_block.get("line", "")):
                    dist_txt = f"~{specs.get('beach_distance_meters', 500)} м" if specs.get("beach_distance_meters") else "300–600 м"
                    shuttle_txt = ", регулярный шаттл на пляж" if specs.get("shuttle_bus") != "none" else ""
                    beach_block["line"] = f"{beach_line}-я линия ({dist_txt}, через променад или дорогу{shuttle_txt})"
                    infra_rich["beach"] = beach_block

        ai_hotel_summary = passport.get("ai_hotel_summary") or verdict

        return {
            "specs": specs,
            "reputation": rep,
            "main_image_url": resolved_main_img,
            "gallery_photos": gallery_photos,
            "tripadvisor_url": tripadvisor_url,
            "google_reviews_url": google_reviews_url,
            "youtube_search_url": youtube_search_url,
            "ta_rating": float(ta_rating) if (ta_rating is not None and float(ta_rating) > 0) else None,
            "ta_reviews": int(ta_reviews) if (ta_reviews is not None and int(ta_reviews) > 0) else None,
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

