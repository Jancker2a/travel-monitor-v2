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
        """Updates HTML dashboards, hotel_series JSONs, and catalog data from DB snapshots."""
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
                cls._update_dashboard_html(dashboard_file, m, now_str)
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
    def _update_dashboard_html(cls, html_path: Path, monitor: FilterMonitor, now_str: str):
        """Patches KPI badges, timestamps, and min price in the HTML dashboard."""
        content = html_path.read_text(encoding="utf-8")

        scraped_dt = monitor.last_scraped_at or datetime.now(timezone.utc)
        scraped_iso = scraped_dt.isoformat()
        scraped_display = scraped_dt.strftime("%d.%m.%Y %H:%M")

        # 1. Update updateStatusBadge
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

        # 2. Update updateAgoText
        ago_pat = re.compile(
            r'(<div class="kpi-card-number kpi-card-time" id="updateAgoText">)(.*?)(</div>)',
            re.IGNORECASE,
        )
        content = ago_pat.sub(rf"\g<1>{scraped_display}\g<3>", content)

        # 3. Update min price if available
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
        """Appends the latest price points into the hotel_series JSON files."""
        data_dir = cls._find_filter_data_dir(monitor.id)
        if not data_dir:
            return

        series_dir = data_dir / "hotel_series"
        if not series_dir.is_dir():
            return

        # Query recent snapshots recorded for cohorts under this destination
        # We join PriceSnapshot -> OfferCohort -> Hotel
        stmt = (
            select(
                Hotel.display_name,
                PriceSnapshot.total_price_pln,
                PriceSnapshot.recorded_at,
                OfferCohort.checkin_date,
                OfferCohort.checkout_date,
                OfferCohort.duration_nights,
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

        for h_name, price, recorded_at, checkin, checkout, duration, offer_url in recent_points:
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
                    data["min_p"] = min(y_list)
                    data["max_p"] = max(y_list)
                    if offer_url and "meta" in data:
                        data["meta"]["offer_url"] = offer_url

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
            # We read only enough or stream if big, or update JSON
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
