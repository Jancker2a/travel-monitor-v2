"""
GeoResolver: Canonical resolution of Country and Region for hotels.
Eliminates contradictions (e.g. 'Турция • Сафага') and accurately detects
resorts from Fly.pl URL slugs and hotel names.
"""

import re
from typing import Optional, Tuple

COUNTRY_SLUG_MAP = {
    "egipt": "Египет",
    "turcja": "Турция",
    "cypr": "Кипр",
    "grecja": "Греция",
    "hiszpania": "Испания",
    "tunezja": "Тунис",
    "zjednoczone-emiraty-arabskie": "ОАЭ",
    "wlochy": "Италия",
    "bulgaria": "Болгария",
    "malta": "Мальта",
    "albania": "Албания",
    "portugalia": "Португалия",
    "czarnogora": "Черногория",
    "chorwacja": "Хорватия",
}

# Maps resort slug -> (Canonical Country, Canonical Region)
RESORT_SLUG_MAP = {
    # --- ЕГИПЕТ ---
    "szarm-el-szejk": ("Египет", "Шарм-эль-Шейх"),
    "sharm-el-sheikh": ("Египет", "Шарм-эль-Шейх"),
    "sharm": ("Египет", "Шарм-эль-Шейх"),
    "hurghada": ("Египет", "Хургада"),
    "hurgada": ("Египет", "Хургада"),
    "safadza": ("Египет", "Сафага"),
    "safaga": ("Египет", "Сафага"),
    "marsa-alam": ("Египет", "Марса-Алам"),
    "marsa": ("Египет", "Марса-Алам"),
    "makadi-bay": ("Египет", "Макади Бэй"),
    "makadi": ("Египет", "Макади Бэй"),
    "soma-bay": ("Египет", "Сома Бэй"),
    "somabay": ("Египет", "Сома Бэй"),
    "el-gouna": ("Египет", "Эль-Гуна"),
    "elgouna": ("Египет", "Эль-Гуна"),
    "al-dzuna": ("Египет", "Эль-Гуна"),
    "sahl-hasheesh": ("Египет", "Сахл Хашиш"),
    "dahab": ("Египет", "Дахаб"),
    "taba": ("Египет", "Таба"),
    "al-kusajr": ("Египет", "Эль-Кусейр"),
    "el-quseir": ("Египет", "Эль-Кусейр"),
    "madinat-coraya": ("Египет", "Марса-Алам"),

    # --- ТУРЦИЯ ---
    "alanya": ("Турция", "Аланья"),
    "konakli": ("Турция", "Аланья"),
    "avsallar": ("Турция", "Аланья"),
    "okurcalar": ("Турция", "Аланья"),
    "mahmutlar": ("Турция", "Аланья"),
    "kargicak": ("Турция", "Аланья"),
    "incekum": ("Турция", "Аланья"),
    "side": ("Турция", "Сиде"),
    "manavgat": ("Турция", "Сиде"),
    "colakli": ("Турция", "Сиде"),
    "kumkoy": ("Турция", "Сиде"),
    "titreyengol": ("Турция", "Сиде"),
    "evrenseki": ("Турция", "Сиде"),
    "kemer": ("Турция", "Кемер"),
    "tekirova": ("Турция", "Кемер"),
    "beldibi": ("Турция", "Кемер"),
    "goynuk": ("Турция", "Кемер"),
    "kiris": ("Турция", "Кемер"),
    "camyuva": ("Турция", "Кемер"),
    "belek": ("Турция", "Белек"),
    "bogazkent": ("Турция", "Белек"),
    "kadriye": ("Турция", "Белек"),
    "antalya": ("Турция", "Анталья"),
    "lara": ("Турция", "Анталья"),
    "kundu": ("Турция", "Анталья"),
    "bodrum": ("Турция", "Бодрум"),
    "turgutreis": ("Турция", "Бодрум"),
    "gumbet": ("Турция", "Бодрум"),
    "torba": ("Турция", "Бодрум"),
    "yalikavak": ("Турция", "Бодрум"),
    "marmaris": ("Турция", "Мармарис"),
    "icmeler": ("Турция", "Мармарис"),
    "turunc": ("Турция", "Мармарис"),
    "fethiye": ("Турция", "Фетхие"),
    "oludeniz": ("Турция", "Фетхие"),
    "kusadasi": ("Турция", "Кушадасы"),
    "didim": ("Турция", "Дидим"),
    "didyma": ("Турция", "Дидим"),
    "cesme": ("Турция", "Чешме"),
    "alacati": ("Турция", "Чешме"),

    # --- ГРЕЦИЯ ---
    "kreta": ("Греция", "Крит"),
    "crete": ("Греция", "Крит"),
    "chania": ("Греция", "Крит"),
    "heraklion": ("Греция", "Крит"),
    "rethymno": ("Греция", "Крит"),
    "hersonissos": ("Греция", "Крит"),
    "malia": ("Греция", "Крит"),
    "agios-nikolaos": ("Греция", "Крит"),
    "rodos": ("Греция", "Родос"),
    "rhodes": ("Греция", "Родос"),
    "faliraki": ("Греция", "Родос"),
    "lindos": ("Греция", "Родос"),
    "kolymbia": ("Греция", "Родос"),
    "kallithea": ("Греция", "Родос"),
    "ialyssos": ("Греция", "Родос"),
    "kos": ("Греция", "Кос"),
    "kardamena": ("Греция", "Кос"),
    "mastichari": ("Греция", "Кос"),
    "tigaki": ("Греция", "Кос"),
    "marmari": ("Греция", "Кос"),
    "korfu": ("Греция", "Корфу"),
    "corfu": ("Греция", "Корфу"),
    "zakynthos": ("Греция", "Закинф"),
    "zante": ("Греция", "Закинф"),
    "chalkidiki": ("Греция", "Халкидики"),
    "halkidiki": ("Греция", "Халкидики"),
    "kassandra": ("Греция", "Халкидики"),
    "sithonia": ("Греция", "Халкидики"),
    "ateny": ("Греция", "Афины"),
    "athens": ("Греция", "Афины"),
    "attyka": ("Греция", "Аттика"),
    "attica": ("Греция", "Аттика"),
    "peloponez": ("Греция", "Пелопоннес"),
    "peloponnese": ("Греция", "Пелопоннес"),
    "santorini": ("Греция", "Санторини"),
    "mykonos": ("Греция", "Миконос"),
    "tassos": ("Греция", "Тасос"),
    "thassos": ("Греция", "Тасос"),

    # --- КИПР ---
    "paphos": ("Кипр", "Пафос"),
    "pafos": ("Кипр", "Пафос"),
    "ayia-napa": ("Кипр", "Айя-Напа"),
    "ajia-napa": ("Кипр", "Айя-Напа"),
    "protaras": ("Кипр", "Протарас"),
    "larnaka": ("Кипр", "Ларнака"),
    "larnaca": ("Кипр", "Ларнака"),
    "limassol": ("Кипр", "Лимассол"),

    # --- ИСПАНИЯ ---
    "majorka": ("Испания", "Майорка"),
    "mallorca": ("Испания", "Майорка"),
    "teneryfa": ("Испания", "Тенерифе"),
    "tenerife": ("Испания", "Тенерифе"),
    "gran-canaria": ("Испания", "Гран-Канария"),
    "fuerteventura": ("Испания", "Фуэртевентура"),
    "lanzarote": ("Испания", "Лансароте"),
    "costa-brava": ("Испания", "Коста-Брава"),
    "costa-del-sol": ("Испания", "Коста-дель-Соль"),
    "costa-dorada": ("Испания", "Коста-Дорада"),
    "costa-blanca": ("Испания", "Коста-Бланка"),
    "ibiza": ("Испания", "Ибица"),

    # --- ТУНИС ---
    "djerba": ("Тунис", "Джерба"),
    "dzerba": ("Тунис", "Джерба"),
    "hammamet": ("Тунис", "Хаммамет"),
    "sousse": ("Тунис", "Сусс"),
    "susa": ("Тунис", "Сусс"),
    "monastir": ("Тунис", "Монастир"),
    "monastyr": ("Тунис", "Монастир"),
    "mahdia": ("Тунис", "Махдия"),

    # --- ОАЭ ---
    "dubaj": ("ОАЭ", "Дубай"),
    "dubai": ("ОАЭ", "Дубай"),
    "ras-al-khaimah": ("ОАЭ", "Рас-эль-Хайма"),
    "ras-al-chajma": ("ОАЭ", "Рас-эль-Хайма"),
    "abu-dhabi": ("ОАЭ", "Абу-Даби"),
    "abu-zabi": ("ОАЭ", "Абу-Даби"),
    "sharjah": ("ОАЭ", "Шарджа"),
    "szardza": ("ОАЭ", "Шарджа"),
    "fujairah": ("ОАЭ", "Фуджейра"),
    "fudzajra": ("ОАЭ", "Фуджейра"),
    "ajman": ("ОАЭ", "Аджман"),

    # --- БОЛГАРИЯ ---
    "zlote-piaski": ("Болгария", "Золотые Пески"),
    "golden-sands": ("Болгария", "Золотые Пески"),
    "sloneczny-brzeg": ("Болгария", "Солнечный Берег"),
    "sunny-beach": ("Болгария", "Солнечный Берег"),
    "nessebar": ("Болгария", "Несебр"),
    "nesebyr": ("Болгария", "Несебр"),
    "albena": ("Болгария", "Албена"),
    "sozopol": ("Болгария", "Созополь"),
    "swiety-wlas": ("Болгария", "Святой Влас"),
    "sveti-vlas": ("Болгария", "Святой Влас"),

    # --- ИТАЛИЯ ---
    "sycylia": ("Италия", "Сицилия"),
    "sicily": ("Италия", "Сицилия"),
    "sardynia": ("Италия", "Сардиния"),
    "sardinia": ("Италия", "Сардиния"),
    "kalabria": ("Италия", "Калабрия"),
    "calabria": ("Италия", "Калабрия"),
    "rimini": ("Италия", "Римини"),
}

