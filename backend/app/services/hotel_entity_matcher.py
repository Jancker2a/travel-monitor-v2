#!/usr/bin/env python3
"""
High-Precision Hotel Entity Matcher & Rename Alias Graph (V2).

Handles:
1. Rebrandings & renames across any chain depth (e.g. Serenity Fun City <-> Serenity Alma Heights <-> SRNTY Sun Ray).
2. Unbracketed rename separators ('A X B', 'A ex. B') and truncated V1 titles ('... (Ex. Serenity Sky Ar').
3. External stable IDs (Fly.pl objectId & URL slug, Check24 hotelId).
4. Unicode diacritic transliteration (Barceló -> Barcelo, Göynük -> Goynuk, Paşa -> Pasa).
5. Canonical compound folding ('Aqua Park'/'Waterpark' -> 'aquapark', 'Sea Gull' -> 'seagull', 'Al Dau' -> 'aldau', 'SRNTY' -> 'serenity').
6. Zero-False-Positive Guards:
   - Granular micro-resort Geo Zone Lock (Sharm vs Hurghada, Soma Bay vs El Gouna, Kemer vs Belek vs Lara, Crete vs Rhodes vs Kos).
   - Chain Sub-Property & Wing Conflict Guard (Club Resort != Club Aquapark, Titanic Beach != Palace, Pickalbatros Jungle != Aqua Vista).
   - Generic-Only Literal Guard (The Grand Hotel Hurghada != The Grand Resort != The Grand Hotel Sharm; Royal Olympic != Olympic Star).
   - Numeral Guard (Sunrise 1 != Sunrise 2; Irene Villas 1+2).
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger("hotel_entity_matcher")

# ---------------------------------------------------------------------------
# 1. Text Normalization & Diacritic Folding
# ---------------------------------------------------------------------------

_CHAR_MAP = str.maketrans({
    "ä": "a", "ö": "o", "ü": "u", "ß": "ss",
    "ł": "l", "ś": "s", "ć": "c", "ź": "z", "ż": "z", "ó": "o", "ń": "n", "ą": "a", "ę": "e",
    "ş": "s", "ğ": "g", "ç": "c", "ı": "i", "İ": "i",
    "é": "e", "è": "e", "ê": "e", "ë": "e",
    "á": "a", "à": "a", "â": "a", "ã": "a",
    "í": "i", "ì": "i", "î": "i",
    "ú": "u", "ù": "u", "û": "u",
    "ñ": "n",
})


def fold_unicode(text: str) -> str:
    """Normalizes diacritics across German, Turkish, Polish, French, Spanish, and Greek transliterations."""
    if not text:
        return ""
    s = text.lower().translate(_CHAR_MAP)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s


# ---------------------------------------------------------------------------
# 2. Granular Geographic Zone Rules (Zero Cross-Resort Mismatches)
# ---------------------------------------------------------------------------

# Maps token/phrase -> (macro_zone, micro_zone)
# Within the same macro_zone, two DIFFERENT non-generic micro_zones ALWAYS conflict (e.g. soma_bay vs el_gouna, kemer vs lara).
GEO_ZONES: Dict[str, Tuple[str, str]] = {
    # Egypt
    "sharm": ("sharm", "sharm"),
    "sheikh": ("sharm", "sharm"),
    "ssh": ("sharm", "sharm"),
    "naama": ("sharm", "naama"),
    "nabq": ("sharm", "nabq"),
    "hadaba": ("sharm", "hadaba"),
    "shark": ("sharm", "sharks_bay"),
    "sharks": ("sharm", "sharks_bay"),
    "nasrani": ("sharm", "ras_nasrani"),
    "pasha": ("sharm", "sharm_el_maya"),
    "makadi": ("hurghada_area", "makadi"),
    "soma": ("hurghada_area", "soma_bay"),
    "gouna": ("hurghada_area", "el_gouna"),
    "safaga": ("hurghada_area", "safaga"),
    "sahl": ("hurghada_area", "sahl_hasheesh"),
    "hasheesh": ("hurghada_area", "sahl_hasheesh"),
    "hashees": ("hurghada_area", "sahl_hasheesh"),
    "hurghada": ("hurghada_area", "hurghada"),
    "hrg": ("hurghada_area", "hurghada"),
    "dahar": ("hurghada_area", "hurghada"),
    "marsa": ("marsa_alam", "marsa_alam"),
    "alam": ("marsa_alam", "marsa_alam"),
    "ghalib": ("marsa_alam", "port_ghalib"),
    "quseir": ("marsa_alam", "quseir"),
    "dahab": ("dahab", "dahab"),
    "nuweiba": ("nuweiba", "nuweiba"),
    "taba": ("taba", "taba"),
    "alamein": ("north_coast", "alamein"),
    "matruh": ("north_coast", "mersa_matruh"),
    "matrouh": ("north_coast", "mersa_matruh"),
    # Russian geo names (DB region column)
    "шарм": ("sharm", "sharm"),
    "хургада": ("hurghada_area", "hurghada"),
    "макади": ("hurghada_area", "makadi"),
    "сафага": ("hurghada_area", "safaga"),
    "сома": ("hurghada_area", "soma_bay"),
    "гуна": ("hurghada_area", "el_gouna"),
    "сахл": ("hurghada_area", "sahl_hasheesh"),
    "марса": ("marsa_alam", "marsa_alam"),
    "дахаб": ("dahab", "dahab"),

    # Turkey (each resort town isolated)
    "antalya": ("antalya_lara", "antalya_lara"),
    "ayt": ("antalya_lara", "antalya_lara"),
    "lara": ("antalya_lara", "lara"),
    "kundu": ("antalya_lara", "kundu"),
    "belek": ("belek", "belek"),
    "bogazkent": ("belek", "bogazkent"),
    "kadriye": ("belek", "kadriye"),
    "side": ("side", "side"),
    "manavgat": ("side", "manavgat"),
    "colakli": ("side", "colakli"),
    "kizilot": ("side", "kizilot"),
    "kizilagac": ("side", "kizilagac"),
    "evrenseki": ("side", "evrenseki"),
    "kumkoy": ("side", "kumkoy"),
    "sorgun": ("side", "sorgun"),
    "titreyengol": ("side", "titreyengol"),
    "kemer": ("kemer", "kemer"),
    "beldibi": ("kemer", "beldibi"),
    "goynuk": ("kemer", "goynuk"),
    "kiris": ("kemer", "kiris"),
    "camyuva": ("kemer", "camyuva"),
    "tekirova": ("kemer", "tekirova"),
    "alanya": ("alanya", "alanya"),
    "avsallar": ("alanya", "avsallar"),
    "konakli": ("alanya", "konakli"),
    "okurcalar": ("alanya", "okurcalar"),
    "turkler": ("alanya", "turkler"),
    "incekum": ("alanya", "incekum"),
    "kestel": ("alanya", "kestel"),
    "mahmutlar": ("alanya", "mahmutlar"),
    "bodrum": ("bodrum", "bodrum"),
    "akbuk": ("didim", "akbuk"),
    "marmaris": ("marmaris", "marmaris"),
    "icmeler": ("marmaris", "icmeler"),
    "fethiye": ("fethiye", "fethiye"),
    "oludeniz": ("fethiye", "oludeniz"),
    "dalaman": ("dalaman", "dalaman"),
    "sarigerme": ("dalaman", "sarigerme"),
    "cesme": ("cesme", "cesme"),
    "kusadasi": ("kusadasi", "kusadasi"),
    "ozdere": ("kusadasi", "ozdere"),
    "didim": ("didim", "didim"),
    "istanbul": ("istanbul", "istanbul"),
    "анталья": ("antalya_lara", "antalya_lara"),
    "белек": ("belek", "belek"),
    "сиде": ("side", "side"),
    "кемер": ("kemer", "kemer"),
    "аланья": ("alanya", "alanya"),
    "бодрум": ("bodrum", "bodrum"),
    "мармарис": ("marmaris", "marmaris"),
    "кушадасы": ("kusadasi", "kusadasi"),

    # Greece (island isolation!)
    "kreta": ("crete", "crete"), "crete": ("crete", "crete"), "крит": ("crete", "crete"),
    "heraklion": ("crete", "heraklion"), "chania": ("crete", "chania"), "rethymno": ("crete", "rethymno"),
    "elounda": ("crete", "elounda"), "hersonissos": ("crete", "hersonissos"), "malia": ("crete", "malia"),
    "georgioupolis": ("crete", "georgioupolis"), "ierapetra": ("crete", "ierapetra"),
    "nikolaos": ("crete", "agios_nikolaos"), "ammoudara": ("crete", "ammoudara"), "anissaras": ("crete", "anissaras"),
    "koutsounari": ("crete", "koutsounari"), "pelagia": ("crete", "agia_pelagia"), "bali": ("crete", "bali"),
    "plakias": ("crete", "plakias"), "adelianos": ("crete", "rethymno"),
    "rhodes": ("rhodes", "rhodes"), "rodos": ("rhodes", "rhodes"), "родос": ("rhodes", "rhodes"),
    "faliraki": ("rhodes", "faliraki"), "lindos": ("rhodes", "lindos"), "kolymbia": ("rhodes", "kolymbia"),
    "kallithea": ("rhodes", "kallithea"), "kalithea": ("rhodes", "kallithea"), "ixia": ("rhodes", "ixia"),
    "theologos": ("rhodes", "theologos"), "ialyssos": ("rhodes", "ialyssos"), "fanes": ("rhodes", "fanes"),
    "kiotari": ("rhodes", "kiotari"), "lardos": ("rhodes", "lardos"), "afandou": ("rhodes", "afandou"),
    "kremasti": ("rhodes", "kremasti"),
    "kos": ("kos", "kos"), "кос": ("kos", "kos"),
    "lambi": ("kos", "lambi"), "mastichari": ("kos", "mastichari"), "kardamena": ("kos", "kardamena"),
    "marmari": ("kos", "marmari"), "tigaki": ("kos", "tigaki"), "psalidi": ("kos", "psalidi"),
    "corfu": ("corfu", "corfu"), "korfu": ("corfu", "corfu"), "kerkyra": ("corfu", "corfu"), "корфу": ("corfu", "corfu"),
    "perama": ("corfu", "perama"), "sidari": ("corfu", "sidari"), "dassia": ("corfu", "dassia"), "liapades": ("corfu", "liapades"),
    "zakynthos": ("zakynthos", "zakynthos"), "zante": ("zakynthos", "zakynthos"), "закинф": ("zakynthos", "zakynthos"),
    "planos": ("zakynthos", "planos"), "tsilivi": ("zakynthos", "tsilivi"), "vasilikos": ("zakynthos", "vasilikos"), "laganas": ("zakynthos", "laganas"),
    "kefalonia": ("kefalonia", "kefalonia"), "lixouri": ("kefalonia", "lixouri"), "kounopetra": ("kefalonia", "kounopetra"),
    "chalkidiki": ("chalkidiki", "chalkidiki"), "halkidiki": ("chalkidiki", "chalkidiki"), "ouranopolis": ("chalkidiki", "ouranopolis"),
    "kassandra": ("chalkidiki", "kassandra"), "sithonia": ("chalkidiki", "sithonia"), "fourka": ("chalkidiki", "fourka"),
    "thassos": ("thassos", "thassos"), "astrida": ("thassos", "thassos"),
    "athens": ("athens", "athens"), "афины": ("athens", "athens"),
    "evia": ("evia", "evia"), "eretria": ("evia", "eretria"),
    "peloponez": ("peloponnese", "peloponnese"), "peloponnese": ("peloponnese", "peloponnese"), "skafidia": ("peloponnese", "skafidia"),
    "santorini": ("santorini", "santorini"), "mykonos": ("mykonos", "mykonos"), "karpathos": ("karpathos", "karpathos"),

    # Cyprus
    "paphos": ("paphos", "paphos"), "pafos": ("paphos", "paphos"),
    "napa": ("ayia_napa", "ayia_napa"), "ayia": ("ayia_napa", "ayia_napa"),
    "protaras": ("protaras", "protaras"),
    "limassol": ("limassol", "limassol"),
    "larnaca": ("larnaca", "larnaca"),
    "kyrenia": ("kyrenia", "kyrenia"),

    # Spain & Islands
    "mallorca": ("mallorca", "mallorca"), "majorca": ("mallorca", "mallorca"), "palma": ("mallorca", "palma"), "alcudia": ("mallorca", "alcudia"), "picafort": ("mallorca", "picafort"),
    "ibiza": ("ibiza", "ibiza"), "menorca": ("menorca", "menorca"),
    "tenerife": ("tenerife", "tenerife"), "fuerteventura": ("fuerteventura", "fuerteventura"),
    "canaria": ("gran_canaria", "gran_canaria"), "lanzarote": ("lanzarote", "lanzarote"),

    # Bulgaria & Others
    "burgas": ("burgas", "burgas"), "nessebar": ("burgas", "nessebar"), "sunny": ("burgas", "sunny_beach"), "sozopol": ("burgas", "sozopol"),
    "varna": ("varna", "varna"), "golden": ("varna", "golden_sands"), "albena": ("varna", "albena"),
    "zanzibar": ("zanzibar", "zanzibar"), "dubai": ("dubai", "dubai"),
}

LOCATION_WORDS: Set[str] = set(GEO_ZONES.keys()) | {
    "el", "al", "ras", "um", "sid", "sea", "red", "dolny", "wschodnia", "zachodnia",
    "egipt", "egypt", "turcja", "turkey", "grecja", "greece", "cypr", "cyprus", "hiszpania", "spain", "bulgaria",
    "makadi", "gouna", "coraya", "can", "cala", "abu", "dhabi",
}

# ---------------------------------------------------------------------------
# 3. Brand, Generic Noise, and Wing/Unit Conflict Tokens
# ---------------------------------------------------------------------------

STOP_WORDS: Set[str] = {
    "hotel", "hotels", "resort", "resorts", "spa", "all", "inclusive",
    "the", "and", "und", "i", "stars", "of", "a", "an", "in", "by", "at",
    "holidays", "collection", "curio", "autograph", "ross", "otium",
}

# Words stripped ONLY as soft filler when matching core identity if an anchor exists
SOFT_DESCRIPTORS: Set[str] = {
    "deluxe", "premium", "luxury", "royal", "grand", "park", "beach",
    "aqua", "aquapark", "waterpark", "village", "inn", "suites", "suite", "villas", "villa",
    "boutique", "garden", "gardens", "sea", "view", "blue", "golden", "sun", "city", "centre",
    "heights", "palace", "club", "residence", "lifestyle", "select", "sensatori",
}

STRONG_BRANDS: Set[str] = {
    "rixos", "pickalbatros", "albatros", "baron", "hilton", "steigenberger",
    "jaz", "sunrise", "titanic", "delphin", "sheraton", "marriott", "kempinski",
    "movenpick", "radisson", "sentido", "tui", "iberostar", "riu", "paloma",
    "voyage", "maxx", "limak", "crystal", "alva", "donna", "dobedan", "papillon",
    "akka", "swandor", "selectum", "xanadu", "gloria", "concorde", "calista",
    "mitsis", "grecotel", "aldemar", "barcelo", "melia", "h10", "lopesan",
    "cleopatra", "rotana", "novotel", "mercure", "sofitel", "swissotel",
    "hyatt", "intercontinental", "amarina", "labranda", "azur", "three", "corners",
    "aladdin", "ali", "baba", "pyramisa", "domina", "meraki", "rehana", "tropitel",
    "verginia", "lido", "coral", "charmillion", "serenity", "amwaj", "fame", "liberty",
    "ramada", "wyndham", "orange", "county", "ic", "asteria", "ananea", "robinson",
    "fort", "arabesque", "barut", "kaya", "titanic", "calimera", "blend", "long",
}

# Distinct properties within the same brand/chain or resort complex.
# Mutual mismatch between two properties that share a brand/prefix blocks false matches.
CONFLICTING_UNIT_TOKENS: Set[str] = {
    # Pickalbatros / Sunrise / Jaz / Charmillion / Titanic / Rixos / Limak / Delphin units
    "jungle", "blu", "blue", "vista", "dana", "citadel", "moderna", "lagoon",
    "remal", "diamond", "oasis", "saraya", "coraya", "lamaya", "samaya", "maraya",
    "prive", "riviera", "crystal", "white", "royal", "palace", "beach", "club",
    "gardens", "garden", "life", "miracle", "nirvana", "imperial", "diva", "be",
    "elite", "golf", "plaza", "downtown", "kingdom", "nickelodeon", "tirana",
    "radamis", "seagate", "west", "elisir", "prestige", "aqua", "aquapark", "aquaviva",
    "alpha", "alma", "sun", "ray", "sea", "reef", "sky", "arc", "queen", "crown",
    "fun", "atlantis", "arcadia", "lara", "belvil", "zeugma", "botanics", "botanik",
    "platinum", "legend", "sungate", "tekir", "tekirova", "kaya", "select",
    "porto", "rithymna", "star", "bay", "hills", "albatross", "albatros", "fantasia",
    "rehana", "sharm", "makadi", "sahl", "hasheesh", "al", "aldau", "alaya", "alcazar",
    "fayrouz", "bluemarine", "acquamarine", "aquamarin", "solymar",
    "holidays", "boutique", "pearl", "village", "residences",
}

# Words where 'one hotel adds "& Aqua Park" or "Hotel & Resort" vs short name' should NOT break matching
# EXCEPT when one specifically calls itself Club Resort vs Club Aquapark (checked separately).
OPTIONAL_INFRA_TAIL_WORDS: Set[str] = {
    "spa", "aquapark", "wellness", "thalasso", "bungalows", "villas", "suites",
    "hotel", "resort", "beach", "deluxe", "club", "adults", "only",
}

# Multi-location hotel groups where missing a city in one name MUST still cross-check geo hints!
MULTI_LOCATION_CHAIN_PREFIXES: Set[str] = {
    "pickalbatros", "albatros", "rixos", "fame", "orange", "liberty", "long", "swiss",
    "ramada", "barcelo", "movenpick", "sheraton", "hilton", "steigenberger", "jaz",
    "sunrise", "domina", "limak", "tui", "robinson", "iberostar", "mitsis", "grecotel",
}

DEFAULT_CACHE_FILE = "hotel_crossborder_mapping.json"
DEFAULT_SIMILARITY_THRESHOLD = 0.80

# ---------------------------------------------------------------------------
# 4. External ID & URL Slug Extractors
# ---------------------------------------------------------------------------


def extract_fly_object_id(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    m = re.search(r"objectId=(\d+)", str(url))
    return m.group(1) if m else None


def extract_fly_url_slug(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    m = re.search(r"https?://[^/]+/wycieczka/[^/]+/([^/?#]+)/", str(url))
    if not m:
        return None
    slug = m.group(1).strip().lower()
    # Ignore empty or generic slugs
    if not slug or len(slug) < 3:
        return None
    return slug


def extract_check24_hotel_id(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    m = re.search(r"hotelId=(\d+)", str(url))
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# 5. Geo Extraction & Rename Alias Parsing
# ---------------------------------------------------------------------------


def _scan_zones(text: str) -> Optional[Tuple[str, str]]:
    if not text:
        return None
    tokens = re.findall(r"[a-zа-я0-9]+", fold_unicode(text))
    found = [GEO_ZONES[tok] for tok in tokens if tok in GEO_ZONES]
    if not found:
        return None
    generic_micros = {
        "hurghada", "antalya_lara", "crete", "rhodes", "kos", "corfu",
        "zakynthos", "sharm", "cyprus", "mallorca", "side", "belek", "kemer", "alanya",
    }
    specific = [z for z in found if z[1] not in generic_micros]
    if specific:
        return specific[-1]
    return found[-1]


def extract_geo_zones(
    raw_name: str,
    country: Optional[str] = None,
    region_hint: Optional[str] = None,
    offer_url: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (macro_zone, micro_zone).
    Priority: explicit resort/city in hotel title > Fly.pl URL path > DB region_hint.
    This guarantees wrong DB macro-buckets (like Fly.pl tagging Lara hotels as 'Alanya')
    never override explicit 'Lara' / 'Makadi' / 'Side' in the hotel name itself!
    """
    title_zone = _scan_zones(raw_name or "")
    if title_zone:
        return title_zone

    if offer_url:
        m_geo = re.search(r"/wycieczka/([^/]+)/", str(offer_url))
        if m_geo:
            url_zone = _scan_zones(m_geo.group(1).replace(",", " ").replace("-", " "))
            if url_zone:
                return url_zone

    if region_hint:
        reg_zone = _scan_zones(str(region_hint))
        if reg_zone:
            return reg_zone

    return (None, None)


