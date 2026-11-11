import urllib.parse
from datetime import timedelta
from typing import Dict, Any, List
from app.schemas.search import SearchRequest

DESTINATION_CODES: Dict[str, str] = {
    # Turkey (39)
    "turkey": "39:",
    "turkey_antalya": "39_14",
    "turkey_aegean": "39_25",
    "turkey_side": "39_14",
    "turkey_alanya": "39_3",
    "turkey_belek": "39_23",
    "turkey_kemer": "39_73",
    "turkey_bodrum": "39_25",
    "turkey_marmaris": "39_196",
    # Egypt (11)
    "egypt": "11:",
    "egypt_sharm": "11_154",
    "egypt_hurghada": "11_64",
    "egypt_marsa": "11_228",
    # Greece (14)
    "greece": "14:",
    "greece_crete": "14_89",
    "greece_rhodes": "14_150",
    "greece_corfu": "14_83",
    "greece_zakynthos": "14_1066",
    "greece_kos": "14_84",
    # Cyprus (6)
    "cyprus": "6:",
    "cyprus_south": "6:",
    "cyprus_north": "6_2616",
    # Spain (15) - Ground truth on Fly.pl (18 is Jamaica/Cuba!)
    "spain": "15:",
    "spain_mallorca": "15_105",
    "spain_canary": "15_flykanary",
    "spain_costa_del_sol": "15_40",
    "spain_costa_blanca": "15_2063",
    # Bulgaria (3) - Ground truth on Fly.pl (4 was empty)
    "bulgaria": "3:",
    # Tunisia (38) - Ground truth on Fly.pl (37 was empty)
    "tunisia": "38:",
    "tunisia_djerba": "38_2",
    "tunisia_mainland": "38_1",
    # UAE (372) - Ground truth on Fly.pl (44 was Italy!)
    "uae": "372:",
    "uae_dubai": "372_46",
    # Italy (44) - Ground truth on Fly.pl (21 was empty)
    "italy": "44:",
    "italy_sicily": "44_2",
    # Malta (26) - Ground truth on Fly.pl (28 was Mauritius)
    "malta": "26:",
}

AIRPORT_NAMES: Dict[str, str] = {
    "WAW": "Warszawa",
    "WMI": "Warszawa - Modlin",
    "RDO": "Warszawa - Radom",
    "KTW": "Katowice",
    "KRK": "Kraków",
    "GDN": "Gdańsk",
    "WRO": "Wrocław",
    "POZ": "Poznań",
    "RZE": "Rzeszów",
    "BZG": "Bydgoszcz",
    "LUZ": "Lublin",
    "SZZ": "Szczecin",
    "LCJ": "Łódź",
    "BER": "Berlin",
}


class UniversalQueryBuilder:
    """Translates arbitrary universal search parameters into provider-specific queries."""

    @staticmethod
    def build_flypl_url(req: SearchRequest, page: int = 1) -> str:
        base_url = "https://fly.pl/szukaj-wycieczek/"
        
        # Resolve destination / region
        target_dest = req.region if req.region else req.destination
        dest_key = target_dest.strip().lower()
        dest_code = DESTINATION_CODES.get(dest_key, DESTINATION_CODES.get(req.destination.strip().lower(), "39:"))
        
        # Resolve airports
        dep_locations: List[str] = []
        for code in req.airports:
            c_upper = code.strip().upper()
            if c_upper in AIRPORT_NAMES:
                dep_locations.append(AIRPORT_NAMES[c_upper])
            else:
                dep_locations.append(code.strip())
        
        dep_str = ",".join(dep_locations) if dep_locations else "Warszawa,Katowice,Kraków,Gdańsk,Wrocław,Poznań"
        
        # Dates formatting
        start_min = req.dates.start_date_min.strftime("%d-%m-%Y") if req.dates.start_date_min else ""
        start_max = req.dates.start_date_max.strftime("%d-%m-%Y") if req.dates.start_date_max else ""
        
        if req.dates.start_date_max:
            calc_return = req.dates.start_date_max + timedelta(days=req.duration.max_nights + 1)
            return_date = calc_return.strftime("%d-%m-%Y")
        else:
            return_date = ""
        
        params: Dict[str, Any] = {
            "destinationLocation": dest_code,
            "departureLocation": dep_str,
            "adults": req.travelers.adults,
            "offerTypes": "accommodation_flight",
            "durationFrom": req.duration.min_nights,
            "durationTo": req.duration.max_nights,
            "order": req.order_by or "price",
        }

        if start_min:
            params["startDateMin"] = start_min
        if start_max:
            params["startDateMax"] = start_max
        if return_date:
            params["returnDate"] = return_date
        
        if req.travelers.children > 0:
            ref_year = req.dates.start_date_min.year if req.dates.start_date_min else 2026
            ages = req.travelers.children_ages if req.travelers.children_ages else [6] * req.travelers.children
            birthdates = [f"15-06-{ref_year - age}" for age in ages]
            params["children"] = ",".join(birthdates)

        if req.catering and req.catering != "all":
            params["catering"] = req.catering

        if req.stars_min and req.stars_min > 0:
            params["categoryRating"] = req.stars_min * 10
                
        if req.price_min_pln and req.price_min_pln > 0:
            params["priceFrom"] = int(req.price_min_pln)

        if req.price_max_pln and req.price_max_pln > 0:
            params["priceTo"] = int(req.price_max_pln)

        if page > 1:
            params["p"] = page

        query_str = urllib.parse.urlencode(params, safe=":,+")
        return f"{base_url}?{query_str}"

