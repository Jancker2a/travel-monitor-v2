import re
import urllib.parse
from typing import Optional, Dict, Any, List
from app.schemas.monitor import FlyUrlParseResponse

# Polish to internal destination/country mapping
COUNTRY_SLUG_MAP = {
    "turcja": "turkey",
    "turkey": "turkey",
    "egipt": "egypt",
    "egypt": "egypt",
    "grecja": "greece",
    "greece": "greece",
    "cypr": "cyprus",
    "cyprus": "cyprus",
    "hiszpania": "spain",
    "spain": "spain",
    "bulgaria": "bulgaria",
    "bułgaria": "bulgaria",
    "tunezja": "tunisia",
    "tunisia": "tunisia",
    "emiraty": "uae",
    "zjednoczone-emiraty-arabskie": "uae",
    "uae": "uae",
    "wlochy": "italy",
    "włochy": "italy",
    "italy": "italy",
    "malta": "malta",
}

REGION_SLUG_MAP = {
    # Turkey
    "antalyjski": "turkey_antalya",
    "antalya": "turkey_antalya",
    "riwiera-turecka": "turkey_antalya",
    "alanya": "turkey_alanya",
    "side": "turkey_side",
    "kemer": "turkey_kemer",
    "belek": "turkey_belek",
    "egejska": "turkey_aegean",
    "bodrum": "turkey_bodrum",
    "marmaris": "turkey_marmaris",
    # Egypt
    "sharm-el-sheikh": "egypt_sharm",
    "hurghada": "egypt_hurghada",
    "marsa-alam": "egypt_marsa",
    # Greece
    "kreta": "greece_crete",
    "rodos": "greece_rhodes",
    "korfu": "greece_corfu",
    "zakynthos": "greece_zakynthos",
    "kos": "greece_kos",
    # Spain
    "majorka": "spain_mallorca",
    "mallorca": "spain_mallorca",
    "wyspy-kanaryjskie": "spain_canary",
    "teneryfa": "spain_canary",
    "fuerteventura": "spain_canary",
    "gran-canaria": "spain_canary",
    "costa-del-sol": "spain_costa_del_sol",
    "costa-blanca": "spain_costa_blanca",
}

CATERING_MAP = {
    "all-inclusive": "all-inclusive",
    "all": "all-inclusive",
    "ultra-all-inclusive": "all-inclusive",
    "all-inclusive-ultra": "all-inclusive",
    "2-posilki": "half-board",
    "hb": "half-board",
    "sniadania": "breakfast",
    "bb": "breakfast",
    "bez-wyzywienia": "room-only",
    "ro": "room-only",
}


