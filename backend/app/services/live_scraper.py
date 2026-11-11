import asyncio
import re
import html as ihtml
import logging
from datetime import datetime, date, timedelta, timezone
from collections import defaultdict
from typing import Dict, Any, List, Optional, Tuple
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, text

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
from app.services.cost_decomposer import CostDecomposer

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
    async def fetch_offers_via_api(
        cls, url: str, max_offers: int = 200, return_meta: bool = False
    ) -> Any:
        """Parses Fly.pl search URL and directly queries Fly.pl JSON search API with multi-page support."""
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)

            def to_iso(d_str: str) -> str:
                parts = d_str.split("-")
                return f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else d_str

            order_val = qs.get("order", ["price"])[0].lower()
            order_dir = "desc" if "desc" in order_val else "asc"

            api_params: Dict[str, Any] = {
                "pager[page]": 1,
                "pager[size]": 100,
                "priceType": "total",
                "totalPrice": 1,
                "pager[orderBy][0][field]": "price",
                "pager[orderBy][0][direction]": order_dir,
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
                try:
                    api_params["priceFrom"] = int(float(qs["priceFrom"][0]))
                except Exception:
                    pass
            if "priceTo" in qs:
                try:
                    api_params["priceTo"] = int(float(qs["priceTo"][0]))
                except Exception:
                    pass

            def parse_date(d_str: str) -> Optional[date]:
                parts = d_str.split("-")
                if len(parts) == 3:
                    try:
                        return date(int(parts[2]), int(parts[1]), int(parts[0]))
                    except Exception:
                        pass
                try:
                    return date.fromisoformat(d_str)
                except Exception:
                    return None

            today = date.today()
            start_min_d = parse_date(qs["startDateMin"][0]) if "startDateMin" in qs else None
            start_max_d = parse_date(qs["startDateMax"][0]) if "startDateMax" in qs else None

            if start_max_d and start_max_d <= today:
                # The search window was in the past (rolling filter).
                # Auto-roll window forward from today keeping equivalent span (default 23 days).
                window_span = max(7, (start_max_d - start_min_d).days) if (start_min_d and start_max_d) else 23
                new_min = today
                new_max = today + timedelta(days=window_span)
                api_params["startDate[min]"] = new_min.isoformat()
                api_params["startDate[max]"] = new_max.isoformat()
            elif start_min_d and start_min_d < today:
                # Start date passed, slide min to today
                api_params["startDate[min]"] = today.isoformat()
                if start_max_d:
                    api_params["startDate[max]"] = start_max_d.isoformat()
            else:
                if start_min_d:
                    api_params["startDate[min]"] = start_min_d.isoformat()
                elif "startDateMin" in qs:
                    api_params["startDate[min]"] = to_iso(qs["startDateMin"][0])
                if start_max_d:
                    api_params["startDate[max]"] = start_max_d.isoformat()
                elif "startDateMax" in qs:
                    api_params["startDate[max]"] = to_iso(qs["startDateMax"][0])

            # Handle children and child birthdates (Fly.pl JSON API expects children[i] = YYYY-MM-DD birthdate)
            ref_date = start_min_d or today
            child_birthdates = []
            if "childrenAges" in qs:
                for a in qs["childrenAges"][0].split(","):
                    try:
                        age = int(a.strip())
                        b_date = ref_date - timedelta(days=int(age * 365.25 + 180))
                        child_birthdates.append(b_date.isoformat())
                    except Exception:
                        pass
            elif "children" in qs:
                for ch in qs["children"][0].split(","):
                    ch_clean = ch.strip()
                    if "-" in ch_clean:
                        child_birthdates.append(to_iso(ch_clean))
                    else:
                        try:
                            cnt = int(ch_clean)
                            for _ in range(cnt):
                                b_date = ref_date - timedelta(days=int(6 * 365.25 + 180))
                                child_birthdates.append(b_date.isoformat())
                        except Exception:
                            pass

            for i, b_date_str in enumerate(child_birthdates):
                api_params[f"children[{i}]"] = b_date_str

            # Handle catering (Fly.pl JSON API expects array format: catering[0] = "all_inclusive")
            if "catering" in qs:
                cats = qs["catering"][0].split(",")
                for i, cat in enumerate(cats):
                    cat_val = cat.strip()
                    if cat_val and cat_val != "all":
                        api_params[f"catering[{i}]"] = cat_val

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
                "Referer": "https://fly.pl/szukaj-wycieczek/",
            }

            results = []
            seen_offers = set()
            start_page = 1
            if "p" in qs:
                try:
                    start_page = max(1, int(qs["p"][0]))
                except Exception:
                    pass
            elif "page" in qs:
                try:
                    start_page = max(1, int(qs["page"][0]))
                except Exception:
                    pass

            page = start_page
            max_pages = start_page + min(3, max(1, (max_offers + 99) // 100)) - 1
            total_count_from_api = None

            async with httpx.AsyncClient(headers=headers, timeout=25.0) as client:
                while page <= max_pages and len(results) < max_offers:
                    api_params["pager[page]"] = page
                    try:
                        resp = await client.get("https://fly.pl/api/fqs/v1/offers/search", params=api_params)
                        if resp.status_code != 200:
                            logger.warning(
                                f"Fly.pl search API returned status {resp.status_code} for {url}: {resp.text[:300]}"
                            )
                            break
                        payload = resp.json().get("data", {})
                        if total_count_from_api is None and isinstance(payload, dict):
                            total_count_from_api = payload.get("count")
                        raw_list = payload.get("offers", []) if isinstance(payload, dict) else []
                        if not raw_list:
                            break

                        for o in raw_list:
                            hotel_name = o.get("name") or o.get("unifiedName") or ""
                            if not hotel_name:
                                continue
                            price_num = float(o.get("total") or o.get("price") or 0.0)
                            if price_num <= 0:
                                continue
                            dep_date = (o.get("departureDate") or "")[:10]
                            ret_date = (o.get("returnDate") or "")[:10]
                            dates_str = f"{dep_date} - {ret_date}" if dep_date else ""

                            # Deduplication key across pages
                            dedup_key = (hotel_name.lower().strip(), dep_date, price_num)
                            if dedup_key in seen_offers:
                                continue
                            seen_offers.add(dedup_key)

                            checkin_d, checkout_d = parse_departure_date(dates_str)
                            nights = int(o.get("nights") or o.get("duration") or 7)
                            stars_val = int(o.get("categoryRating", 40)) // 10 if o.get("categoryRating") else 4
                            thumb = o.get("thumbnailUrl") or (o.get("imagesUrl")[0] if o.get("imagesUrl") else "")
                            pub_url = f"https://fly.pl{o.get('publicUrl')}" if o.get("publicUrl") else ""
                            cms_data = o.get("cmsData") or {}
                            ta_val = cms_data.get("tripadvisorRating") or o.get("rating")
                            try:
                                ta_r = float(ta_val) if ta_val and float(ta_val) > 0 else None
                            except (ValueError, TypeError):
                                ta_r = None
                            try:
                                ta_revs_val = cms_data.get("tripadvisorNumReviews")
                                ta_revs = int(ta_revs_val) if ta_revs_val and int(ta_revs_val) > 0 else None
                            except (ValueError, TypeError):
                                ta_revs = None
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
                                "ta_reviews": ta_revs,
                                "operator": o.get("operatorName") or o.get("operator") or "",
                            })
                            if len(results) >= max_offers:
                                break

                        page += 1
                        await asyncio.sleep(0.2)
                    except Exception as page_err:
                        logger.warning(f"Error fetching page {page} for {url}: {page_err}")
                        break

            if return_meta:
                return results, (total_count_from_api or len(results))
            return results
        except Exception as e:
            logger.warning(f"Direct Fly.pl JSON API search failed for {url}: {e}")
        if return_meta:
            return [], 0
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
        dest_keyword = (req.destination or "turkey").lower()
        destination_country = (
            "Египет" if "egypt" in dest_keyword
            else "Турция" if "turkey" in dest_keyword
            else "Греция" if "greece" in dest_keyword
            else "Кипр" if "cyprus" in dest_keyword
            else "Испания" if "spain" in dest_keyword
            else req.destination.capitalize() if req.destination else "Турция"
        )
        batch_recorded_at = datetime.now(timezone.utc)

        all_hids = list(set(slugify(off["hotel_name"]) for off in raw_offers if off.get("hotel_name")))

        # 1. Bulk pre-fetch all known hotels in 1 query
        seen_hotels: Dict[str, Hotel] = {}
        if all_hids:
            try:
                h_stmt = select(Hotel).where(Hotel.hotel_id.in_(all_hids))
                h_res = await db.execute(h_stmt)
                for h in h_res.scalars().all():
                    seen_hotels[h.hotel_id] = h
            except Exception as e:
                logger.warning(f"Bulk hotel fetch error: {e}")

        # 2. Bulk pre-fetch historical price points for all candidate hotels in 1 query
        join_col = "cohort_id"
        try:
            if db.bind and db.bind.dialect.name == "sqlite":
                pragma_res = await db.execute(text("PRAGMA table_info(price_snapshots)"))
                pragma_cols = {r[1] for r in pragma_res.fetchall()}
                if "cohort_hash" in pragma_cols:
                    join_col = "cohort_hash"
                elif "cohort_id" in pragma_cols:
                    join_col = "cohort_id"
        except Exception:
            pass

        hist_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        if all_hids:
            try:
                placeholders = ",".join(f":h{i}" for i in range(len(all_hids)))
                h_params = {f"h{i}": hid for i, hid in enumerate(all_hids)}
                h_sql = f"""
                    SELECT oc.hotel_id, ps.total_price_pln, oc.adults, oc.children, oc.duration_nights, ps.recorded_at, oc.checkin_date
                    FROM price_snapshots ps
                    JOIN offer_cohorts oc ON ps.{join_col} = oc.{join_col}
                    WHERE oc.hotel_id IN ({placeholders})
                    ORDER BY ps.recorded_at DESC
                    LIMIT 1000
                """
                h_res = await db.execute(text(h_sql), h_params)
                for hid, p_val, s_adults, s_children, s_nights, s_time, s_checkin in h_res.fetchall():
                    if len(hist_map[hid]) < 25:
                        hist_map[hid].append({
                            "price": float(p_val),
                            "adults": int(s_adults or 2),
                            "children": int(s_children or 0),
                            "duration_nights": int(s_nights or 8),
                            "recorded_at": s_time,
                            "departure_date": s_checkin,
                        })
            except Exception as e:
                logger.warning(f"Bulk hist lookup error: {e}")

        req_adults = req.travelers.adults if req.travelers else 2
        req_children = req.travelers.children if req.travelers else 0
        pax_count = max(1, req_adults + req_children)

        # Pre-compute peer star pure rates within this search batch for fair baseline comparison
        peer_star_pure_rates: Dict[int, List[float]] = defaultdict(list)
        for off in raw_offers:
            off_p = float(off.get("price") or 0)
            off_n = max(1, off.get("duration_nights") or 8)
            off_stars = int(off.get("stars") or 4)
            if off_p > 0:
                off_decomp = CostDecomposer.decompose(
                    total_price_pln=off_p,
                    duration_nights=off_n,
                    adults=req_adults,
                    children=req_children,
                    destination=destination_country,
                )
                peer_star_pure_rates[off_stars].append(off_decomp.get("pure_hotel_night_per_adult", 150.0))

        from app.services.search_intelligence import evaluate_search_intelligence

        for off in raw_offers:
            hotel_id = slugify(off["hotel_name"])
            hotel_entity = seen_hotels.get(hotel_id)

            off_ta = off.get("ta_rating")
            off_reviews = off.get("ta_reviews")

            if not hotel_entity:
                hotel_entity = Hotel(
                    hotel_id=hotel_id,
                    display_name=off["hotel_name"],
                    country=destination_country,
                    region="",
                    stars=off["stars"],
                    ta_rating=off_ta,
                    ta_reviews=off_reviews,
                    main_image_url=off["main_image_url"],
                )
                db.add(hotel_entity)
                seen_hotels[hotel_id] = hotel_entity
            else:
                if off["main_image_url"] and not hotel_entity.main_image_url:
                    hotel_entity.main_image_url = off["main_image_url"]
                if off_ta and (not hotel_entity.ta_rating or hotel_entity.ta_rating != off_ta):
                    hotel_entity.ta_rating = off_ta
                if off_reviews and not hotel_entity.ta_reviews:
                    hotel_entity.ta_reviews = off_reviews

            cohort_hash = compute_cohort_hash(
                hotel_id=hotel_id,
                checkin_date=off["checkin_date"],
                duration_nights=off["duration_nights"],
                airport_code=off["departure_airport"],
                adults=req_adults,
                board_basis=off["board_basis"],
                filter_id=req.filter_id,
            )

            curr_price = float(off["price"])
            hotel_snaps = hist_map.get(hotel_id, [])
            spark_pts = []
            if hotel_snaps:
                for s in hotel_snaps[:12]:
                    s_price = s["price"]
                    if s["adults"] == req_adults and s["children"] == req_children:
                        spark_pts.append(round(s_price, 0))
                    else:
                        d = CostDecomposer.decompose(
                            total_price_pln=s_price,
                            duration_nights=s.get("duration_nights", 8),
                            adults=s["adults"],
                            children=s["children"],
                            destination=destination_country,
                        )
                        flight_bench = CostDecomposer.get_flight_benchmark(destination_country)
                        recon_price = (
                            (req_adults + req_children) * flight_bench
                            + max(1, off["duration_nights"])
                            * d["pure_hotel_night_per_adult"]
                            * (req_adults + req_children * 0.2)
                        )
                        spark_pts.append(round(recon_price, 0))
            if not spark_pts:
                spark_pts = [curr_price]
            sparkline = list(reversed(spark_pts))

            effective_ta = off_ta or (hotel_entity.ta_rating if hotel_entity else None)
            effective_reviews = off_reviews or (hotel_entity.ta_reviews if hotel_entity else None)

            # Compute authentic Deal Score & Hopper Forecast using price, normalized history, seasonality, and drop risk
            intelligence = evaluate_search_intelligence(
                destination=destination_country,
                departure_date=off["checkin_date"],
                duration_nights=off["duration_nights"],
                adults=req_adults,
                children=req_children,
                total_price_pln=curr_price,
                stars=off["stars"],
                ta_rating=effective_ta,
                hist_snapshots=hotel_snaps,
                peer_star_pure_rates=peer_star_pure_rates.get(off["stars"]),
            )

            current_offer = OfferSummary(
                cohort_hash=cohort_hash,
                total_price_pln=curr_price,
                price_per_night_pax=round(curr_price / (max(1, off["duration_nights"]) * pax_count), 2),
                departure_date=off["checkin_date"],
                duration_nights=off["duration_nights"],
                airport=off["departure_airport"],
                operator=off["operator"],
                booking_url=off["offer_url"],
                adults=req_adults,
                children=req_children,
            )

            item = SearchHotelItem(
                hotel_id=hotel_id,
                hotel_name=off["hotel_name"],
                stars=off["stars"],
                region=hotel_entity.region or destination_country,
                country=hotel_entity.country or destination_country,
                main_image_url=off["main_image_url"],
                ta_rating=effective_ta,
                ta_reviews=effective_reviews,
                specs=hotel_entity.specs if hotel_entity else None,
                current_offer=current_offer,
                intelligence=intelligence,
                history_sparkline=sparkline,
            )
            items.append(item)

        # Commit newly discovered hotels if any
        try:
            await db.commit()
        except Exception:
            pass

        return items