# Strict region-to-country validation to forbid contradictions
STRICT_REGION_TO_COUNTRY = {
    # Egypt regions
    "Шарм-эль-Шейх": "Египет",
    "Хургада": "Египет",
    "Сафага": "Египет",
    "Марса-Алам": "Египет",
    "Макади Бэй": "Египет",
    "Сома Бэй": "Египет",
    "Эль-Гуна": "Египет",
    "Сахл Хашиш": "Египет",
    "Дахаб": "Египет",
    "Таба": "Египет",
    "Эль-Кусейр": "Египет",

    # Turkey regions
    "Аланья": "Турция",
    "Сиде": "Турция",
    "Кемер": "Турция",
    "Белек": "Турция",
    "Анталья": "Турция",
    "Бодрум": "Турция",
    "Мармарис": "Турция",
    "Фетхие": "Турция",
    "Кушадасы": "Турция",
    "Дидим": "Турция",
    "Чешме": "Турция",

    # Cyprus regions
    "Пафос": "Кипр",
    "Айя-Напа": "Кипр",
    "Протарас": "Кипр",
    "Ларнака": "Кипр",
    "Лимассол": "Кипр",

    # Greece regions
    "Крит": "Греция",
    "Родос": "Греция",
    "Кос": "Греция",
    "Корфу": "Греция",
    "Закинф": "Греция",
    "Халкидики": "Греция",
    "Афины": "Греция",
    "Аттика": "Греция",
    "Пелопоннес": "Греция",
    "Санторини": "Греция",
    "Миконос": "Греция",
    "Тасос": "Греция",

    # Spain regions
    "Майорка": "Испания",
    "Тенерифе": "Испания",
    "Гран-Канария": "Испания",
    "Фуэртевентура": "Испания",
    "Лансароте": "Испания",
    "Коста-Брава": "Испания",
    "Коста-дель-Соль": "Испания",
    "Коста-Дорада": "Испания",
    "Коста-Бланка": "Испания",
    "Ибица": "Испания",

    # Tunisia regions
    "Джерба": "Тунис",
    "Хаммамет": "Тунис",
    "Сусс": "Тунис",
    "Монастир": "Тунис",
    "Махдия": "Тунис",

    # UAE regions
    "Дубай": "ОАЭ",
    "Рас-эль-Хайма": "ОАЭ",
    "Абу-Даби": "ОАЭ",
    "Шарджа": "ОАЭ",
    "Фуджейра": "ОАЭ",
    "Аджман": "ОАЭ",

    # Bulgaria regions
    "Золотые Пески": "Болгария",
    "Солнечный Берег": "Болгария",
    "Несебр": "Болгария",
    "Албена": "Болгария",
    "Созополь": "Болгария",
    "Святой Влас": "Болгария",

    # Italy regions
    "Сицилия": "Италия",
    "Сардиния": "Италия",
    "Калабрия": "Италия",
    "Римини": "Италия",
}


