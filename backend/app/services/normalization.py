"""
Shared canonical normalization helpers for airports, board basis, countries, and URL dates.
Single source of truth used across live_scraper, sync scripts, analytics, catalog, and DB sanitization.
"""

from __future__ import annotations

import re
import urllib.parse
from datetime import date
from typing import Iterable, Optional, Set, Tuple

_AIRPORT_MAP = {
    "waw": "WAW",
    "warszawa": "WAW",
    "okecie": "WAW",
    "okęcie": "WAW",
    "warsaw": "WAW",
    "chopin": "WAW",
    "wmi": "WMI",
    "modlin": "WMI",
    "rdo": "RDO",
    "radom": "RDO",
    "ktw": "KTW",
    "katowice": "KTW",
    "krk": "KRK",
    "krakow": "KRK",
    "kraków": "KRK",
    "wro": "WRO",
    "wroclaw": "WRO",
    "wrocław": "WRO",
    "gdn": "GDN",
    "gdansk": "GDN",
    "gdańsk": "GDN",
    "poz": "POZ",
    "poznan": "POZ",
    "poznań": "POZ",
    "rze": "RZE",
    "rzeszow": "RZE",
    "rzeszów": "RZE",
    "bzg": "BZG",
    "bydgoszcz": "BZG",
    "lcj": "LCJ",
    "lodz": "LCJ",
    "łódź": "LCJ",
    "luz": "LUZ",
    "lublin": "LUZ",
    "ieg": "IEG",
    "zielona": "IEG",
    "szz": "SZZ",
    "szczecin": "SZZ",
    "ber": "BER",
    "berlin": "BER",
}


def normalize_airport_code(raw: Optional[str], offer_url: Optional[str] = None) -> str:
    """Normalizes Polish/German departure airport names into canonical 3-letter IATA codes."""
    candidates = []
    if offer_url:
        try:
            m = re.search(r"[?&](?:departureLocation|airport)=([^&#]+)", offer_url, re.I)
            if m:
                url_loc = urllib.parse.unquote_plus(m.group(1)).strip()
                candidates.append(url_loc)
        except Exception:
            pass
    if raw:
        candidates.append(str(raw).strip())

    # Prioritize raw first unless raw is an "ALL/ANY/ВСЕ" placeholder
    raw_low = str(raw or "").lower().strip()
    is_placeholder = not raw_low or "все" in raw_low or raw_low in ("all", "any", "-")
    ordered = candidates if is_placeholder else list(reversed(candidates))

    for cand in ordered:
        c = cand.lower().strip()
        if not c or "все" in c or c in ("all", "any"):
            continue
        if "modlin" in c:
            return "WMI"
        if "radom" in c:
            return "RDO"
        if "okęcie" in c or "okecie" in c or "chopin" in c:
            return "WAW"
        if "zielona" in c:
            return "IEG"
        for key, code in _AIRPORT_MAP.items():
            if c == key or key in c:
                return code
        up = cand.strip().upper()
        if len(up) == 3 and up.isalpha():
            return up

    return "ALL" if is_placeholder else (str(raw or "WAW").strip()[:10].upper() or "WAW")


def normalize_board_basis(raw: Optional[str]) -> str:
    """Canonicalizes board basis / catering strings to prevent cohort fragmentation and false AI/RO mixes."""
    s = str(raw or "").strip().lower()
    if not s:
        return "All Inclusive"
    if any(k in s for k in ("ultra", "uai", "ultimate", "premium ai")):
        return "Ultra All Inclusive"
    if "all" in s or s == "hai" or re.search(r"\b(?:ai|hai)\b", s):
        return "All Inclusive"
    if any(k in s for k in ("full board", "pełne wyż", "pelne wyz", "fb")):
        return "FB (Full Board)"
    if any(k in s for k in ("obiadokol", "half board", "dwa posił", "hb")):
        return "HB (Half Board)"
    if any(k in s for k in ("śniad", "sniad", "breakfast", "bb")):
        return "BB (Śniadania)"
    if any(k in s for k in ("bez wyż", "bez wyz", "self catering", "room only", "ro", "własne", "без пит")):
        return "RO (Bez wyżywienia)"
    return "All Inclusive" if "włącz" in s else str(raw).strip()[:64]


