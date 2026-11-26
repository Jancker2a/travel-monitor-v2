#!/usr/bin/env python3
"""
Consolidates duplicate & renamed hotels in Neon PostgreSQL and builds:
1. backend/app/knowledge/hotel_aliases_kb.json (canonical hotel clusters + external IDs + rename chains)
2. Cleaned & validated backend/app/knowledge/hotel_canonical_crossborder_kb.json

Usage:
  PYTHONPATH=backend .venv/bin/python3 scripts/consolidate_hotels_and_aliases.py --dry-run
  PYTHONPATH=backend .venv/bin/python3 scripts/consolidate_hotels_and_aliases.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.services.arbitrage_service import get_check24_kb, normalize_dest_key
from app.services.hotel_entity_matcher import (
    HotelEntityMatcher,
    UnionFind,
    _canonicalize_for_key,
    calculate_hotel_similarity,
    extract_check24_hotel_id,
    extract_fly_object_id,
    extract_fly_url_slug,
    extract_geo_zones,
    extract_hotel_aliases,
    fold_unicode,
    geo_zones_conflict,
)

ROOT = Path(__file__).resolve().parents[1]
ALIASES_KB_PATH = ROOT / "backend" / "app" / "knowledge" / "hotel_aliases_kb.json"
CROSSBORDER_KB_PATH = ROOT / "backend" / "app" / "knowledge" / "hotel_canonical_crossborder_kb.json"


def _is_truncated(name: str) -> bool:
    s = (name or "").strip()
    return len(s) == 40 and not s.endswith(")")


def _has_geo_tail(name: str) -> bool:
    return bool(re.search(r"\b(?:egipt|turcja|grecja|cypr|hiszpania|bulgaria)\s*,", fold_unicode(name or "")))


def _choose_canonical_hotel(group_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Picks the best surviving hotel_id and display_name for a merged cluster:
    - Prefer most cohorts / snapshots
    - Avoid truncated 40-char names and raw country-tail names ('Egipt, ...')
    - Prefer newer rebranded name when it explicitly mentions '(ex. ...)' or 'SRNTY' and has active cohorts
    """
    def _rank_row(r: Dict[str, Any]) -> Tuple[int, int, int, int, int]:
        dn = r["display_name"]
        has_ex_or_srnty = 1 if (re.search(r"\b(srnty|ex\.|dawniej)\b", dn, re.I) and not _has_geo_tail(dn)) else 0
        not_trunc = 0 if _is_truncated(dn) else 1
        no_tail = 0 if _has_geo_tail(dn) else 1
        cohorts = int(r.get("cohorts", 0))
        has_specs = 1 if r.get("has_specs") else 0
        return (not_trunc, no_tail, has_specs, cohorts, has_ex_or_srnty)

    best = max(group_rows, key=_rank_row)

    # Pick cleanest current display_name (prefer latest non-truncated name without country tail)
    def _name_rank(r: Dict[str, Any]) -> Tuple[int, int, int, int, int, str]:
        dn = r["display_name"]
        not_trunc = 0 if _is_truncated(dn) else 1
        no_tail = 0 if _has_geo_tail(dn) else 1
        is_recent = 1 if (r.get("max_checkin") and str(r["max_checkin"]) >= "2026-11-25") else 0
        is_rebranded = 1 if re.search(r"(\bsrnty\b|\(ex\.|\s+[xX×]\s+)", dn, re.I) else 0
        not_all_caps = 0 if dn.isupper() else 1
        return (not_trunc, no_tail, is_recent, is_rebranded, not_all_caps, dn)

    best_name_row = max(group_rows, key=_name_rank)
    return {
        "keep_id": best["hotel_id"],
        "display_name": best_name_row["display_name"],
        "country": best["country"],
    }


