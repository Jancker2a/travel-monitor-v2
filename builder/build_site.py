#!/usr/bin/env python3
"""
builder/build_site.py — Orchestrates generation of all authentic V1 dashboards,
landing hub, hotel catalog, and outputs everything to site/.
"""

import os
import sys
import shutil
import subprocess
import time
from pathlib import Path

BUILDER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BUILDER_DIR.parent
SITE_DIR = PROJECT_ROOT / "site"

sys.path.insert(0, str(BUILDER_DIR))

from filter_registry import get_all_dashboard_configs, all_filter_groups_with_archive


def build_site():
    t0 = time.time()
    print("🚀 Starting authentic dashboard generation from database...")

    # Ensure output directories exist
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "data" / "filters").mkdir(parents=True, exist_ok=True)

    # Copy static assets and HTML templates
    assets_src = BUILDER_DIR / "assets"
    if assets_src.is_dir():
        shutil.copytree(assets_src, SITE_DIR / "assets", dirs_exist_ok=True)

    for item in [
        "favicon.svg",
        "hotel-chart.html",
        "help.html",
        "create_filter.html",
        "filter_builder.js",
        "admin_filters.html",
    ]:
        src_file = BUILDER_DIR / item
        if src_file.is_file():
            shutil.copy(src_file, SITE_DIR / item)

    configs = get_all_dashboard_configs()
    print(f"📋 Found {len(configs)} dashboard configurations.")

    for i, cfg in enumerate(configs, 1):
        out_name = cfg["output"]
        title = cfg["title"]
        data_file = cfg["data"]
        charts_dir = cfg["charts"]
        alerts_file = cfg.get("alerts")

        print(f"[{i}/{len(configs)}] Generating {out_name}...")
        cmd = [
            sys.executable,
            str(BUILDER_DIR / "generate_inline_charts_dashboard.py"),
            "--data-file", data_file,
            "--output", str(SITE_DIR / out_name),
            "--title", title,
            "--charts-dir", str(SITE_DIR / charts_dir),
            "--display-price-ceiling", str(cfg.get("display_price_ceiling", 10000)),
            "--history-price-ceiling", str(cfg.get("history_price_ceiling", 20000)),
        ]
        if cfg.get("config"):
            cmd.extend(["--config-file", cfg["config"]])
        if alerts_file:
            cmd.extend(["--alerts-file", alerts_file])

        res = subprocess.run(cmd, cwd=str(BUILDER_DIR), capture_output=True, text=True)
        if res.returncode != 0:
            print(f"⚠️ Warning: {out_name} returned code {res.returncode}")
            if res.stderr:
                print(res.stderr[-400:])
        else:
            print(f"  ✓ {out_name} ready")

    # Generate Landing
    print("📑 Generating landing hub (index.html)...")
    res_landing = subprocess.run([sys.executable, str(BUILDER_DIR / "generate_landing.py")], cwd=str(BUILDER_DIR), capture_output=True, text=True)
    if (BUILDER_DIR / "index.html").is_file():
        shutil.copy(BUILDER_DIR / "index.html", SITE_DIR / "index.html")
    if (BUILDER_DIR / "help.html").is_file():
        shutil.copy(BUILDER_DIR / "help.html", SITE_DIR / "help.html")

    # Generate Hotel Catalog
    print("🏨 Generating hotel catalog (hotels.html)...")
    subprocess.run([sys.executable, str(BUILDER_DIR / "build_hotel_catalog.py")], cwd=str(BUILDER_DIR), capture_output=True, text=True)
    if (BUILDER_DIR / "hotels.html").is_file():
        shutil.copy(BUILDER_DIR / "hotels.html", SITE_DIR / "hotels.html")
    if (BUILDER_DIR / "hotels_catalog_data.json").is_file():
        shutil.copy(BUILDER_DIR / "hotels_catalog_data.json", SITE_DIR / "hotels_catalog_data.json")

    print(f"✅ Full site build completed in {time.time() - t0:.1f}s at {SITE_DIR}")


if __name__ == "__main__":
    build_site()