def geo_zones_conflict(z1: Tuple[Optional[str], Optional[str]], z2: Tuple[Optional[str], Optional[str]]) -> bool:
    """True when both zones are known and represent different cities/islands/micro-resorts."""
    m1, u1 = z1
    m2, u2 = z2
    if not m1 or not m2:
        return False
    if m1 != m2:
        return True

    # Hurghada area micro-zones conflict strictly with each other AND specific vs 'hurghada' when explicit
    specific_hurghada = {"makadi", "soma_bay", "el_gouna", "safaga", "sahl_hasheesh"}
    if m1 == "hurghada_area":
        if u1 in specific_hurghada and u2 in specific_hurghada and u1 != u2:
            return True

    # Turkish micro-towns inside the same macro bucket conflict strictly
    specific_turkey_micro = {
        "lara", "kundu", "antalya_lara",
        "goynuk", "beldibi", "kiris", "camyuva", "tekirova",
        "avsallar", "konakli", "okurcalar", "turkler", "incekum",
        "colakli", "kizilot", "kizilagac", "evrenseki", "kumkoy", "sorgun", "titreyengol",
    }
    if u1 in specific_turkey_micro and u2 in specific_turkey_micro and u1 != u2:
        # Allow antalya_lara <-> lara / kundu, reject distinct towns (e.g. colakli vs kizilot)
        if not ({u1, u2} <= {"antalya_lara", "lara", "kundu"}):
            return True

    # Greek island sub-resorts (e.g. Georgioupolis != Plakias on Crete, Faliraki != Lindos on Rhodes)
    generic_greek = {"crete", "rhodes", "kos", "corfu", "zakynthos", "chalkidiki", "athens"}
    if m1 in generic_greek:
        if u1 not in generic_greek and u2 not in generic_greek and u1 != u2:
            return True

    return False