async def run(apply: bool = False) -> None:
    async with AsyncSessionLocal() as db:
        hotels_raw = (
            await db.execute(
                text(
                    """
                    SELECT h.hotel_id, h.display_name, h.country, h.region, h.stars,
                           h.ta_rating, h.ta_reviews, h.main_image_url,
                           (h.specs IS NOT NULL) AS has_specs,
                           (h.reputation IS NOT NULL) AS has_rep,
                           COUNT(DISTINCT oc.cohort_id) AS cohorts,
                           MAX(oc.checkin_date) AS max_checkin
                    FROM hotels h
                    LEFT JOIN offer_cohorts oc ON oc.hotel_id = h.hotel_id
                    GROUP BY h.hotel_id, h.display_name, h.country, h.region, h.stars,
                             h.ta_rating, h.ta_reviews, h.main_image_url, (h.specs IS NOT NULL), (h.reputation IS NOT NULL)
                    ORDER BY h.country, h.hotel_id
                    """
                )
            )
        ).fetchall()

        hotels_by_id: Dict[str, Dict[str, Any]] = {}
        for r in hotels_raw:
            hotels_by_id[r[0]] = {
                "hotel_id": r[0],
                "display_name": r[1],
                "country": r[2],
                "region": r[3],
                "stars": r[4],
                "ta_rating": r[5],
                "ta_reviews": r[6],
                "main_image_url": r[7],
                "has_specs": bool(r[8]),
                "has_rep": bool(r[9]),
                "cohorts": int(r[10] or 0),
                "max_checkin": r[11],
                "oids": set(),
                "slugs": set(),
                "sample_url": None,
            }

        url_rows = (
            await db.execute(
                text(
                    """
                    SELECT DISTINCT oc.hotel_id, oc.offer_url
                    FROM offer_cohorts oc
                    WHERE oc.offer_url IS NOT NULL AND oc.offer_url != ''
                    """
                )
            )
        ).fetchall()

        for hid, url in url_rows:
            h = hotels_by_id.get(hid)
            if not h:
                continue
            if not h["sample_url"]:
                h["sample_url"] = url
            oid = extract_fly_object_id(url)
            if oid:
                h["oids"].add(oid)
            sl = extract_fly_url_slug(url)
            if sl:
                h["slugs"].add(sl)

        # Build Union-Find clusters per country
        uf = UnionFind()
        for hid in hotels_by_id:
            uf.find(hid)

        merge_reasons: Dict[Tuple[str, str], str] = {}

        def _try_union(h1: str, h2: str, reason: str, strict_geo: bool = True, allow_diff_oid: bool = False) -> None:
            if h1 == h2:
                return
            r1, r2 = hotels_by_id[h1], hotels_by_id[h2]
            if fold_unicode(r1["country"]) != fold_unicode(r2["country"]):
                return
            if not allow_diff_oid and r1["oids"] and r2["oids"] and not r1["oids"].intersection(r2["oids"]):
                return
            if strict_geo:
                z1 = extract_geo_zones(r1["display_name"], r1["country"], r1["region"], r1["sample_url"])
                z2 = extract_geo_zones(r2["display_name"], r2["country"], r2["region"], r2["sample_url"])
                if geo_zones_conflict(z1, z2):
                    return
            ra, rb = uf.find(h1), uf.find(h2)
            if ra != rb:
                uf.union(h1, h2)
                merge_reasons[(h1, h2)] = reason

        # Signal 1: Same (country, Fly.pl objectId)
        by_oid: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        for hid, h in hotels_by_id.items():
            ctry = fold_unicode(h["country"])
            for oid in h["oids"]:
                by_oid[(ctry, oid)].append(hid)
        for (_, oid), hids in by_oid.items():
            if len(hids) > 1:
                for other in hids[1:]:
                    _try_union(hids[0], other, f"fly_object_id={oid}", strict_geo=False, allow_diff_oid=True)

        # Signal 2: Same (country, Fly.pl URL slug) -> only when no conflicting objectId AND names/aliases match cleanly
        by_slug: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        for hid, h in hotels_by_id.items():
            ctry = fold_unicode(h["country"])
            for sl in h["slugs"]:
                by_slug[(ctry, sl)].append(hid)
        for (_, sl), hids in by_slug.items():
            if len(hids) > 1:
                for i in range(len(hids)):
                    for j in range(i + 1, len(hids)):
                        r1, r2 = hotels_by_id[hids[i]], hotels_by_id[hids[j]]
                        if r1["oids"] and r2["oids"] and not r1["oids"].intersection(r2["oids"]):
                            continue
                        # Verify at least one alias pair matches >= 0.85 so shared generic/operator slugs never merge sister hotels
                        a1s = extract_hotel_aliases(r1["display_name"])
                        a2s = extract_hotel_aliases(r2["display_name"])
                        best_sc = max(calculate_hotel_similarity(x, y) for x in a1s for y in a2s)
                        if best_sc >= 0.85:
                            _try_union(hids[i], hids[j], f"fly_slug={sl} ({best_sc})", strict_geo=True)

        # Signal 3: Exact canonical normalized key OR truncated 40-char prefix match within same country
        by_ckey: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        for hid, h in hotels_by_id.items():
            ctry = fold_unicode(h["country"])
            for al in extract_hotel_aliases(h["display_name"]):
                # Only use primary (first or cleaned without parens) for direct same-hotel key merge;
                # former names from '(ex. ...)' are linked via Signal 4 if unambiguous!
                break
            ck = _canonicalize_for_key(h["display_name"])
            if ck and len(ck.split()) >= 2:
                by_ckey[(ctry, ck)].append(hid)

        for (_, ck), hids in by_ckey.items():
            if len(hids) > 1:
                base = hids[0]
                r_base = hotels_by_id[base]
                for other in hids[1:]:
                    r_oth = hotels_by_id[other]
                    sc = calculate_hotel_similarity(
                        r_base["display_name"],
                        r_oth["display_name"],
                        region_hint1=r_base["region"],
                        region_hint2=r_oth["region"],
                        url1=r_base["sample_url"],
                        url2=r_oth["sample_url"],
                    )
                    if sc >= 0.90:
                        _try_union(base, other, f"canonical_key={ck} ({sc})", strict_geo=True)

        # Signal 4: Truncated 40-char names matching full name in same country
        by_country: Dict[str, List[str]] = defaultdict(list)
        for hid, h in hotels_by_id.items():
            by_country[fold_unicode(h["country"])].append(hid)

        for ctry, hids in by_country.items():
            truncs = [hid for hid in hids if _is_truncated(hotels_by_id[hid]["display_name"])]
            fulls = [hid for hid in hids if not _is_truncated(hotels_by_id[hid]["display_name"])]
            for th in truncs:
                t_name = hotels_by_id[th]["display_name"]
                t_fold = fold_unicode(t_name).rstrip(" (.-")
                for fh in fulls:
                    f_name = hotels_by_id[fh]["display_name"]
                    if fold_unicode(f_name).startswith(t_fold[:32]):
                        sc = calculate_hotel_similarity(
                            t_name, f_name,
                            region_hint1=hotels_by_id[th]["region"],
                            region_hint2=hotels_by_id[fh]["region"],
                            url1=hotels_by_id[th]["sample_url"],
                            url2=hotels_by_id[fh]["sample_url"],
                        )
                        if sc >= 0.85:
                            _try_union(fh, th, f"truncated_40={sc}", strict_geo=True)

        # Signal 5: Explicit rename chains (' X ' or '(ex. ...)') linking old/new DB records
        for hid, h in hotels_by_id.items():
            dn = h["display_name"]
            if not re.search(r"(\(ex\.?|\bex\.?\s+|\s+[xX×]\s+|\(dawniej|\(former)", dn, re.I):
                continue
            aliases = extract_hotel_aliases(dn)
            if len(aliases) < 2:
                continue
            ctry = fold_unicode(h["country"])
            for al in aliases[1:]:
                ak = _canonicalize_for_key(al)
                if not ak or len(ak.split()) < 2:
                    continue
                for cand_hid in by_ckey.get((ctry, ak), []):
                    if cand_hid != hid:
                        _try_union(hid, cand_hid, f"rename_link='{al}'", strict_geo=True)

        # Collect final multi-member clusters
        clusters_map: Dict[str, List[str]] = defaultdict(list)
        for hid in hotels_by_id:
            clusters_map[uf.find(hid)].append(hid)

        merge_clusters = [hids for hids in clusters_map.values() if len(hids) > 1]
        total_to_merge = sum(len(c) - 1 for c in merge_clusters)
        print(f"DB HOTELS: {len(hotels_by_id)} -> MERGE CLUSTERS: {len(merge_clusters)} (removing {total_to_merge} duplicates/renames)")

        # Preview Serenity + top clusters
        for c in merge_clusters:
            names = [hotels_by_id[x]["display_name"] for x in c]
            if any("serenity" in n.lower() or "srnty" in n.lower() for n in names):
                choice = _choose_canonical_hotel([hotels_by_id[x] for x in c])
                print("  SERENITY CLUSTER:", choice["keep_id"], "| display=", choice["display_name"], "| members=", names)

        print("\nSample 15 merge clusters:")
        for c in merge_clusters[:15]:
            choice = _choose_canonical_hotel([hotels_by_id[x] for x in c])
            print(" ", choice["keep_id"], "<-", [x for x in c if x != choice["keep_id"]])

        # Build hotel_aliases_kb.json from ALL clusters + Check24 hotelId groups
        kb_clusters: Dict[str, Dict[str, Any]] = {}
        for root_hid, hids in clusters_map.items():
            rows = [hotels_by_id[x] for x in hids]
            choice = _choose_canonical_hotel(rows)
            keep_id = choice["keep_id"]
            all_aliases: List[str] = []
            seen_a: Set[str] = set()
            all_oids: Set[str] = set()
            all_slugs: Set[str] = set()
            for r in rows:
                all_oids |= r["oids"]
                all_slugs |= r["slugs"]
                for a in [r["display_name"], *extract_hotel_aliases(r["display_name"])]:
                    ak = fold_unicode(a)
                    if a and ak not in seen_a:
                        seen_a.add(ak)
                        all_aliases.append(a)
            if len(all_aliases) > 1 or all_oids or all_slugs:
                z = extract_geo_zones(choice["display_name"], choice["country"], rows[0]["region"], rows[0]["sample_url"])
                kb_clusters[keep_id] = {
                    "canonical_name": choice["display_name"],
                    "country": choice["country"],
                    "geo_zone": z[1] or z[0],
                    "aliases": all_aliases,
                    "fly_object_ids": sorted(all_oids),
                    "fly_slugs": sorted(all_slugs),
                    "check24_hotel_ids": [],
                }

        # Attach Check24 hotelId groups (e.g. 26373 -> Serenity Alma Heights + SRNTY Sun Ray)
        c24_kb = get_check24_kb()
        c24_by_id: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for o in c24_kb.get("offers", []):
            cid_24 = extract_check24_hotel_id(o.get("offer_url"))
            if cid_24:
                c24_by_id[cid_24].append(o)

        for cid_24, offers in c24_by_id.items():
            de_names = sorted({o["hotel_name"] for o in offers if o.get("hotel_name")})
            de_dest = offers[0].get("destination")
            if len(de_names) > 1:
                # Multiple DE names share the exact same Check24 hotelId -> add to matching cluster or create one
                matched_cid = None
                for k_cid, rec in kb_clusters.items():
                    if normalize_dest_key(rec["country"]) != normalize_dest_key(de_dest):
                        continue
                    rec_keys = {_canonicalize_for_key(a) for a in rec["aliases"]}
                    if any(_canonicalize_for_key(dn) in rec_keys for dn in de_names):
                        matched_cid = k_cid
                        break
                if matched_cid:
                    rec = kb_clusters[matched_cid]
                    if cid_24 not in rec["check24_hotel_ids"]:
                        rec["check24_hotel_ids"].append(cid_24)
                    for dn in de_names:
                        if fold_unicode(dn) not in {fold_unicode(a) for a in rec["aliases"]}:
                            rec["aliases"].append(dn)
                else:
                    kb_clusters[f"check24_{cid_24}"] = {
                        "canonical_name": de_names[0],
                        "country": de_dest or "",
                        "geo_zone": None,
                        "aliases": de_names,
                        "fly_object_ids": [],
                        "fly_slugs": [],
                        "check24_hotel_ids": [cid_24],
                    }

        if not apply:
            print("\n[DRY RUN] No DB or KB files modified. Re-run with --apply to execute.")
            return

        # 1. Write hotel_aliases_kb.json
        ALIASES_KB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(ALIASES_KB_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "version": "1.0.0",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "total_clusters": len(kb_clusters),
                    "clusters": kb_clusters,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"Wrote {len(kb_clusters)} clusters to {ALIASES_KB_PATH}")

        # 2. Sanitize hotel_canonical_crossborder_kb.json using the strict V2 matcher
        if CROSSBORDER_KB_PATH.exists():
            with open(CROSSBORDER_KB_PATH, "r", encoding="utf-8") as f:
                cb_data = json.load(f)
            pl_to_de = cb_data.get("pl_to_de", {})
            kept_pl_to_de: Dict[str, Any] = {}
            removed_bad: List[Tuple[str, str]] = []
            for pl_n, rec in pl_to_de.items():
                de_n = rec.get("german_name", "")
                method = rec.get("verification_method", "")
                if "CURATED" in method:
                    kept_pl_to_de[pl_n] = rec
                    continue
                sc = calculate_hotel_similarity(pl_n, de_n)
                if sc >= 0.80:
                    kept_pl_to_de[pl_n] = rec
                else:
                    removed_bad.append((pl_n, de_n))
            cb_data["pl_to_de"] = kept_pl_to_de
            cb_data["de_to_pl"] = {
                v["german_name"]: v for v in kept_pl_to_de.values() if v.get("german_name")
            }
            cb_data["total_mappings"] = len(kept_pl_to_de)
            with open(CROSSBORDER_KB_PATH, "w", encoding="utf-8") as f:
                json.dump(cb_data, f, ensure_ascii=False, indent=2)
            print(f"Sanitized crossborder KB: kept={len(kept_pl_to_de)}, removed_false={len(removed_bad)} -> {removed_bad}")

        # 3. Apply hotel merges in Neon PostgreSQL safely
        merged_hotels = 0
        for c in merge_clusters:
            rows = [hotels_by_id[x] for x in c]
            choice = _choose_canonical_hotel(rows)
            keep_id = choice["keep_id"]
            drop_ids = [x for x in c if x != keep_id]

            # Best metadata inheritance
            best_img = next((r["main_image_url"] for r in rows if r["main_image_url"] and "data:image" not in r["main_image_url"]), None)
            best_ta = max([r["ta_rating"] for r in rows if r["ta_rating"]], default=None)
            best_rev = max([r["ta_reviews"] for r in rows if r["ta_reviews"]], default=0)
            best_stars = max([r["stars"] for r in rows if r["stars"]], default=4)

            aliases_list = sorted({r["display_name"] for r in rows if r["display_name"] != choice["display_name"]})

            # Update canonical hotel specs['aliases'] & metadata
            keep_specs_row = (await db.execute(text("SELECT specs, reputation FROM hotels WHERE hotel_id = :hid"), {"hid": keep_id})).fetchone()
            specs_obj = dict(keep_specs_row[0]) if (keep_specs_row and isinstance(keep_specs_row[0], dict)) else {}
            rep_obj = keep_specs_row[1] if keep_specs_row else None

            if not keep_specs_row[0] or not rep_obj:
                for did in drop_ids:
                    d_row = (await db.execute(text("SELECT specs, reputation FROM hotels WHERE hotel_id = :hid"), {"hid": did})).fetchone()
                    if d_row:
                        if not specs_obj and isinstance(d_row[0], dict):
                            specs_obj = dict(d_row[0])
                        if not rep_obj and d_row[1]:
                            rep_obj = d_row[1]

            existing_aliases = set(specs_obj.get("aliases") or [])
            existing_aliases.update(aliases_list)
            specs_obj["aliases"] = sorted(existing_aliases)

            await db.execute(
                text(
                    """
                    UPDATE hotels
                    SET display_name = :dn,
                        stars = GREATEST(COALESCE(stars, 4), :st),
                        ta_rating = COALESCE(ta_rating, :ta),
                        ta_reviews = GREATEST(COALESCE(ta_reviews, 0), :rev),
                        main_image_url = COALESCE(NULLIF(main_image_url, ''), :img),
                        specs = CAST(:sp AS json),
                        reputation = COALESCE(reputation, CAST(:rep AS json))
                    WHERE hotel_id = :hid
                    """
                ),
                {
                    "hid": keep_id,
                    "dn": choice["display_name"],
                    "st": best_stars,
                    "ta": best_ta,
                    "rev": best_rev,
                    "img": best_img,
                    "sp": json.dumps(specs_obj, ensure_ascii=False),
                    "rep": json.dumps(rep_obj, ensure_ascii=False) if rep_obj else None,
                },
            )

            for did in drop_ids:
                await db.execute(
                    text("UPDATE offer_cohorts SET hotel_id = :keep WHERE hotel_id = :drop"),
                    {"keep": keep_id, "drop": did},
                )
                await db.execute(
                    text("UPDATE normalized_price_snapshots SET hotel_id = :keep WHERE hotel_id = :drop"),
                    {"keep": keep_id, "drop": did},
                )
                await db.execute(
                    text("DELETE FROM hotels WHERE hotel_id = :drop"),
                    {"drop": did},
                )
                merged_hotels += 1

        await db.commit()
        print(f"DB MERGE COMPLETE: consolidated {merged_hotels} duplicate/renamed hotel records into canonical entities.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(apply=args.apply))
