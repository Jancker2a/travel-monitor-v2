import urllib.parse
from datetime import timedelta
from typing import Dict, Any, List
from app.schemas.search import SearchRequest

DESTINATION_CODES: Dict[str, str] = {
    "egypt": "1:",
    "egypt_sharm": "1:1",
    "egypt_hurghada": "1:2",
    "egypt_marsa": "1:3",
    "turkey": "2:",
    "turkey_antalya": "2:1",
    "turkey_aegean": "2:2",
    "greece": "3:",
    "greece_crete": "3:1",
    "greece_rhodes": "3:2",
    "spain": "4:",
    "cyprus": "6:",
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
    "BER": "Berlin",
}


class UniversalQueryBuilder:
    """Translates arbitrary universal search parameters into provider-specific queries."""

    @staticmethod
    def build_flypl_url(req: SearchRequest, page: int = 1) -> str:
        base_url = "https://fly.pl/szukaj-wycieczek/"
        
        # Resolve destination
        dest_key = req.destination.strip().lower()
        dest_code = DESTINATION_CODES.get(dest_key, dest_key)
        
        # Resolve airports
        dep_locations: List[str] = []
        for code in req.airports:
            c_upper = code.strip().upper()
            if c_upper in AIRPORT_NAMES:
                dep_locations.append(AIRPORT_NAMES[c_upper])
            else:
                dep_locations.append(code.strip())
        
        dep_str = ",".join(dep_locations) if dep_locations else "Warszawa,Katowice"
        
        # Dates formatting
        start_min = req.dates.start_date_min.strftime("%d-%m-%Y")
        start_max = req.dates.start_date_max.strftime("%d-%m-%Y")
        calc_return = req.dates.start_date_max + timedelta(days=req.duration.max_nights + 1)
        return_date = calc_return.strftime("%d-%m-%Y")
        
        params: Dict[str, Any] = {
            "destinationLocation": dest_code,
            "departureLocation": dep_str,
            "startDateMin": start_min,
            "startDateMax": start_max,
            "returnDate": return_date,
            "adults": req.travelers.adults,
            "offerTypes": "accommodation_flight",
            "durationFrom": req.duration.min_nights,
            "durationTo": req.duration.max_nights,
            "order": "price",
        }
        
        if req.travelers.children > 0:
            params["children"] = req.travelers.children
            if req.travelers.children_ages:
                params["childrenAges"] = ",".join(str(a) for a in req.travelers.children_ages)
                
        if req.price_max_pln and req.price_max_pln > 0:
            params["priceTo"] = int(req.price_max_pln)

        if page > 1:
            params["p"] = page

        query_str = urllib.parse.urlencode(params)
        return f"{base_url}?{query_str}"

