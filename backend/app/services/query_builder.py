import urllib.parse
from datetime import timedelta
from typing import Dict, Any, List
from app.schemas.search import SearchRequest

DESTINATION_CODES: Dict[str, str] = {
    "turkey": "39:",
    "turkey_antalya": "39_3",
    "turkey_aegean": "39_14",
    "turkey_side": "39_3_40",
    "turkey_alanya": "39_3_38",
    "turkey_belek": "39_3_39",
    "turkey_kemer": "39_3_41",
    "turkey_bodrum": "39_14_45",
    "turkey_marmaris": "39_14_44",
    "egypt": "11:",
    "egypt_sharm": "11_154",
    "egypt_hurghada": "11_155",
    "egypt_marsa": "11_156",
    "greece": "14:",
    "greece_crete": "14_1",
    "greece_rhodes": "14_2",
    "greece_corfu": "14_4",
    "greece_zakynthos": "14_3",
    "greece_kos": "14_5",
    "cyprus": "6:",
    "cyprus_south": "6_1",
    "cyprus_north": "6_2",
    "spain": "18:",
    "spain_mallorca": "18_1",
    "spain_canary": "18_13",
    "spain_costa_del_sol": "18_3",
    "bulgaria": "4:",
    "tunisia": "37:",
    "italy": "21:",
    "uae": "44:",
    "malta": "28:",
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
            params["children"] = req.travelers.children
            if req.travelers.children_ages:
                params["childrenAges"] = ",".join(str(a) for a in req.travelers.children_ages)

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

        query_str = urllib.parse.urlencode(params)
        return f"{base_url}?{query_str}"

