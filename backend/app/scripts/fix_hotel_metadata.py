"""
Migration script: Canonical Geo Metadata Fix.
Applies GeoResolver across the entire hotels table, eliminating contradictions
(like 'Турция • Сафага') and accurately setting resorts (e.g. Arena Beach -> Хургада).
"""

import asyncio
import logging
from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.services.geo_resolver import GeoResolver

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fix_hotel_metadata")


async def main():
    logger.info("Starting canonical geo metadata migration...")
    async with AsyncSessionLocal() as db:
        # Fetch all hotels and their representative offer URLs
        stmt = text("""
            SELECT h.hotel_id, h.display_name, h.country, h.region,
                   (SELECT oc.offer_url FROM offer_cohorts oc WHERE oc.hotel_id = h.hotel_id AND oc.offer_url LIKE '%/wycieczka/%' LIMIT 1) as url
            FROM hotels h
        """)
        res = await db.execute(stmt)
        hotels = res.fetchall()
        logger.info(f"Fetched {len(hotels)} hotels from database.")

        updates = []
        for hid, name, curr_c, curr_r, url in hotels:
            new_c, new_r = GeoResolver.resolve(
                hotel_name=name,
                offer_url=url,
                current_country=curr_c,
                current_region=curr_r,
            )
            if new_c != curr_c or new_r != curr_r:
                updates.append((new_c, new_r, hid))

        logger.info(f"Identified {len(updates)} hotels needing geo correction.")

        if updates:
            batch_size = 200
            for i in range(0, len(updates), batch_size):
                batch = updates[i : i + batch_size]
                for new_c, new_r, hid in batch:
                    await db.execute(
                        text("UPDATE hotels SET country = :c, region = :r WHERE hotel_id = :hid"),
                        {"c": new_c, "r": new_r, "hid": hid},
                    )
                await db.commit()
                logger.info(f"Committed {min(i + batch_size, len(updates))} / {len(updates)} updates...")

        logger.info("Successfully completed canonical geo metadata migration.")

        # Verification check
        v_res = await db.execute(text("""
            SELECT display_name, country, region
            FROM hotels
            WHERE display_name ILIKE '%arena beach%' OR display_name ILIKE '%shams safaga%'
        """))
        for row in v_res.fetchall():
            logger.info(f"VERIFIED: {row[0]} -> {row[1]} • {row[2]}")

if __name__ == "__main__":
    asyncio.run(main())