def normalize_country_ru(raw: Optional[str]) -> str:
    s = str(raw or "").strip().lower()
    if any(k in s for k in ("турц", "turk", "turcj")):
        return "Турция"
    if any(k in s for k in ("егип", "egypt", "egipt")):
        return "Египет"
    if any(k in s for k in ("грец", "gree", "grecj")):
        return "Греция"
    if any(k in s for k in ("кипр", "cypr")):
        return "Кипр"
    if any(k in s for k in ("испан", "spain", "hiszpan")):
        return "Испания"
    if any(k in s for k in ("тунис", "tunis", "tunezj")):
        return "Тунис"
    if any(k in s for k in ("болгар", "bulgar")):
        return "Болгария"
    if any(k in s for k in ("оаэ", "uae", "emirates")):
        return "ОАЭ"
    return str(raw or "").strip() or "Турция"


def normalize_dest_slug(raw: Optional[str]) -> str:
    s = str(raw or "").strip().lower()
    if any(k in s for k in ("турц", "turk", "turcj")):
        return "turkey"
    if any(k in s for k in ("егип", "egypt", "egipt")):
        return "egypt"
    if any(k in s for k in ("грец", "gree", "grecj")):
        return "greece"
    if any(k in s for k in ("кипр", "cypr")):
        return "cyprus"
    if any(k in s for k in ("испан", "spain", "hiszpan")):
        return "spain"
    if any(k in s for k in ("тунис", "tunis", "tunezj")):
        return "tunisia"
    if any(k in s for k in ("болгар", "bulgar")):
        return "bulgaria"
    if any(k in s for k in ("оаэ", "uae", "emirates")):
        return "uae"
    return s


def extract_offer_url_dates(offer_url: Optional[str]) -> Tuple[Optional[date], Optional[date]]:
    """Extracts authoritative YYYY-MM-DD departureDate and returnDate from Fly.pl offer_url query params."""
    if not offer_url:
        return None, None
    dep_d: Optional[date] = None
    ret_d: Optional[date] = None
    m_dep = re.search(r"[?&]departureDate=(\d{4}-\d{2}-\d{2})", offer_url)
    if m_dep:
        try:
            dep_d = date.fromisoformat(m_dep.group(1))
        except ValueError:
            pass
    m_ret = re.search(r"[?&]returnDate=(\d{4}-\d{2}-\d{2})", offer_url)
    if m_ret:
        try:
            ret_d = date.fromisoformat(m_ret.group(1))
        except ValueError:
            pass
    return dep_d, ret_d


def normalize_requested_airports(requested_airports: Optional[Iterable[str]]) -> Set[str]:
    """Converts a list/iterable of airport codes or city names into canonical 3-letter IATA codes.
    Returns an empty set when no specific restriction applies (None, empty, ALL/ВСЕ).
    """
    if not requested_airports:
        return set()
    codes: Set[str] = set()
    for raw in requested_airports:
        s = str(raw or "").strip()
        if not s:
            continue
        low = s.lower()
        if low in ("all", "any", "все", "wszystkie", "-"):
            return set()
        code = normalize_airport_code(s)
        if code and code != "ALL":
            codes.add(code)
    return codes


def matches_requested_airports(
    raw_airport: Optional[str],
    requested_airports: Optional[Iterable[str]],
    offer_url: Optional[str] = None,
) -> bool:
    """Returns True if raw_airport matches any canonical IATA code in requested_airports (or no filter)."""
    req_codes = normalize_requested_airports(requested_airports)
    if not req_codes:
        return True
    ap_code = normalize_airport_code(raw_airport, offer_url)
    return ap_code in req_codes