class FlyUrlParser:
    """Robust parser converting raw fly.pl URLs into internal search parameters."""

    @classmethod
    def parse(cls, raw_url: str) -> FlyUrlParseResponse:
        url_str = (raw_url or "").strip()
        if not url_str:
            return FlyUrlParseResponse(
                is_valid=False,
                parsed_title="Пустая ссылка",
                error_message="Вставьте корректную ссылку с сайта fly.pl",
            )

        if "fly.pl" not in url_str.lower():
            return FlyUrlParseResponse(
                is_valid=False,
                parsed_title="Неподдерживаемый сайт",
                error_message="Поддерживаются только ссылки поисковой выдачи https://fly.pl",
            )

        try:
            parsed = urllib.parse.urlparse(url_str)
            path_parts = [p.lower() for p in parsed.path.strip("/").split("/") if p]
            qs = urllib.parse.parse_qs(parsed.query)

            # 1. Determine destination and region from path or query
            dest_key: Optional[str] = None
            region_key: Optional[str] = None
            catering: Optional[str] = None

            for part in path_parts:
                if part in ("wyszukiwarka", "wczasy", "wycieczki", "last-minute", "all-inclusive"):
                    if part == "all-inclusive" and not catering:
                        catering = "all-inclusive"
                    continue
                if part in COUNTRY_SLUG_MAP and not dest_key:
                    dest_key = COUNTRY_SLUG_MAP[part]
                elif part in REGION_SLUG_MAP and not region_key:
                    region_key = REGION_SLUG_MAP[part]
                elif part in CATERING_MAP and not catering:
                    catering = CATERING_MAP[part]

            # Query params override
            if "kraj" in qs and qs["kraj"][0] in COUNTRY_SLUG_MAP:
                dest_key = COUNTRY_SLUG_MAP[qs["kraj"][0]]
            if "region" in qs and qs["region"][0] in REGION_SLUG_MAP:
                region_key = REGION_SLUG_MAP[qs["region"][0]]

            if not dest_key:
                dest_key = "turkey"  # Default fallback if unspecified

            # 2. Airports
            airports: List[str] = []
            if "samolotem" in qs:
                raw_ap = qs["samolotem"][0].upper()
                airports = [a.strip() for a in re.split(r"[,;|+]", raw_ap) if a.strip()]

            # 3. Dates
            date_from: Optional[str] = qs.get("od", [None])[0]
            date_to: Optional[str] = qs.get("do", [None])[0]

            # 4. Passengers
            adults = 2
            children = 0
            child_ages: List[int] = []

            if "dorosli" in qs:
                try:
                    adults = max(1, int(qs["dorosli"][0]))
                except (ValueError, TypeError):
                    adults = 2

            if "dzieci" in qs:
                try:
                    children = max(0, int(qs["dzieci"][0]))
                except (ValueError, TypeError):
                    children = 0

            if "wiek" in qs:
                raw_ages = qs["wiek"][0]
                for a_str in re.split(r"[,;|+]", raw_ages):
                    try:
                        child_ages.append(int(a_str.strip()))
                    except (ValueError, TypeError):
                        pass

            # 5. Duration
            dur_min = 7
            dur_max = 10
            if "dlugosc" in qs:
                dur_str = qs["dlugosc"][0]
                if "-" in dur_str:
                    parts = dur_str.split("-")
                    try:
                        dur_min = int(parts[0])
                        dur_max = int(parts[1])
                    except (ValueError, TypeError):
                        pass
                else:
                    try:
                        val = int(dur_str)
                        dur_min = val
                        dur_max = val
                    except (ValueError, TypeError):
                        pass

            # 6. Stars
            stars: Optional[int] = None
            if "gwiazdki" in qs:
                st_str = qs["gwiazdki"][0]
                nums = re.findall(r"\d+", st_str)
                if nums:
                    stars = min([int(n) for n in nums])

            # 7. Catering from query
            if "wyzywienie" in qs:
                c_val = qs["wyzywienie"][0].lower()
                if c_val in CATERING_MAP:
                    catering = CATERING_MAP[c_val]

            # Build human-friendly title
            dest_name = dest_key.capitalize()
            if dest_key == "turkey":
                dest_name = "Турция"
            elif dest_key == "egypt":
                dest_name = "Египет"
            elif dest_key == "greece":
                dest_name = "Греция"
            elif dest_key == "spain":
                dest_name = "Испания"
            elif dest_key == "cyprus":
                dest_name = "Кипр"
            elif dest_key == "bulgaria":
                dest_name = "Болгария"
            elif dest_key == "tunisia":
                dest_name = "Тунис"
            elif dest_key == "uae":
                dest_name = "ОАЭ"
            elif dest_key == "italy":
                dest_name = "Италия"

            ap_str = f" из {', '.join(airports)}" if airports else ""
            pax_str = f" ({adults} взр" + (f" + {children} реб" if children > 0 else "") + ")"
            title = f"{dest_name}{ap_str} • {dur_min}-{dur_max} ночей{pax_str}"

            # Structured SearchRequest dictionary
            structured_req = {
                "destination": region_key or dest_key,
                "country": dest_key,
                "departure_airports": airports,
                "date_from": date_from,
                "date_to": date_to,
                "duration_min": dur_min,
                "duration_max": dur_max,
                "adults": adults,
                "children": children,
                "child_ages": child_ages,
                "catering": catering or "all-inclusive",
                "stars": stars or 4,
            }

            return FlyUrlParseResponse(
                is_valid=True,
                parsed_title=title,
                destination=dest_key,
                region=region_key,
                departure_airports=airports,
                date_from=date_from,
                date_to=date_to,
                duration_min=dur_min,
                duration_max=dur_max,
                adults=adults,
                children=children,
                catering=catering or "all-inclusive",
                stars=stars or 4,
                structured_search_request=structured_req,
            )

        except Exception as e:
            return FlyUrlParseResponse(
                is_valid=False,
                parsed_title="Ошибка разбора ссылки",
                error_message=f"Не удалось распознать параметры ссылки Fly.pl: {str(e)}",
            )

