import os
import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.filter_monitor import FilterMonitor
from app.models.price_snapshot import PriceSnapshot
from app.models.cohort import OfferCohort
from app.models.hotel import Hotel

logger = logging.getLogger("travel_monitor_2.rebuilder")


def slugify(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "hotel"


class SiteRebuilderService:
    SITE_DIR = Path(__file__).resolve().parents[3] / "site"

    @classmethod
    async def rebuild_all(cls, db: AsyncSession) -> Dict[str, Any]:
        """Updates HTML dashboards, hotel_series JSONs, and catalog data from DB snapshots and saved runs."""
        logger.info(f"🔄 Starting site rebuild in {cls.SITE_DIR}...")
        if not cls.SITE_DIR.is_dir():
            logger.warning(f"Site directory {cls.SITE_DIR} does not exist. Skipping rebuild.")
            return {"status": "skipped", "reason": "site_dir_not_found"}

        stmt = select(FilterMonitor)
        res = await db.execute(stmt)
        monitors = res.scalars().all()

        now_utc = datetime.now(timezone.utc)
        now_str = now_utc.strftime("%d.%m.%Y %H:%M")

        updated_dashboards = []

        for m in monitors:
            dashboard_file = cls._find_dashboard_file(m.id)
            if not dashboard_file or not dashboard_file.is_file():
                continue

            try:
                # Check if we have saved last_run_offers.json
                filter_dir = cls._find_filter_data_dir(m.id)
                last_run_file = filter_dir / "last_run_offers.json" if filter_dir else None
                if last_run_file and last_run_file.is_file():
                    try:
                        raw_offers = json.loads(last_run_file.read_text(encoding="utf-8"))
                        if raw_offers and isinstance(raw_offers, list):
                            scraped_dt = m.last_scraped_at or now_utc
                            cls.record_monitor_scrape_run(m.id, raw_offers, scraped_dt)
                            updated_dashboards.append(m.id)
                            continue
                    except Exception as err:
                        logger.warning(f"Could not load last_run_offers for {m.id}: {err}")

                cls._update_dashboard_kpis_only(dashboard_file, m, now_str)
                await cls._update_hotel_series_for_monitor(db, m)
                updated_dashboards.append(m.id)
            except Exception as e:
                logger.error(f"Error updating dashboard for monitor '{m.id}': {e}", exc_info=True)

        cls._update_landing_page(now_str)
        cls._update_hotels_catalog_timestamp(now_utc)

        logger.info(f"✅ Site rebuild completed: {len(updated_dashboards)} dashboards refreshed.")
        return {
            "status": "success",
            "updated_dashboards": updated_dashboards,
            "rebuilt_at": now_utc.isoformat(),
        }

    @classmethod
    def record_monitor_scrape_run(
        cls, monitor_id: str, raw_offers: List[Dict[str, Any]], scraped_at: datetime
    ) -> Dict[str, Any]:
        """
        Processes freshly scraped offers for a monitor:
        1. Computes the TOP-10 cheapest hotels and analytics.
        2. Appends new data point to Plotly chart arrays (const X, Y, minY, maxY, detailedData) in index_filter_*.html.
        3. Updates header KPI badges and relative timestamps.
        4. Appends price points to hotel_series/*.json for individual hotel history drawers.
        5. Persists site/data/filters/<filter_id>/last_run_offers.json.
        """
        if not raw_offers:
            return {"status": "skipped", "reason": "no_offers"}

        dashboard_file = cls._find_dashboard_file(monitor_id)
        filter_dir = cls._find_filter_data_dir(monitor_id)

        # 1. Group offers by hotel and take lowest price per hotel
        hotel_best: Dict[str, float] = {}
        for o in raw_offers:
            h_name = str(o.get("hotel_name") or "").strip()
            price = float(o.get("price") or 0.0)
            if not h_name or price <= 0:
                continue
            if h_name not in hotel_best or price < hotel_best[h_name]:
                hotel_best[h_name] = price

        if not hotel_best:
            return {"status": "skipped", "reason": "no_valid_prices"}

        sorted_hotels = sorted(hotel_best.items(), key=lambda x: (x[1], x[0]))[:10]
        top10_hotels = [
            {"name": name, "price": price, "position": idx + 1}
            for idx, (name, price) in enumerate(sorted_hotels)
        ]
        prices = [h["price"] for h in top10_hotels]
        avg_price = round(sum(prices) / len(prices), 1)
        min_price = round(min(prices), 1)
        max_price = round(max(prices), 1)

        run_time_str = scraped_at.strftime("%Y-%m-%d %H:%M:%S")
        scraped_iso = scraped_at.isoformat()
        scraped_display = scraped_at.strftime("%d.%m.%Y %H:%M")
        now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")

        # 2. Update dashboard HTML chart & KPIs
        if dashboard_file and dashboard_file.is_file():
            try:
                content = dashboard_file.read_text(encoding="utf-8")

                m_x = re.search(r"const X = (\[.*?\]);", content)
                m_y = re.search(r"const Y = (\[.*?\]);", content)
                m_min = re.search(r"const minY = (\[.*?\]);", content)
                m_max = re.search(r"const maxY = (\[.*?\]);", content)
                m_det = re.search(r"const detailedData = (\[.*?\]);", content)

                if m_x and m_y and m_min and m_max and m_det:
                    xs = json.loads(m_x.group(1))
                    ys = json.loads(m_y.group(1))
                    mins = json.loads(m_min.group(1))
                    maxs = json.loads(m_max.group(1))
                    dets = json.loads(m_det.group(1))

                    if run_time_str not in xs:
                        # Compute price differences vs previous run
                        prev_entry = dets[-1] if dets else None
                        diff_data = cls._compute_run_differences(top10_hotels, avg_price, run_time_str, prev_entry)

                        xs.append(run_time_str)
                        ys.append(avg_price)
                        mins.append(min_price)
                        maxs.append(max_price)
                        dets.append(diff_data)

                        content = content.replace(m_x.group(0), f"const X = {json.dumps(xs, ensure_ascii=False)};", 1)
                        content = content.replace(m_y.group(0), f"const Y = {json.dumps(ys, ensure_ascii=False)};", 1)
                        content = content.replace(m_min.group(0), f"const minY = {json.dumps(mins, ensure_ascii=False)};", 1)
                        content = content.replace(m_max.group(0), f"const maxY = {json.dumps(maxs, ensure_ascii=False)};", 1)
                        content = content.replace(m_det.group(0), f"const detailedData = {json.dumps(dets, ensure_ascii=False)};", 1)

                # Patch KPI badge
                badge_pat = re.compile(
                    r'(<span class="update-status[^"]*" id="updateStatusBadge"[^>]*>)([\s\S]*?)(</span>)',
                    re.IGNORECASE,
                )
                new_badge = (
                    f'<span class="update-status update-status--ok" id="updateStatusBadge" '
                    f'title="Проверено: {now_str} | Свежие предложения: {scraped_display}" '
                    f'data-iso="{scraped_iso}">\n'
                    f'                                🟢 Обновлено\n'
                    f'                            </span>'
                )
                content = badge_pat.sub(new_badge, content)

                # Patch updateAgoText
                ago_pat = re.compile(
                    r'(<div class="kpi-card-number kpi-card-time" id="updateAgoText">)(.*?)(</div>)',
                    re.IGNORECASE,
                )
                content = ago_pat.sub(rf"\g<1>{scraped_display}\g<3>", content)

                # Patch min price
                price_formatted = f"от {int(min_price):,} zł".replace(",", " ")
                min_price_pat = re.compile(
                    r'(<div class="kpi-card-number" id="heroKpiMinPrice">)(.*?)(</div>)',
                    re.IGNORECASE,
                )
                content = min_price_pat.sub(rf"\g<1>{price_formatted}\g<3>", content)

                dashboard_file.write_text(content, encoding="utf-8")
                logger.info(f"📊 Dashboard {dashboard_file.name} chart and KPIs updated with point at {run_time_str} (min {min_price} zł).")
            except Exception as e:
                logger.error(f"Error patching dashboard {dashboard_file.name}: {e}", exc_info=True)

        # 3. Save last_run_offers.json in data folder
        if filter_dir:
            filter_dir.mkdir(parents=True, exist_ok=True)
            last_run_file = filter_dir / "last_run_offers.json"
            try:
                last_run_file.write_text(json.dumps(raw_offers, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            except Exception as err:
                logger.warning(f"Could not write last_run_offers.json: {err}")

            # 4. Update hotel_series
            series_dir = filter_dir / "hotel_series"
            if series_dir.is_dir():
                cls._append_offers_to_hotel_series(series_dir, hotel_best, run_time_str)

        cls._update_landing_page(now_str)
        return {
            "status": "success",
            "monitor_id": monitor_id,
            "run_time": run_time_str,
            "top10_avg": avg_price,
            "min_price": min_price,
        }

    @classmethod
    def _compute_run_differences(
        cls,
        top10_hotels: List[Dict[str, Any]],
        avg_price: float,
        run_time_str: str,
        prev_entry: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Calculates price differences and hover tooltips vs prior scrape run."""
        price_changes = []
        new_hotels = []
        removed_hotels = []
        avg_change = 0.0
        avg_pct = 0.0

        if prev_entry:
            prev_hotels = {h["name"]: h for h in prev_entry.get("top10_hotels", [])}
            cur_hotels = {h["name"]: h for h in top10_hotels}

            for name, cur in cur_hotels.items():
                if name in prev_hotels:
                    prev_p = prev_hotels[name]["price"]
                    cur_p = cur["price"]
                    if prev_p != cur_p:
                        diff = round(cur_p - prev_p, 1)
                        pct = round(((cur_p - prev_p) / prev_p) * 100, 2)
                        price_changes.append({
                            "name": name,
                            "old_price": prev_p,
                            "new_price": cur_p,
                            "change": diff,
                            "change_percent": pct,
                            "position": cur["position"],
                        })
                else:
                    new_hotels.append({
                        "name": name,
                        "price": cur["price"],
                        "position": cur["position"],
                    })

            for name, prev in prev_hotels.items():
                if name not in cur_hotels:
                    removed_hotels.append({
                        "name": name,
                        "price": prev["price"],
                        "position": prev["position"],
                    })

            prev_avg = prev_entry.get("avg_price", avg_price)
            if prev_avg:
                avg_change = round(avg_price - prev_avg, 1)
                avg_pct = round(((avg_price - prev_avg) / prev_avg) * 100, 2)

        arrow = "↗️" if avg_change > 0 else "↘️" if avg_change < 0 else ""
        sign = "+" if avg_change > 0 else ""

        hover_data = {
            "title": f"📊 ТОП-10 ({run_time_str})",
            "avg_price": avg_price,
            "avg_change": {
                "arrow": arrow,
                "change": avg_change,
                "change_percent": avg_pct,
                "sign": sign,
            } if avg_change != 0 else None,
            "price_changes": [
                {
                    **c,
                    "arrow": "↗️" if c["change"] > 0 else "↘️",
                    "sign": "+" if c["change"] > 0 else "",
                }
                for c in price_changes
            ],
            "new_hotels": new_hotels,
            "removed_hotels": removed_hotels,
            "no_changes": len(price_changes) == 0 and len(new_hotels) == 0 and len(removed_hotels) == 0,
        }

        return {
            "run_time": run_time_str,
            "avg_price": avg_price,
            "min_price": top10_hotels[0]["price"] if top10_hotels else avg_price,
            "max_price": top10_hotels[-1]["price"] if top10_hotels else avg_price,
            "top10_hotels": top10_hotels,
            "price_changes": price_changes,
            "new_hotels": new_hotels,
            "removed_hotels": removed_hotels,
            "avg_price_change": avg_change,
            "avg_price_change_percent": avg_pct,
            "hover_data": hover_data,
        }

    @classmethod
    def _append_offers_to_hotel_series(
        cls, series_dir: Path, hotel_best: Dict[str, float], run_time_str: str
    ):
        """Appends latest best price for each hotel into its series JSON file."""
        for hotel_name, price in hotel_best.items():
            slug = slugify(hotel_name)
            series_file = series_dir / f"{slug}.json"
            if not series_file.is_file():
                continue

            try:
                data = json.loads(series_file.read_text(encoding="utf-8"))
                x_list = data.get("x", [])
                y_list = data.get("y", [])

                if run_time_str not in x_list:
                    x_list.append(run_time_str)
                    y_list.append(float(price))

                    data["x"] = x_list
                    data["y"] = y_list
                    data["samples"] = len(x_list)
                    data["current_price"] = float(price)
                    data["min_p"] = min(y_list)
                    data["max_p"] = max(y_list)

                    series_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                logger.debug(f"Could not update series for {slug}: {e}")

    @classmethod
    def _find_dashboard_file(cls, monitor_id: str) -> Optional[Path]:
        """Resolves HTML filename for a monitor ID."""
        candidates = [
            cls.SITE_DIR / f"index_filter_{monitor_id}.html",
            cls.SITE_DIR / f"index_filter_{monitor_id}_days.html",
        ]
        if monitor_id == "turkey_vacation_jul18":
            candidates.append(cls.SITE_DIR / "index_filter_turkey_vacation_jul18.html")
        elif monitor_id == "cyprus_7_10":
            candidates.append(cls.SITE_DIR / "index_filter_cyprus_7_10.html")

        for c in candidates:
            if c.is_file():
                return c
        return None

    @classmethod
    def _find_filter_data_dir(cls, monitor_id: str) -> Optional[Path]:
        """Resolves data/filters folder for a monitor ID."""
        filters_dir = cls.SITE_DIR / "data" / "filters"
        candidates = [
            filters_dir / f"filter_{monitor_id}",
            filters_dir / f"filter_{monitor_id}_days",
        ]
        if monitor_id == "turkey_vacation_jul18":
            candidates.append(filters_dir / "filter_turkey_vacation_jul18_2026")

        for c in candidates:
            if c.is_dir():
                return c
        return None

    @classmethod
    def _update_dashboard_kpis_only(cls, html_path: Path, monitor: FilterMonitor, now_str: str):
        """Patches KPI badges and min price if no new run data is available."""
        content = html_path.read_text(encoding="utf-8")

        scraped_dt = monitor.last_scraped_at or datetime.now(timezone.utc)
        scraped_iso = scraped_dt.isoformat()
        scraped_display = scraped_dt.strftime("%d.%m.%Y %H:%M")

        badge_pat = re.compile(
            r'(<span class="update-status[^"]*" id="updateStatusBadge"[^>]*>)([\s\S]*?)(</span>)',
            re.IGNORECASE,
        )
        new_badge = (
            f'<span class="update-status update-status--ok" id="updateStatusBadge" '
            f'title="Проверено: {now_str} | Свежие предложения: {scraped_display}" '
            f'data-iso="{scraped_iso}">\n'
            f'                                🟢 Обновлено\n'
            f'                            </span>'
        )
        content = badge_pat.sub(new_badge, content)

        ago_pat = re.compile(
            r'(<div class="kpi-card-number kpi-card-time" id="updateAgoText">)(.*?)(</div>)',
            re.IGNORECASE,
        )
        content = ago_pat.sub(rf"\g<1>{scraped_display}\g<3>", content)

        if monitor.last_min_price_pln and monitor.last_min_price_pln > 0:
            price_formatted = f"от {int(monitor.last_min_price_pln):,} zł".replace(",", " ")
            min_price_pat = re.compile(
                r'(<div class="kpi-card-number" id="heroKpiMinPrice">)(.*?)(</div>)',
                re.IGNORECASE,
            )
            content = min_price_pat.sub(rf"\g<1>{price_formatted}\g<3>", content)

        html_path.write_text(content, encoding="utf-8")

    @classmethod
    async def _update_hotel_series_for_monitor(cls, db: AsyncSession, monitor: FilterMonitor):
        """Fallback DB query to update hotel series."""
        data_dir = cls._find_filter_data_dir(monitor.id)
        if not data_dir:
            return

        series_dir = data_dir / "hotel_series"
        if not series_dir.is_dir():
            return

        stmt = (
            select(
                Hotel.display_name,
                PriceSnapshot.total_price_pln,
                PriceSnapshot.recorded_at,
                OfferCohort.offer_url,
            )
            .join(OfferCohort, PriceSnapshot.cohort_hash == OfferCohort.cohort_hash)
            .join(Hotel, OfferCohort.hotel_id == Hotel.hotel_id)
            .where(OfferCohort.destination_code == monitor.destination)
            .order_by(PriceSnapshot.recorded_at.desc())
            .limit(100)
        )
        res = await db.execute(stmt)
        recent_points = res.all()

        for h_name, price, recorded_at, offer_url in recent_points:
            slug = slugify(h_name)
            series_file = series_dir / f"{slug}.json"
            if not series_file.is_file():
                continue

            try:
                data = json.loads(series_file.read_text(encoding="utf-8"))
                x_list = data.get("x", [])
                y_list = data.get("y", [])

                rec_str = recorded_at.strftime("%Y-%m-%d %H:%M:%S")
                if rec_str not in x_list:
                    x_list.append(rec_str)
                    y_list.append(float(price))

                    data["x"] = x_list
                    data["y"] = y_list
                    data["samples"] = len(x_list)
                    data["current_price"] = float(price)
                    data["min_p"] = min(y_list)
                    data["max_p"] = max(y_list)

                    series_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                logger.debug(f"Could not append series for {slug}: {e}")

    @classmethod
    def _update_landing_page(cls, now_str: str):
        """Updates header timestamp in site/index.html."""
        landing_file = cls.SITE_DIR / "index.html"
        if not landing_file.is_file():
            return
        content = landing_file.read_text(encoding="utf-8")
        pat = re.compile(r'(<span>Обновлено:\s*)([0-9.:\s]+)(</span>)', re.IGNORECASE)
        content = pat.sub(rf"\g<1>{now_str}\g<3>", content)
        landing_file.write_text(content, encoding="utf-8")

    @classmethod
    def _update_hotels_catalog_timestamp(cls, now_utc: datetime):
        """Updates generated_at in site/hotels_catalog_data.json."""
        catalog_file = cls.SITE_DIR / "hotels_catalog_data.json"
        if not catalog_file.is_file():
            return
        try:
            with open(catalog_file, "r+", encoding="utf-8") as f:
                head = f.read(500)
                new_head = re.sub(
                    r'("generated_at":\s*")[^"]+(")',
                    rf'\g<1>{now_utc.isoformat()}\g<2>',
                    head,
                    count=1,
                )
                if new_head != head:
                    f.seek(0)
                    f.write(new_head)
        except Exception as e:
            logger.warning(f"Could not patch hotels_catalog_data.json timestamp: {e}")