class GeoResolver:
    """Accurately identifies Country and Region from URLs, Hotel Names, and Filters."""

    @classmethod
    def parse_from_url(cls, url: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """Extracts (Country, Region) directly from Fly.pl / Wakacje package URLs."""
        if not url:
            return None, None

        # Fly.pl pattern: /wycieczka/{country},{region_macro}[,{region_micro}]/{hotel}/...
        m = re.search(r"/wycieczka/([^,/]+),([^,/]+)(?:,([^,/]+))?", url, re.I)
        if m:
            c_slug = m.group(1).lower()
            r1_slug = m.group(2).lower()
            r2_slug = m.group(3).lower() if m.group(3) else None

            # First, check micro resort if present
            if r2_slug and r2_slug in RESORT_SLUG_MAP:
                c, r = RESORT_SLUG_MAP[r2_slug]
                return c, r

            # Next, check macro resort
            if r1_slug in RESORT_SLUG_MAP:
                c, r = RESORT_SLUG_MAP[r1_slug]
                return c, r

            # Country slug mapping
            resolved_country = COUNTRY_SLUG_MAP.get(c_slug)

            # If resort slug isn't mapped, create clean title
            fallback_resort = None
            candidate_resort = r2_slug if (r2_slug and r2_slug != "c") else (r1_slug if r1_slug != "c" else None)
            if candidate_resort:
                fallback_resort = candidate_resort.replace("-", " ").title()

            return resolved_country, fallback_resort

        return None, None

    @classmethod
    def detect_from_name(cls, hotel_name: str) -> Tuple[Optional[str], Optional[str]]:
        """Extracts (Country, Region) from keywords inside the hotel name."""
        if not hotel_name:
            return None, None

        name_lower = f" {hotel_name.lower().replace('-', ' ').replace('_', ' ')} "

        # Check all known resort keywords sorted by length descending to match longest first
        keywords = [
            ("safaga", "Египет", "Сафага"),
            ("safadza", "Египет", "Сафага"),
            ("hurghada", "Египет", "Хургада"),
            ("hurgada", "Египет", "Хургада"),
            ("sharm el sheikh", "Египет", "Шарм-эль-Шейх"),
            ("sharm", "Египет", "Шарм-эль-Шейх"),
            ("marsa alam", "Египет", "Марса-Алам"),
            ("makadi bay", "Египет", "Макади Бэй"),
            ("makadi", "Египет", "Макади Бэй"),
            ("soma bay", "Египет", "Сома Бэй"),
            ("el gouna", "Египет", "Эль-Гуна"),
            ("sahl hasheesh", "Египет", "Сахл Хашиш"),
            ("dahab", "Египет", "Дахаб"),
            ("taba", "Египет", "Таба"),

            ("alanya", "Турция", "Аланья"),
            ("side", "Турция", "Сиде"),
            ("kemer", "Турция", "Кемер"),
            ("belek", "Турция", "Белек"),
            ("antalya", "Турция", "Анталья"),
            ("bodrum", "Турция", "Бодрум"),
            ("marmaris", "Турция", "Мармарис"),
            ("fethiye", "Турция", "Фетхие"),
            ("kusadasi", "Турция", "Кушадасы"),
            ("didim", "Турция", "Дидим"),
            ("cesme", "Турция", "Чешме"),

            ("ayia napa", "Кипр", "Айя-Напа"),
            ("protaras", "Кипр", "Протарас"),
            ("paphos", "Кипр", "Пафос"),
            ("larnaca", "Кипр", "Ларнака"),
            ("limassol", "Кипр", "Лимассол"),

            ("crete", "Греция", "Крит"),
            ("rhodes", "Греция", "Родос"),
            ("kos", "Греция", "Кос"),
            ("corfu", "Греция", "Корфу"),
            ("zakynthos", "Греция", "Закинф"),
            ("athens", "Греция", "Афины"),
            ("attica", "Греция", "Аттика"),

            ("mallorca", "Испания", "Майорка"),
            ("tenerife", "Испания", "Тенерифе"),
            ("ibiza", "Испания", "Ибица"),

            ("djerba", "Тунис", "Джерба"),
            ("hammamet", "Тунис", "Хаммамет"),
            ("sousse", "Тунис", "Сусс"),

            ("dubai", "ОАЭ", "Дубай"),
            ("ras al khaimah", "ОАЭ", "Рас-эль-Хайма"),

            ("golden sands", "Болгария", "Золотые Пески"),
            ("sunny beach", "Болгария", "Солнечный Берег"),
            ("nessebar", "Болгария", "Несебр"),
        ]

        for kw, country, region in keywords:
            if f" {kw} " in name_lower or f"({kw})" in name_lower:
                return country, region

        return None, None

    @classmethod
    def resolve(
        cls,
        hotel_name: str,
        offer_url: Optional[str] = None,
        current_country: Optional[str] = None,
        current_region: Optional[str] = None,
        destination_hint: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Determines canonical Country and Region, enforcing strict geographic consistency.
        Returns: (country: str, region: str)
        """
        resolved_country = None
        resolved_region = None

        # 1. Parse from offer URL (highest authority from tour operator)
        url_c, url_r = cls.parse_from_url(offer_url)
        if url_c:
            resolved_country = url_c
        if url_r:
            resolved_region = url_r

        # 2. Check hotel name for explicit resort keywords
        name_c, name_r = cls.detect_from_name(hotel_name)
        if name_r and not resolved_region:
            resolved_region = name_r
        if name_c and not resolved_country:
            resolved_country = name_c

        # 3. Use current region if not resolved yet
        if not resolved_region and current_region:
            resolved_region = current_region.strip()

        # 4. Strict Conflict Resolution: Region dictates country if known!
        # E.g. 'Сафага' ALWAYS implies 'Египет', never 'Турция'.
        if resolved_region in STRICT_REGION_TO_COUNTRY:
            # Overwrite any conflicting country
            resolved_country = STRICT_REGION_TO_COUNTRY[resolved_region]

        # 5. Fallback country resolution
        if not resolved_country:
            if current_country:
                resolved_country = current_country.strip()
            elif destination_hint:
                dh = destination_hint.lower()
                if "egypt" in dh or "егип" in dh:
                    resolved_country = "Египет"
                elif "turk" in dh or "турц" in dh:
                    resolved_country = "Турция"
                elif "gree" in dh or "грец" in dh:
                    resolved_country = "Греция"
                elif "cypr" in dh or "кипр" in dh:
                    resolved_country = "Кипр"
                elif "spain" in dh or "испан" in dh:
                    resolved_country = "Испания"
                elif "bulgar" in dh or "болгар" in dh:
                    resolved_country = "Болгария"
                elif "tunis" in dh or "тунис" in dh:
                    resolved_country = "Тунис"
                elif "uae" in dh or "оаэ" in dh or "emir" in dh:
                    resolved_country = "ОАЭ"
                elif "ital" in dh or "итал" in dh:
                    resolved_country = "Италия"
                else:
                    resolved_country = destination_hint.capitalize()
            else:
                resolved_country = "Египет"

        # 6. Fallback region if still empty
        if not resolved_region:
            resolved_region = resolved_country

        return resolved_country, resolved_region