def _strip_rename_and_promo_noise(raw_name: str, fold_synonyms: bool = True) -> str:
    """Strips promo tails, operator suffixes, Polish geo suffixes, and brackets cleanly."""
    text = fold_unicode(raw_name or "").strip()
    if not text:
        return ""

    # 1. Strip Polish/OTA geo tails: "Egipt, Hurghada, Makadi Bay", "Turcja, Side, Colakli", "Grecja, Rodos, Ialyssos"
    text = re.sub(
        r"\s+(?:egipt|turcja|grecja|cypr|hiszpania|bulgaria)(?:\s*,.*|\s+.*)?$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # 2. Strip promo/concept tails (must keep "The Land of Legends Kingdom Hotel" intact!)
    text = re.sub(r"\s*[-–—]?\s*the\s+land\s+of\s+legends(?:\s+free)?\s+access\b.*$", "", text, flags=re.I)
    text = re.sub(r"\s+powered\s+by\s+.*$", "", text, flags=re.I)
    text = re.sub(r"\s+ross\s+park\s+collection\b", "", text, flags=re.I)
    text = re.sub(r"\s+(?:curio|autograph|tapest?ry)\s+collection(?:\s+by\s+hilton|\s+by\s+marriott)?\b", "", text, flags=re.I)
    text = re.sub(r"\s*\(?\badults?\s*only(?:\s*\d+\+?)?\)?", " ", text, flags=re.I)
    text = re.sub(r"\b(?:only\s*)?1[68]\+\b", " ", text, flags=re.I)
    text = re.sub(r"^allsun\s+(?:hotel\s+)?", "", text, flags=re.I)

    # 3. Strip (ex. ...), (dawniej ...), including TRUNCATED unclosed "(ex. Serenity Sky Ar" at end of V1 strings
    text = re.sub(r"\((?:ex\.?|dawniej|former|fka|previously|ehem\.?|ehemals)\b[^)]*(?:\)|$)", " ", text, flags=re.I)
    # Also strip unbracketed trailing "ex. Old Name" or " X Old Name" when computing PRIMARY name
    text = re.sub(r"\s+ex\.?\s+.*$", "", text, flags=re.I)

    # 4. Strip operator/airport bracketed codes & trailing -SSH / -HRG / -AYT (preserve explicit resort city parens for branch guard)
    text = re.sub(r"\((?:\b[a-z]{2,4}\d*\b|ssh|hrg|ayt|rmf)\s*[^)]*(?:\)|$)", " ", text, flags=re.I)
    text = re.sub(r"\s*[-–]\s*(?:ssh|hrg|ayt|rmf)\b\s*$", "", text, flags=re.I)
    text = re.sub(r"\[[^\]]*\]", " ", text)

    # Strip trailing unclosed parens caused by 40-char truncation like "(Naa" or "(Sharm El Sh"
    text = re.sub(r"\([^)]*$", " ", text)

    # 5. Strip trailing "by JAZ" / "by Wyndham" / "by Atlantica" / "by MP Hotels" / "by Sunrise"
    # Note: keep "Canvas by Mitsis", only strip short chain suffix when preceded by >=2 tokens
    tokens_tmp = text.split()
    if len(tokens_tmp) >= 3:
        text = re.sub(
            r"\s+by\s+(?:jaz|wyndham|atlantica|mp\s+hotels|sunrise|hilton|marriott|radisson|mitsis)\b",
            "",
            text,
            flags=re.I,
        )

    # 6. Synonym & Compound Token Folding
    if fold_synonyms:
        text = re.sub(r"\bsrnty\b", "serenity", text)
        text = re.sub(r"\baqua\s+park\b|\bwater\s+park\b|\bwaterpark\b", "aquapark", text)
        text = re.sub(r"\bsea\s+gull\b", "seagull", text)
        text = re.sub(r"\bal\s+dau\b", "aldau", text)
        text = re.sub(r"\blux\s*[®]?\s*me\b", "luxme", text)
        text = re.sub(r"\bblue\s+marine\b", "bluemarine", text)
        text = re.sub(r"\bmerete\b", "mirette", text)

    return re.sub(r"\s+", " ", text).strip()


def extract_hotel_aliases(raw_name: str) -> List[str]:
    """
    Extracts all candidate name variants from a raw hotel title including:
    - primary cleaned name
    - bracketed or truncated former names: '(ex. ...)', '(Ex. Serenity Sky Ar', '(dawniej ...)', '(former ...)'
    - unbracketed rename pairs: 'SRNTY Sun Ray X Serenity Alma Heights', 'SERENITY ALPHA EX. MAKADI BEACH'
    - slash-separated dual names with >=2 tokens on each side
    """
    if not raw_name or not isinstance(raw_name, str):
        return []

    raw_s = raw_name.strip()
    variants: List[str] = [raw_s]

    def _add(v: str) -> None:
        vv = re.sub(r"\s+", " ", (v or "").strip(" -–—/,"))
        if vv and vv not in variants and len(vv) >= 3:
            variants.append(vv)

    # 1. Explicit closed OR unclosed (truncated) parenthetical former names
    for m in re.findall(
        r"\((?:ex\.?|dawniej|former|fka|previously|ehem\.?|ehemals)\s+([^)]+)(?:\)|$)",
        raw_s,
        flags=re.I,
    ):
        _add(m)

    # 2. Unbracketed "EX. <old name>" outside parentheses (e.g. "SERENITY ALPHA EX. MAKADI BEACH")
    m_unbr_ex = re.search(r"^(.+?)\s+\bex\.?\s+(.+)$", re.sub(r"\([^)]*\)", "", raw_s), flags=re.I)
    if m_unbr_ex:
        left, right = m_unbr_ex.group(1).strip(), m_unbr_ex.group(2).strip()
        _add(left)
        if len(right.split()) >= 2:
            # Also combine chain prefix if right omitted it (e.g. "SERENITY ALPHA EX. MAKADI BEACH" -> "SERENITY MAKADI BEACH")
            _add(right)
            first_word = left.split()[0] if left.split() else ""
            if fold_unicode(first_word) in {"serenity", "srnty", "pickalbatros", "albatros", "jaz", "rixos", "sunrise", "baron"} and fold_unicode(right.split()[0]) not in {"serenity", "srnty"}:
                _add(f"{first_word} {right}")

    # 3. Rebranding cross separator " X " (e.g. "SRNTY Sun Ray X Serenity Alma Heights")
    m_x = re.match(r"^(.+?)\s+[xX×]\s+(.+)$", raw_s)
    if m_x:
        left, right = m_x.group(1).strip(), m_x.group(2).strip()
        if len(left.split()) >= 2 and len(right.split()) >= 2:
            _add(left)
            _add(right)

    # 4. Primary stripped name
    primary = _strip_rename_and_promo_noise(raw_s, fold_synonyms=False)
    if primary:
        _add(primary)
    # Remove any " X <old>" tail from primary variant if present
    if re.search(r"\s+[xX×]\s+", primary):
        parts = re.split(r"\s+[xX×]\s+", primary)
        for p in parts:
            if len(p.split()) >= 2:
                _add(p)

    # 5. Clean version stripping only (ex./dawniej/former/operator code) parens, keeping branch geo parens like "(Lambi)" for single-word safety
    clean_no_paren = re.sub(r"\((?:ex\.?|dawniej|former|fka|previously|ehem\.?|ehemals|\b[a-z]{2,4}\d*\b)[^)]*(?:\)|$)", " ", raw_s, flags=re.I).strip()
    _add(clean_no_paren)

    return variants


def clean_hotel_name(raw_name: str) -> str:
    """Cleans raw hotel name into sorted canonical search tokens (diacritic-folded, synonyms unified)."""
    base = _strip_rename_and_promo_noise(raw_name, fold_synonyms=True)
    # If rename separator ' X ' survived, keep left half for single-name cleaning
    m_x = re.match(r"^(.+?)\s+[xX×]\s+(.+)$", base)
    if m_x and len(m_x.group(1).split()) >= 2 and len(m_x.group(2).split()) >= 2:
        base = m_x.group(1)

    text = re.sub(r"[-_/,+&.`'’®™]", " ", base)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [t.strip() for t in text.split() if t.strip()]
    meaningful = [t for t in tokens if t not in STOP_WORDS]
    if not meaningful:
        meaningful = [t for t in tokens if t.isalpha()]
    return " ".join(sorted(meaningful))


def _canonicalize_for_key(raw_name: str) -> str:
    """Order-preserving normalized key for O(1) dictionary / alias graph lookups."""
    base = _strip_rename_and_promo_noise(raw_name, fold_synonyms=True)
    text = re.sub(r"[^a-z0-9\s]", " ", base)
    tokens = [t for t in text.split() if t and t not in {"the", "hotel", "hotels", "resort", "resorts", "spa", "all", "inclusive"}]
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# 6. Exact Multi-Stage Similarity & Zero-False-Positive Guards
# ---------------------------------------------------------------------------

_ROMAN_NUMERALS = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5"}


def _extract_unit_numbers(tokens: Iterable[str]) -> Set[str]:
    nums: Set[str] = set()
    for t in tokens:
        if t in _ROMAN_NUMERALS:
            nums.add(_ROMAN_NUMERALS[t])
        elif t.isdigit() and t not in {"5", "4", "3", "16", "18"}:
            # Skip star ratings 3/4/5 and age 16/18+; keep wing numbers like 1, 2
            nums.add(t)
    return nums


def calculate_hotel_similarity(
    name1: str,
    name2: str,
    region_hint1: Optional[str] = None,
    region_hint2: Optional[str] = None,
    url1: Optional[str] = None,
    url2: Optional[str] = None,
) -> float:
    """
    Computes composite similarity [0.0, 1.0] between two hotel names with strict guards:
    - Granular Geo Zone Guard (both title & external region_hint / URL)
    - Generic-Only Literal Guard
    - Chain Sub-Property & Wing Conflict Guard
    - Numeral Guard
    - Truncation awareness for 40-char V1 titles
    """
    if not name1 or not name2:
        return 0.0

    # Check truncation flag before stripping
    is_trunc1 = len(name1.strip()) == 40 and not name1.strip().endswith(")")
    is_trunc2 = len(name2.strip()) == 40 and not name2.strip().endswith(")")

    # 0. External URL ID Match (100% deterministic if both URLs come from same Fly.pl / Check24 entity)
    if url1 and url2:
        oid1, oid2 = extract_fly_object_id(url1), extract_fly_object_id(url2)
        if oid1 and oid2 and oid1 == oid2:
            return 1.0
        cid1, cid2 = extract_check24_hotel_id(url1), extract_check24_hotel_id(url2)
        if cid1 and cid2 and cid1 == cid2:
            return 1.0

    # 1. Geographic Conflict Check (extract BEFORE noise stripping!)
    z1 = extract_geo_zones(name1, region_hint=region_hint1, offer_url=url1)
    z2 = extract_geo_zones(name2, region_hint=region_hint2, offer_url=url2)
    if geo_zones_conflict(z1, z2):
        return 0.0

    c1 = clean_hotel_name(name1)
    c2 = clean_hotel_name(name2)
    if not c1 or not c2:
        return 0.0

    # Exact canonical normalized string match
    raw_k1 = _canonicalize_for_key(name1)
    raw_k2 = _canonicalize_for_key(name2)
    if raw_k1 and raw_k1 == raw_k2:
        toks = set(raw_k1.split())
        if toks.issubset(LOCATION_WORDS | STOP_WORDS):
            return 0.0
        return 1.0

    r1_tokens = set(c1.split())
    r2_tokens = set(c2.split())

    # If a 40-char name truncated the final token (e.g. 'hashees' for 'hasheesh', 'shei' for 'sheikh', 'ar' for 'arc'),
    # normalize trailing partial prefix token cleanly if it prefixes a token in the other set.
    if is_trunc1:
        r1_tokens = {
            next((t2 for t2 in r2_tokens if t2.startswith(t1) and len(t1) >= 2), t1)
            for t1 in r1_tokens
        }
    if is_trunc2:
        r2_tokens = {
            next((t1 for t1 in r1_tokens if t1.startswith(t2) and len(t2) >= 2), t2)
            for t2 in r2_tokens
        }

    # Check if tokens differ by explicit title micro-zones even when wrapped under a parent area (e.g. Gravity Hurghada vs Gravity Sahl Hasheesh)
    loc1 = {t for t in r1_tokens if t in GEO_ZONES}
    loc2 = {t for t in r2_tokens if t in GEO_ZONES}
    if loc1 and loc2:
        mz1 = {GEO_ZONES[t] for t in loc1}
        mz2 = {GEO_ZONES[t] for t in loc2}
        # If explicit title locations point to different micro-zones (even Kemer vs Antalya, Lara vs Side, Hurghada vs Sahl Hasheesh)
        for a in mz1:
            for b in mz2:
                if geo_zones_conflict(a, b):
                    return 0.0
                if a[0] == "hurghada_area" and b[0] == "hurghada_area" and a[1] != b[1]:
                    # Explicitly titled 'Hurghada' vs 'Sahl Hasheesh' / 'Makadi' / 'El Gouna' / 'Soma Bay'
                    return 0.0

    # Strip location tokens for core comparison, EXCEPT keep a city/location name if it is the ONLY differentiator
    core1 = {t for t in r1_tokens if t not in LOCATION_WORDS}
    core2 = {t for t in r2_tokens if t not in LOCATION_WORDS}
    if not core1:
        core1 = set(r1_tokens)
    if not core2:
        core2 = set(r2_tokens)

    # 2. Numeral Guard (e.g. Sunrise 1 vs Sunrise 2)
    n1 = _extract_unit_numbers(r1_tokens)
    n2 = _extract_unit_numbers(r2_tokens)
    if n1 and n2 and not n1.intersection(n2):
        return 0.0

    # 3. Generic-Only / Single-Generic-Word Guard
    # Prevent "The Grand Resort" == "The Grand Hotel Hurghada" == "Grand Makadi" and "Royal Olympic" == "Olympic Star"
    d1 = r1_tokens - LOCATION_WORDS - SOFT_DESCRIPTORS - STOP_WORDS
    d2 = r2_tokens - LOCATION_WORDS - SOFT_DESCRIPTORS - STOP_WORDS

    if not d1 or not d2:
        # Both names consist purely of generic words + locations (like "The Grand Resort" vs "The Grand Hotel Sharm")
        f1 = set(fold_unicode(name1).split()) - {"the", "a", "an", "and", "&"}
        f2 = set(fold_unicode(name2).split()) - {"the", "a", "an", "and", "&"}
        # Strip explicit country words only
        f1 = {t for t in f1 if t not in {"egipt", "egypt", "turcja", "turkey", "grecja", "greece"}}
        f2 = {t for t in f2 if t not in {"egipt", "egypt", "turcja", "turkey", "grecja", "greece"}}
        if "resort" in f1 and "hotel" in f2 or "hotel" in f1 and "resort" in f2:
            if len(core1) <= 2 and len(core2) <= 2:
                return 0.0
        # Require non-location cores to match identically AND geo zones not to disagree (nor one missing city vs named city like Grand Makadi)
        if core1 != core2 or (loc1 != loc2 and ("grand" in core1 or "royal" in core1 or "star" in core1)):
            return 0.0

    # 4. Distinctive Core Token Intersection (with prefix/stem allowance for blu/blue, single typo)
    if d1 and d2:
        # Normalize minor suffix variants like blu -> blue
        d1_norm = {"blue" if t == "blu" else t for t in d1}
        d2_norm = {"blue" if t == "blu" else t for t in d2}
        d_inter = d1_norm & d2_norm
        if not d_inter:
            return 0.0
        # Guard against Royal Olympic vs Olympic Star:
        # If there is ONLY 1 overlapping distinctive word and the other distinctive words are different proper nouns
        # AND SOFT_DESCRIPTORS differ (e.g. Royal vs Star), reject!
        if len(d_inter) == 1 and len(d1_norm) == 1 and len(d2_norm) == 1:
            soft_diff = (core1 ^ core2) & {"royal", "star", "grand", "plaza", "empire", "elite", "kingdom", "nickelodeon"}
            if soft_diff:
                return 0.0
        # If one side has multiple distinctive words (e.g. "the royal senses" vs "aulus lindos"), require high distinctive coverage
        # Unless one side is a curated alias handled by HotelAliasGraph
        min_d_cov = len(d_inter) / max(len(d1_norm), len(d2_norm))
        # Example: "Ramada Plaza Antalya" vs "Ramada Resort Lara": both have {ramada}, one has 'plaza' vs 'resort' -> blocked by geo & soft_diff
        # Example: "Royal Olympic" ({olympic}, soft={royal}) vs "Olympic Star" ({olympic}, soft={star}) -> blocked!
        # Example: "Ariadne Apartments & Studios" ({ariadne, apartments, studios}) vs "Panorama Sea View Studios and Apartments" ({panorama, view, studios, apartments})
        # Reject if overlap is ONLY taxonomy nouns like apartments/studios/suites/villas!
        TAXONOMY_ONLY = {"apartments", "apartment", "studios", "studio", "villas", "villa", "suites", "suite", "rooms", "boutique", "beachfront"}
        if d_inter.issubset(TAXONOMY_ONLY):
            return 0.0
    else:
        return 0.0

    # 5. Strong Brand & Sub-Property / Sister-Hotel Conflict Guard
    b1 = r1_tokens & STRONG_BRANDS
    b2 = r2_tokens & STRONG_BRANDS
    # Fold albatros -> pickalbatros for brand checking
    b1_f = {"pickalbatros" if x == "albatros" else x for x in b1}
    b2_f = {"pickalbatros" if x == "albatros" else x for x in b2}
    if b1_f and b2_f and not b1_f.intersection(b2_f):
        # Different famous hotel brands (except Iberotel <-> Jaz handled in AliasGraph!)
        return 0.0

    # Check Wing / Sub-Property Conflict (both when sharing a brand OR sharing a complex name like Charmillion / Fort Arabesque / Domina)
    c1_norm = {"blue" if t == "blu" else t for t in core1}
    c2_norm = {"blue" if t == "blu" else t for t in core2}

    sub1 = c1_norm & CONFLICTING_UNIT_TOKENS
    sub2 = c2_norm & CONFLICTING_UNIT_TOKENS
    if sub1 != sub2:
        sym_diff = sub1 ^ sub2
        # Case A: Mutually exclusive wings/concepts (e.g. Club Resort vs Club Aquapark, Elisir vs Oasis, West Bay vs Beach Resort)
        is_subset = sub1.issubset(sub2) or sub2.issubset(sub1)
        if not is_subset:
            return 0.0
        # Case B: One is strict subset of the other. Allow ONLY if the extra tokens are pure optional infrastructure tags
        # AND they do NOT change a hotel's type (e.g. 'Sharm Plaza' vs 'Sharm Grand Plaza', 'Club' vs 'Club Aquapark'!)
        extra = sym_diff
        # Extra 'aquapark' IS allowed ONLY if the shorter hotel doesn't end in 'club' or 'resort' where sister aquapark exists, OR when shorter is e.g. Titanic Beach -> Titanic Beach Spa & Aqua Park!
        # Wait: "Charmillion Club Resort" vs "Charmillion Club Aquapark" -> NOT a subset (resort vs aquapark -> blocked above by Case A if 'resort' retained or handled here)!
        if "resort" in set(fold_unicode(name1).split()) and "aquapark" in extra:
            if "club" in c1_norm or "gardens" in c1_norm or "aqua" in extra:
                return 0.0
        if "resort" in set(fold_unicode(name2).split()) and "aquapark" in extra:
            if "club" in c2_norm or "gardens" in c2_norm or "aqua" in extra:
                return 0.0
        # Never ignore proper sub-unit differentiators (grand, star, royal, palace, beach, plaza, vista, west, elisir, etc.)
        STRICT_UNIT_ONLY = {
            "jungle", "dana", "citadel", "moderna", "lagoon", "vista", "remal", "diamond",
            "oasis", "saraya", "coraya", "lamaya", "samaya", "maraya", "riviera", "white",
            "crystal", "mirabel", "miracle", "nirvana", "imperial", "diva", "be", "elite",
            "downtown", "kingdom", "nickelodeon", "tirana", "radamis", "seagate", "west",
            "elisir", "plaza", "grand", "royal", "star", "palace", "gardens", "garden",
            "alpha", "alma", "sun", "ray", "sea", "reef", "sky", "arc", "queen", "crown",
            "atlantis", "arcadia", "belvil", "zeugma", "botanik", "platinum", "sungate",
            "bay", "hills", "albatross", "fantasia", "aldau", "alaya", "alcazar", "fayrouz",
            "bluemarine", "acquamarine", "solymar", "sahl", "hasheesh",
            "blue", "pearl", "holidays", "boutique", "makadi", "aqua",
        }
        # Allow location-redundant suffix like "Pickalbatros Citadel Resort" vs "Pickalbatros Citadel Sahl Hasheesh"
        # Also allow "Star Beach Village" vs "Star Beach Village & Waterpark" (where extra='aquapark' on non-brand/non-club resort)
        extra_non_loc = extra - {"sahl", "hasheesh", "lara", "bay"}
        # Allow 'beach' / 'village' / 'resort' difference ONLY if not competing sister names (e.g. Kakkos Beach vs Bay, Asterias Bay vs Village)
        if extra_non_loc == {"aquapark"} and not b1_f and not b2_f and "club" not in c1_norm and "club" not in c2_norm:
            extra_non_loc = set()
        # Reject single-word name matching another hotel with a differing unit type when a title has explicit branch city parens like 'Atlantis (Lambi)' vs 'Atlantis Beach Hotel'
        # Exclude '(ex. ...)' / '(dawniej ...)' / '(former ...)' parens which indicate rebrands, not branches.
        m_p1 = re.search(r"\(([^)]+)\)\s*$", name1.strip())
        m_p2 = re.search(r"\(([^)]+)\)\s*$", name2.strip())
        has_branch_paren1 = bool(m_p1 and not re.match(r"^(?:ex\.?|dawniej|former|fka|ehem)", m_p1.group(1).strip(), re.I)) and z1[1] is not None and z2[1] is None
        has_branch_paren2 = bool(m_p2 and not re.match(r"^(?:ex\.?|dawniej|former|fka|ehem)", m_p2.group(1).strip(), re.I)) and z2[1] is not None and z1[1] is None
        if (has_branch_paren1 or has_branch_paren2) and sym_diff:
            return 0.0
        if extra_non_loc & STRICT_UNIT_ONLY:
            if b1_f or b2_f or len(extra_non_loc) >= 1:
                return 0.0

    # Multi-location chain guard: if chain requires geo match and BOTH names have NO title geo, rely on region_hint/url check done in Step 1!
    # Additional check: if chain is multi-location and ONE side explicitly puts a resort town in parens/title while the other has NO location at all -> allow only if DB region_hint agrees!

    # 6. Composite Jaccard + Sequence Similarity
    inter = c1_norm & c2_norm
    if not inter:
        return 0.0
    union = c1_norm | c2_norm
    jaccard = len(inter) / max(1, len(union))

    # Boost clean subset matches where only descriptive tails (e.g. 'deluxe', 'villas', 'lifestyle', 'aquapark' on unique hotel) differ
    clean_subset = False
    if c1_norm.issubset(c2_norm) or c2_norm.issubset(c1_norm):
        diff_toks = (c1_norm ^ c2_norm) - OPTIONAL_INFRA_TAIL_WORDS - SOFT_DESCRIPTORS - {"aquapark"}
        if not diff_toks:
            jaccard = max(jaccard, 0.90)
            clean_subset = True

    str1 = " ".join(sorted(c1_norm))
    str2 = " ".join(sorted(c2_norm))
    seq_ratio = difflib.SequenceMatcher(None, str1, str2).ratio()
    if clean_subset:
        return round(0.75 * jaccard + 0.25 * seq_ratio, 3)
    return round(0.60 * jaccard + 0.40 * seq_ratio, 3)


# ---------------------------------------------------------------------------
# 7. Canonical Rename & Alias Graph Registry
# ---------------------------------------------------------------------------


class UnionFind:
    def __init__(self) -> None:
        self.parent: Dict[str, str] = {}

    def find(self, x: str) -> str:
        if x not in self.parent:
            self.parent[x] = x
            return x
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> str:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra
        return ra


class HotelEntityMatcher:
    def __init__(
        self,
        cache_file: str = DEFAULT_CACHE_FILE,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ):
        self.cache_file = cache_file
        self.similarity_threshold = similarity_threshold
        self.mappings: Dict[str, str] = {}  # polish_name -> german_name (exact curated pairs)
        self.canonical_kb: Dict[str, Any] = {}
        self.blacklist_pairs: Set[Tuple[str, str]] = set()

        # Transitive alias clusters from hotel_aliases_kb.json
        self.clusters: Dict[str, Dict[str, Any]] = {}
        self.key_to_clusters: Dict[str, List[str]] = {}
        self.oid_to_cluster: Dict[Tuple[str, str], str] = {}
        self.slug_to_cluster: Dict[Tuple[str, str], str] = {}
        self.check24_id_to_cluster: Dict[str, str] = {}
        self._cand_index_cache: Dict[Tuple[Any, ...], Dict[str, Any]] = {}

        self._load_canonical_kb()
        self._load_aliases_kb()

    def _load_canonical_kb(self) -> None:
        """Loads pre-verified 1:1 cross-border mappings and blacklist."""
        possible_paths = [
            Path(__file__).resolve().parents[1] / "knowledge" / "hotel_canonical_crossborder_kb.json",
            Path(__file__).resolve().parent / "hotel_canonical_crossborder_kb.json",
            Path(os.getcwd()) / "hotel_canonical_crossborder_kb.json",
        ]
        for p in possible_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.canonical_kb = data
                    for item in data.get("blacklist_mismatches", []):
                        pl = fold_unicode(item.get("pl", "")).strip()
                        de = fold_unicode(item.get("de", "")).strip()
                        if pl and de:
                            self.blacklist_pairs.add((pl, de))
                            self.blacklist_pairs.add((de, pl))
                    for pl_name, rec in data.get("pl_to_de", {}).items():
                        de_name = rec.get("german_name", "")
                        if de_name:
                            self.mappings[pl_name] = de_name
                    break
                except Exception as e:
                    logger.warning(f"Failed to load hotel_canonical_crossborder_kb.json: {e}")

    def _load_aliases_kb(self) -> None:
        """Loads hotel_aliases_kb.json and builds O(1) alias & external-ID lookup indices."""
        kb_paths = [
            Path(__file__).resolve().parents[1] / "knowledge" / "hotel_aliases_kb.json",
            Path(__file__).resolve().parent / "hotel_aliases_kb.json",
        ]
        data: Dict[str, Any] = {}
        for p in kb_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    break
                except Exception as e:
                    logger.warning(f"Failed to load hotel_aliases_kb.json: {e}")

        for cid, rec in (data.get("clusters") or {}).items():
            ctry = fold_unicode(rec.get("country") or "").strip()
            aliases = list(rec.get("aliases") or [])
            if rec.get("canonical_name") and rec["canonical_name"] not in aliases:
                aliases.insert(0, rec["canonical_name"])
            norm_keys = set()
            for a in aliases:
                for sub_a in extract_hotel_aliases(a):
                    k = _canonicalize_for_key(sub_a)
                    if k:
                        norm_keys.add(k)
                        self.key_to_clusters.setdefault(k, [])
                        if cid not in self.key_to_clusters[k]:
                            self.key_to_clusters[k].append(cid)
                    clean_k = clean_hotel_name(sub_a)
                    if clean_k:
                        norm_keys.add(clean_k)
                        self.key_to_clusters.setdefault(clean_k, [])
                        if cid not in self.key_to_clusters[clean_k]:
                            self.key_to_clusters[clean_k].append(cid)

            oids = {str(x) for x in (rec.get("fly_object_ids") or []) if x}
            slugs = {str(x).lower() for x in (rec.get("fly_slugs") or []) if x}
            c24_ids = {str(x) for x in (rec.get("check24_hotel_ids") or []) if x}

            for oid in oids:
                self.oid_to_cluster[(ctry, oid)] = cid
            for sl in slugs:
                self.slug_to_cluster[(ctry, sl)] = cid
            for c24 in c24_ids:
                self.check24_id_to_cluster[c24] = cid

            self.clusters[cid] = {
                "cluster_id": cid,
                "canonical_name": rec.get("canonical_name") or (aliases[0] if aliases else cid),
                "country": rec.get("country") or "",
                "country_norm": ctry,
                "geo_zone": rec.get("geo_zone"),
                "aliases": aliases,
                "norm_keys": norm_keys,
                "fly_object_ids": oids,
                "fly_slugs": slugs,
                "check24_hotel_ids": c24_ids,
            }

    def get_alias_variants(
        self,
        name: str,
        country: Optional[str] = None,
        offer_url: Optional[str] = None,
    ) -> List[str]:
        """Returns all known aliases/renames for a hotel name via external IDs + alias graph + title parsing."""
        variants = extract_hotel_aliases(name)
        seen_norm = {_canonicalize_for_key(v) for v in variants}

        matched_cids: List[str] = []
        ctry_norm = fold_unicode(country or "").strip()

        if offer_url:
            oid = extract_fly_object_id(offer_url)
            if oid:
                if (ctry_norm, oid) in self.oid_to_cluster:
                    matched_cids.append(self.oid_to_cluster[(ctry_norm, oid)])
                elif not ctry_norm:
                    for (c_k, o_k), cid in self.oid_to_cluster.items():
                        if o_k == oid:
                            matched_cids.append(cid)
            sl = extract_fly_url_slug(offer_url)
            if sl and (ctry_norm, sl) in self.slug_to_cluster:
                matched_cids.append(self.slug_to_cluster[(ctry_norm, sl)])
            c24 = extract_check24_hotel_id(offer_url)
            if c24 and c24 in self.check24_id_to_cluster:
                matched_cids.append(self.check24_id_to_cluster[c24])

        for v in list(variants):
            for key in (_canonicalize_for_key(v), clean_hotel_name(v)):
                if not key:
                    continue
                for cid in self.key_to_clusters.get(key, []):
                    cl = self.clusters.get(cid)
                    if not cl:
                        continue
                    if ctry_norm and cl["country_norm"] and cl["country_norm"] != ctry_norm:
                        continue
                    if cid not in matched_cids:
                        matched_cids.append(cid)

        for cid in matched_cids:
            cl = self.clusters[cid]
            for a in cl["aliases"]:
                ak = _canonicalize_for_key(a)
                if ak not in seen_norm:
                    seen_norm.add(ak)
                    variants.append(a)
                elif a not in variants:
                    variants.append(a)

        return variants

    def _get_candidate_index(
        self,
        candidate_names: List[str],
        destination: Optional[str] = None,
        candidate_meta: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        sig = (
            len(candidate_names),
            candidate_names[0] if candidate_names else "",
            candidate_names[-1] if candidate_names else "",
            fold_unicode(destination or ""),
            bool(candidate_meta),
        )
        cached = self._cand_index_cache.get(sig)
        if cached is not None:
            return cached

        cand_lookup_lower = {fold_unicode(c.strip()): c for c in candidate_names}
        cand_alias_norm_map: Dict[str, List[str]] = {}
        cand_aliases_map: Dict[str, List[str]] = {}
        token_to_cands: Dict[str, List[str]] = {}

        for cand in candidate_names:
            c_meta = (candidate_meta or {}).get(cand, {})
            c_aliases = self.get_alias_variants(cand, country=destination, offer_url=c_meta.get("offer_url"))
            cand_aliases_map[cand] = c_aliases
            seen_toks: Set[str] = set()
            for ca in c_aliases:
                ck = _canonicalize_for_key(ca)
                if ck and not set(ck.split()).issubset(LOCATION_WORDS | STOP_WORDS):
                    cand_alias_norm_map.setdefault(ck, [])
                    if cand not in cand_alias_norm_map[ck]:
                        cand_alias_norm_map[ck].append(cand)
                for tok in clean_hotel_name(ca).split():
                    if tok not in LOCATION_WORDS and tok not in STOP_WORDS:
                        seen_toks.add(tok)
                        if tok == "blu":
                            seen_toks.add("blue")
                        elif tok == "blue":
                            seen_toks.add("blu")
            for tok in seen_toks:
                token_to_cands.setdefault(tok, []).append(cand)

        idx = {
            "cand_lookup_lower": cand_lookup_lower,
            "cand_alias_norm_map": cand_alias_norm_map,
            "cand_aliases_map": cand_aliases_map,
            "token_to_cands": token_to_cands,
        }
        if len(self._cand_index_cache) < 64:
            self._cand_index_cache[sig] = idx
        return idx

    def match_hotel(
        self,
        target_name: str,
        candidate_names: List[str],
        destination: Optional[str] = None,
        target_stars: Optional[int] = None,
        region_hint: Optional[str] = None,
        offer_url: Optional[str] = None,
        candidate_meta: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Optional[Tuple[str, float]]:
        """
        Matches a target hotel against candidate names using:
        1. Transitive Rename & Alias Graph + External IDs (1.000)
        2. Curated 1:1 Crossborder KB (1.000, after blacklist & geo validation)
        3. Strict Inverted-Index + Multi-Stage Similarity with Geo, Brand/Wing & Generic Guards
        """
        if not target_name or not candidate_names:
            return None

        clean_target = target_name.strip()
        target_lower = fold_unicode(clean_target)
        idx = self._get_candidate_index(candidate_names, destination=destination, candidate_meta=candidate_meta)
        cand_lookup_lower = idx["cand_lookup_lower"]
        cand_alias_norm_map = idx["cand_alias_norm_map"]
        cand_aliases_map = idx["cand_aliases_map"]
        token_to_cands = idx["token_to_cands"]

        # Expand aliases transitively (handles renames like Serenity Alma Heights <-> SRNTY Sun Ray)
        aliases = self.get_alias_variants(clean_target, country=destination, offer_url=offer_url)
        z_target = extract_geo_zones(clean_target, destination, region_hint, offer_url)

        # 1. Exact Check24 / Alias Cluster Candidate Lookup
        for a in aliases:
            a_low = fold_unicode(a)
            if a_low in cand_lookup_lower:
                cand = cand_lookup_lower[a_low]
                if (target_lower, fold_unicode(cand.strip())) not in self.blacklist_pairs:
                    meta = (candidate_meta or {}).get(cand, {})
                    if not geo_zones_conflict(
                        z_target,
                        extract_geo_zones(cand, destination, meta.get("region"), meta.get("offer_url")),
                    ):
                        return (cand, 1.0)

        # 2. Direct / Alias Curated KB Lookup (validate no geo conflict!)
        for a in aliases:
            for k in (a, clean_target):
                if k in self.mappings:
                    mapped = self.mappings[k]
                    mapped_low = fold_unicode(mapped.strip())
                    cand = cand_lookup_lower.get(mapped_low) or (mapped if mapped in candidate_names else None)
                    if cand and (target_lower, fold_unicode(cand.strip())) not in self.blacklist_pairs:
                        meta = (candidate_meta or {}).get(cand, {})
                        if not geo_zones_conflict(
                            z_target,
                            extract_geo_zones(cand, destination, meta.get("region"), meta.get("offer_url")),
                        ):
                            return (cand, 1.0)

        # 3. Check normalized alias key overlap against candidate aliases
        for a in aliases:
            ak = _canonicalize_for_key(a)
            if ak in cand_alias_norm_map:
                for cand in cand_alias_norm_map[ak]:
                    if (target_lower, fold_unicode(cand.strip())) in self.blacklist_pairs:
                        continue
                    c_meta = (candidate_meta or {}).get(cand, {})
                    if not geo_zones_conflict(
                        z_target,
                        extract_geo_zones(cand, destination, c_meta.get("region"), c_meta.get("offer_url")),
                    ):
                        return (cand, 1.0)

        # 4. Shortlist candidates via inverted token index (zero-overlap candidates score 0.0 by rule)
        shortlist: List[str] = []
        seen_cands: Set[str] = set()
        for a in aliases:
            for tok in clean_hotel_name(a).split():
                if tok in LOCATION_WORDS or tok in STOP_WORDS:
                    continue
                for cand in token_to_cands.get(tok, ()):
                    if cand not in seen_cands:
                        seen_cands.add(cand)
                        shortlist.append(cand)

        if not shortlist:
            return None

        best_candidate: Optional[str] = None
        best_score = 0.0

        for cand in shortlist:
            cand_lower = fold_unicode(cand.strip())
            if (target_lower, cand_lower) in self.blacklist_pairs:
                continue

            c_meta = (candidate_meta or {}).get(cand, {})
            c_reg = c_meta.get("region")
            c_url = c_meta.get("offer_url")
            c_stars = c_meta.get("stars")

            z_cand = extract_geo_zones(cand, destination, c_reg, c_url)
            if geo_zones_conflict(z_target, z_cand):
                continue
            if z_target[0] == "hurghada_area" and z_cand[0] == "hurghada_area" and z_target[1] != z_cand[1]:
                continue

            # Strict Star Gap Guard (if both clearly known and differ by >= 2 stars, reject)
            if target_stars and c_stars and abs(int(target_stars) - int(c_stars)) >= 2:
                continue

            c_aliases = cand_aliases_map.get(cand, [cand])
            for a in aliases:
                for ca in c_aliases:
                    score = calculate_hotel_similarity(
                        a,
                        ca,
                        region_hint1=region_hint,
                        region_hint2=c_reg,
                        url1=offer_url,
                        url2=c_url,
                    )
                    if score > best_score:
                        best_score = score
                        best_candidate = cand

        if best_candidate and best_score >= self.similarity_threshold:
            return (best_candidate, best_score)

        return None

    def resolve_canonical_cluster_id(
        self,
        name: str,
        country: Optional[str] = None,
        offer_url: Optional[str] = None,
    ) -> Optional[str]:
        """Returns the canonical cluster hotel_id if this hotel/rename/URL belongs to a known cluster."""
        ctry_norm = fold_unicode(country or "").strip()
        if offer_url:
            oid = extract_fly_object_id(offer_url)
            if oid and (ctry_norm, oid) in self.oid_to_cluster:
                return self.oid_to_cluster[(ctry_norm, oid)]
            sl = extract_fly_url_slug(offer_url)
            if sl and (ctry_norm, sl) in self.slug_to_cluster:
                cid = self.slug_to_cluster[(ctry_norm, sl)]
                cl = self.clusters.get(cid)
                if cl and any(calculate_hotel_similarity(name, a) >= 0.85 for a in cl.get("aliases", [])):
                    return cid

        for v in extract_hotel_aliases(name):
            for key in (_canonicalize_for_key(v), clean_hotel_name(v)):
                if not key:
                    continue
                for cid in self.key_to_clusters.get(key, []):
                    cl = self.clusters.get(cid)
                    if not cl:
                        continue
                    if ctry_norm and cl["country_norm"] and cl["country_norm"] != ctry_norm:
                        continue
                    if not geo_zones_conflict(
                        extract_geo_zones(name, country, offer_url=offer_url),
                        extract_geo_zones(cl["canonical_name"], cl["country"]),
                    ):
                        return cid
        return None

    def match_all_pairs(
        self,
        polish_hotels: List[str],
        german_hotels: List[str],
    ) -> Dict[str, Tuple[str, float]]:
        matched: Dict[str, Tuple[str, float]] = {}
        unique_pl = list(set(polish_hotels))
        unique_de = list(set(german_hotels))
        for pl_h in unique_pl:
            res = self.match_hotel(pl_h, unique_de)
            if res:
                matched[pl_h] = res
        return matched
