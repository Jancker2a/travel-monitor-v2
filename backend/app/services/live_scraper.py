import re
import html as ihtml
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.models.hotel import Hotel
from app.models.cohort import OfferCohort, compute_cohort_hash
from app.models.price_snapshot import PriceSnapshot
from app.schemas.search import (
    SearchRequest,
    SearchHotelItem,
    OfferSummary,
    HotelIntelligence,
)
from app.services.query_builder import UniversalQueryBuilder

from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("travel_monitor_2.scraper")


def slugify(text: str) -> str:
    text = str(text or "").lower().strip()
    text = re.sub(r"[^\w\d]+", "-", text)
    return text.strip("-") or "hotel"


def parse_departure_date(date_str: str) -> Tuple[Optional[date], Optional[date]]:
    """Extracts (checkin_date, checkout_date) from date string."""
    if not date_str:
        return None, None
    matches = re.findall(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", date_str)
    res_dates: List[date] = []
    for p1, p2, y in matches:
        v1, v2, year = int(p1), int(p2), int(y)
        try:
            if v2 > 12 and v1 <= 12:
                res_dates.append(date(year, v1, v2))
            else:
                res_dates.append(date(year, v2, v1))
        except ValueError:
            pass

    if not res_dates:
        m_iso = re.findall(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
        for y, m_val, d_val in m_iso:
            try:
                res_dates.append(date(int(y), int(m_val), int(d_val)))
            except ValueError:
                pass

    if len(res_dates) >= 2:
        return res_dates[0], res_dates[1]
    elif len(res_dates) == 1:
        return res_dates[0], None
    return None, None


def parse_duration_nights(duration_str: str) -> int:
    """Parses '8 dni' or '7 nocy' into integer nights."""
    if not duration_str:
        return 7
    m = re.search(r"(\d+)", str(duration_str))
    if m:
        val = int(m.group(1))
        return max(1, val - 1) if "dni" in str(duration_str).lower() else val
    return 7


class LiveScraperService:
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    }
    DEFAULT_COOKIES = {
        "_crflytest": "newfly2:new",
        "newpath": "1",
    }

    @classmethod
    async def fetch_offers_via_api(cls, url: str, max_offers: int = 50) -> List[Dict[str, Any]]:
        """Parses Fly.pl search URL and directly queries Fly.pl JSON search API."""
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)

            def to_iso(d_str: str) -> str:
                parts = d_str.split("-")
                return f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else d_str

            api_params: Dict[str, Any] = {
                "pager[page]": 1,
                "pager[size]": min(50, max_offers),
                "priceType": "total",
                "totalPrice": 1,
                "pager[orderBy][0][field]": "price",
                "pager[orderBy][0][direction]": "asc",
            }

            if "adults" in qs:
                api_params["adults"] = int(qs["adults"][0])
            if "durationFrom" in qs:
                api_params["durationFrom"] = int(qs["durationFrom"][0])
            if "durationTo" in qs:
                api_params["durationTo"] = int(qs["durationTo"][0])
            if "categoryRating" in qs:
                cat_val = float(qs["categoryRating"][0])
                api_params["categoryRating"] = cat_val / 10.0 if cat_val >= 10 else cat_val
            if "priceFrom" in qs:
                api_params["price[min]"] = float(qs["priceFrom"][0])
            if "priceTo" in qs:
                api_params["price[max]"] = float(qs["priceTo"][0])
            if "startDateMin" in qs:
                api_params["startDate[min]"] = to_iso(qs["startDateMin"][0])
            if "startDateMax" in qs:
                api_params["startDate[max]"] = to_iso(qs["startDateMax"][0])
            if "children" in qs:
                for i, ch in enumerate(qs["children"][0].split(",")):
                    api_params[f"children[{i}]"] = to_iso(ch.strip())
            if "destinationLocation" in qs:
                dest_val = qs["destinationLocation"][0].rstrip(":")
                api_params["destinationLocation[0]"] = dest_val
            if "departureLocation" in qs:
                deps = qs["departureLocation"][0].split(",")
                dep_idx = 0
                for dep in deps:
                    dep_clean = dep.replace("+-+", " ").replace("+", " ").strip()
                    if "radom" in dep_clean.lower():
                        dep_clean = "Radom"
                    elif "modlin" in dep_clean.lower():
                        dep_clean = "Modlin"
                    elif "warszawa" in dep_clean.lower():
                        dep_clean = "Warszawa"
                    if dep_clean:
                        api_params[f"departureLocation[{dep_idx}]"] = dep_clean
                        dep_idx += 1

            headers = {
                "User-Agent": cls.DEFAULT_HEADERS["User-Agent"],
                "Accept": "application/json, text/plain, */*",
                "Referer": url,
            }

            async with httpx.AsyncClient(headers=headers, timeout=15.0) as client:
                resp = await client.get("https://fly.pl/api/fqs/v1/offers/search", params=api_params)
                if resp.status_code == 200:
                    payload = resp.json().get("data", {})
                    raw_list = payload.get("offers", []) if isinstance(payload, dict) else []
                    results = []
                    for o in raw_list[:max_offers]:
                        hotel_name = o.get("name") or o.get("unifiedName") or ""
                        if not hotel_name:
                            continue
                        price_num = float(o.get("total") or o.get("price") or 0.0)
                        if price_num <= 0:
                            continue
                        dep_date = (o.get("departureDate") or "")[:10]
                        ret_date = (o.get("returnDate") or "")[:10]
                        dates_str = f"{dep_date} - {ret_date}" if dep_date else ""
                        checkin_d, checkout_d = parse_departure_date(dates_str)
                        nights = int(o.get("nights") or o.get("duration") or 7)
                        stars_val = int(o.get("categoryRating", 40)) // 10 if o.get("categoryRating") else 4
                        thumb = o.get("thumbnailUrl") or (o.get("imagesUrl")[0] if o.get("imagesUrl") else "")
                        pub_url = f"https://fly.pl{o.get('publicUrl')}" if o.get("publicUrl") else ""
                        ta_r = float(o["rating"]) if o.get("rating") else None
                        board = o.get("serviceDesc") or "All Inclusive"
                        results.append({
                            "hotel_name": hotel_name,
                            "price": price_num,
                            "dates": dates_str,
                            "checkin_date": checkin_d or date.today(),
                            "checkout_date": checkout_d,
                            "duration": f"{nights} nocy",
                            "duration_nights": nights,
                            "departure_airport": o.get("departureLocation") or o.get("departureCode") or "WAW",
                            "board_basis": board,
                            "stars": stars_val,
                            "main_image_url": thumb,
                            "image_url": thumb,
                            "offer_url": pub_url,
                            "ta_rating": ta_r,
                            "operator": o.get("operatorName") or o.get("operator") or "",
                        })
                    return results
        except Exception as e:
            logger.warning(f"Direct Fly.pl JSON API search failed for {url}: {e}")
        return []

    @classmethod
    async def fetch_page_html(cls, url: str, timeout_seconds: float = 12.0) -> Optional[str]:
        """Performs async HTTP GET request to Fly.pl with retry and browser simulation."""
        async with httpx.AsyncClient(
            headers=cls.DEFAULT_HEADERS,
            cookies=cls.DEFAULT_COOKIES,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
        ) as client:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.text
                logger.warning(f"Fly.pl responded with HTTP {resp.status_code} for URL: {url}")
            except Exception as e:
                logger.error(f"HTTP request failed for {url}: {e}")
        return None

    @classmethod
    def parse_offers_html(cls, page_html: str, max_offers: int = 50) -> List[Dict[str, Any]]:
        """Parses Fly.pl server-rendered cards from raw HTML."""
        if not page_html or "brak ofert" in page_html.lower():
            return []

        offers: List[Dict[str, Any]] = []
        cards = re.split(r'<div class="card-offer-search', page_html)[1:]

        for card in cards[:max_offers]:
            def find(pattern: str, flags: int = 0) -> str:
                m = re.search(pattern, card, flags)
                return ihtml.unescape(m.group(1)).strip() if m else ""

            # Hotel Name
            name = ""
            mh = re.search(r'<h2[^>]*property="schema:name"[^>]*>(.*?)</h2>', card, re.S)
            if mh:
                name = ihtml.unescape(re.sub(r"<[^>]+>", "", mh.group(1))).strip()
            if not name:
                name = find(r'property="schema:name"[^>]*content="([^"]+)"')
            if not name:
                continue

            # Price
            total_raw = find(r'data-priceperall="([^"]+)"')
            price_val = 0.0
            if total_raw:
                try:
                    price_val = float(re.sub(r"[^\d.]", "", total_raw.replace(",", ".").replace(" ", "")))
                except ValueError:
                    price_val = 0.0
            if not price_val:
                pp = find(r'property="schema:price"[^>]*content="([^"]+)"')
                if pp:
                    try:
                        price_val = float(re.sub(r"[^\d.]", "", pp.replace(",", ".").replace(" ", "")))
                    except ValueError:
                        price_val = 0.0

            if price_val <= 0:
                continue

            # URL & Image
            offer_url = find(r'property="schema:url"[^>]*content="([^"]+)"') or find(r'data-phref="([^"]+)"')
            if offer_url and not offer_url.startswith("http"):
                offer_url = f"https://fly.pl{offer_url}"

            img_url = find(r'rel="schema:image"[^>]*resource="([^"]+)"')
            if img_url and not img_url.startswith("http"):
                img_url = f"https://fly.pl{img_url}"

            # Dates & Duration
            md = re.search(
                r'(\d{1,2}\.\d{1,2}(?:\.\d{4})?\s*-\s*\d{1,2}\.\d{1,2}(?:\.\d{4})?)\s*(?:\(([^)]*?dni[^)]*)\))?',
                card,
            )
            raw_dates = md.group(1).strip() if md else ""
            raw_duration = md.group(2).strip() if (md and md.group(2)) else ""
            if not raw_duration:
                m_dur = re.search(r'(\d+)\s*(?:dni|days|day|d|nocleg\w*|nights?|nocy)', card, re.I)
                raw_duration = m_dur.group(0) if m_dur else "7 nocy"

            checkin_d, checkout_d = parse_departure_date(raw_dates)
            nights = parse_duration_nights(raw_duration)

            # Airport
            airport = "WAW"
            m_air = re.search(r'class="[^"]*airport[^"]*"[^>]*>([^<]+)', card, re.I)
            if m_air:
                airport = m_air.group(1).strip()
            else:
                m_flight = re.search(r'(?:Warszawa|Katowice|Kraków|Gdańsk|Wrocław|Poznań)', card, re.I)
                if m_flight:
                    airport = m_flight.group(0)

            # Stars
            stars = 4
            m_stars = re.search(r'stars-(\d)', card) or re.search(r'data-stars="(\d)"', card)
            if m_stars:
                try:
                    stars = int(m_stars.group(1))
                except ValueError:
                    pass

            # TripAdvisor rating
            ta_rating = None
            img_m = re.search(r'tripadvisor\.com/[^"\']*/([0-9.]+)-[0-9]+-\d+\.svg', card, re.I)
            if img_m:
                try:
                    ta_rating = float(img_m.group(1))
                except ValueError:
                    pass
            if ta_rating is None:
                bubble_m = re.search(r'bubble_(\d{2})\b', card, re.I)
                if bubble_m:
                    try:
                        ta_rating = float(bubble_m.group(1)) / 10.0
                    except ValueError:
                        pass

            # Operator & Board
            m_op = re.search(r'data-operator="([^"]+)"', card, re.I) or re.search(r'operator=([^&"\'\s]+)', card)
            operator = m_op.group(1).strip() if m_op else "Touroperator"

            board = "All Inclusive"
            if re.search(r'All\s*Inclusive', card, re.I):
                board = "All Inclusive"
            elif re.search(r'HB|dwa\s*posiłki|śniadania\s*i\s*obiadokolacje', card, re.I):
                board = "HB (Half Board)"
            elif re.search(r'BB|śniadania', card, re.I):
                board = "BB (Bed & Breakfast)"

            offers.append({
                "hotel_name": name,
                "price": price_val,
                "dates_str": raw_dates,
                "checkin_date": checkin_d or date.today(),
                "checkout_date": checkout_d,
                "duration_nights": nights,
                "departure_airport": airport,
                "stars": stars,
                "ta_rating": ta_rating,
                "main_image_url": img_url,
                "offer_url": offer_url,
                "operator": operator,
                "board_basis": board,
            })

        return offers

    @classmethod
    async def process_and_persist_offers(
        cls,
        db: AsyncSession,
        req: SearchRequest,
        raw_offers: List[Dict[str, Any]],
    ) -> List[SearchHotelItem]:
        """Computes intelligence against historical data, persists new records, and constructs response models."""
        items: List[SearchHotelItem] = []
        destination_country = req.destination.capitalize()

        for off in raw_offers:
            hotel_id = slugify(off["hotel_name"])
            
            # 1. Upsert / fetch Hotel
            h_stmt = select(Hotel).where(Hotel.hotel_id == hotel_id)
            h_res = await db.execute(h_stmt)
            hotel_entity = h_res.scalar_one_or_none()

            if not hotel_entity:
                hotel_entity = Hotel(
                    hotel_id=hotel_id,
                    display_name=off["hotel_name"],
                    country=destination_country,
                    region="",
                    stars=off["stars"],
                    ta_rating=off["ta_rating"],
                    main_image_url=off["main_image_url"],
                )
                db.add(hotel_entity)
            else:
                # Update image or TA rating if newly discovered
                if off["main_image_url"] and not hotel_entity.main_image_url:
                    hotel_entity.main_image_url = off["main_image_url"]
                if off["ta_rating"] and not hotel_entity.ta_rating:
                    hotel_entity.ta_rating = off["ta_rating"]

            # 2. Compute Cohort Signature
            cohort_hash = compute_cohort_hash(
                hotel_id=hotel_id,
                checkin_date=off["checkin_date"],
                duration_nights=off["duration_nights"],
                airport_code=off["departure_airport"],
                adults=req.travelers.adults,
                board_basis=off["board_basis"],
            )

            # Upsert Cohort
            c_stmt = select(OfferCohort).where(OfferCohort.cohort_hash == cohort_hash)
            c_res = await db.execute(c_stmt)
            cohort_entity = c_res.scalar_one_or_none()

            now_dt = datetime.utcnow()
            if not cohort_entity:
                cohort_entity = OfferCohort(
                    cohort_hash=cohort_hash,
                    hotel_id=hotel_id,
                    destination_code=req.destination,
                    checkin_date=off["checkin_date"],
                    checkout_date=off["checkout_date"],
                    duration_nights=off["duration_nights"],
                    airport_code=off["departure_airport"],
                    board_basis=off["board_basis"],
                    adults=req.travelers.adults,
                    children=req.travelers.children,
                    operator=off["operator"],
                    offer_url=off["offer_url"],
                    first_seen_at=now_dt,
                    last_seen_at=now_dt,
                )
                db.add(cohort_entity)
            else:
                cohort_entity.last_seen_at = now_dt
                if off["offer_url"]:
                    cohort_entity.offer_url = off["offer_url"]

            # 3. Insert Price Snapshot
            pax_count = max(1, req.travelers.adults + req.travelers.children)
            price_pax_night = off["price"] / (max(1, off["duration_nights"]) * pax_count)

            snapshot = PriceSnapshot(
                cohort_hash=cohort_hash,
                recorded_at=now_dt,
                total_price_pln=off["price"],
                price_per_night_per_pax=round(price_pax_night, 2),
                currency="PLN",
                source="fly_pl",
            )
            db.add(snapshot)

            # 4. Compute Intelligence & Sparkline from Historical Snapshots
            snap_stmt = (
                select(PriceSnapshot.total_price_pln)
                .where(PriceSnapshot.cohort_hash == cohort_hash)
                .order_by(PriceSnapshot.recorded_at.desc())
                .limit(20)
            )
            snap_res = await db.execute(snap_stmt)
            recent_prices = [row[0] for row in snap_res.fetchall()]
            if not recent_prices:
                recent_prices = [off["price"]]

            sparkline = list(reversed(recent_prices))
            hist_min = min(recent_prices)
            hist_median = sorted(recent_prices)[len(recent_prices) // 2]
            curr_price = off["price"]

            # Deal Score & Badge calculation
            if hist_median > 0:
                price_diff_ratio = (curr_price - hist_median) / hist_median
            else:
                price_diff_ratio = 0.0

            if curr_price <= hist_min and len(recent_prices) >= 3:
                deal_score = 95
                deal_badge = "SUPER_DEAL"
                verdict = "BUY NOW"
                recom = f"Абсолютный исторический минимум! Скидка от медианы: {abs(price_diff_ratio) * 100:.1f}%"
            elif price_diff_ratio <= -0.08:
                deal_score = 82
                deal_badge = "GOOD_DEAL"
                verdict = "BUY NOW"
                recom = f"Отличная цена, ниже типичного уровня на {abs(price_diff_ratio) * 100:.0f}%."
            elif price_diff_ratio <= 0.05:
                deal_score = 65
                deal_badge = "FAIR_PRICE"
                verdict = "WAIT"
                recom = "Стандартная рыночная цена. Возможны колебания."
            else:
                deal_score = 40
                deal_badge = "OVERPRICED"
                verdict = "OVERPRICED"
                recom = f"Цена завышена на {price_diff_ratio * 100:.0f}% относительно обычного тарифа."

            intelligence = HotelIntelligence(
                deal_score=deal_score,
                deal_badge=deal_badge,
                hopper_verdict=verdict,
                hopper_confidence=0.88 if len(recent_prices) >= 5 else 0.65,
                recommendation=recom,
                drop_48h_pct=round(-price_diff_ratio * 100, 1) if price_diff_ratio < 0 else 0.0,
                historic_min_pln=hist_min,
                typical_median_pln=hist_median,
                german_arbitrage_diff_pln=None,
            )

            current_offer = OfferSummary(
                cohort_hash=cohort_hash,
                total_price_pln=curr_price,
                price_per_night_pax=round(price_pax_night, 2),
                departure_date=off["checkin_date"],
                duration_nights=off["duration_nights"],
                airport=off["departure_airport"],
                operator=off["operator"],
                booking_url=off["offer_url"],
            )

            item = SearchHotelItem(
                hotel_id=hotel_id,
                hotel_name=off["hotel_name"],
                stars=off["stars"],
                region=hotel_entity.region,
                country=hotel_entity.country,
                main_image_url=off["main_image_url"],
                current_offer=current_offer,
                intelligence=intelligence,
                history_sparkline=sparkline,
            )
            items.append(item)

        await db.commit()
        return items

