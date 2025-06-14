# real_estate_tool.py

import os
import requests
from typing import Optional, List, Dict

# Optional: categoryExternalIDs from Bayut docs
PROPERTY_TYPE_IDS = {
    "apartment": "4",
    "villa": "16",
    "townhouse": "17",
    "penthouse": "19",
    "office": "7",
    "shop": "6",
    "plot": "9"
}

# For general "Dubai" fallback to popular villa areas
DUBAI_VILLA_NEIGHBORHOODS = [
    "Dubai Hills Estate",
    "Arabian Ranches",
    "Palm Jumeirah",
    "Emirates Hills",
    "The Villa",
    "Jumeirah Park",
    "Damac Lagoons",
    "Tilal Al Ghaf"
]

# Can expand with correct externalIDs when available
location_map = {
    "downtown dubai": "5002",
    "dubai marina": "5002",
    "mirdif": "5002",
    "arabian ranches": "5002",
    "dubai hills estate": "5002",
    "jumeirah": "5002",
    "palm jumeirah": "5002",
    "dubai": "5002",  # main fallback
}


def fetch_properties(location: str, purpose: str, budget: Optional[float] = None, property_type: Optional[str] = None) -> List[Dict]:
    """
    Search for properties in Dubai given a location, purpose ('rent' or 'sale'), optional budget, and optional property type.
    Returns a list of dicts, each with keys: type, purpose, price, location, size (sqm).
    """

    if not location or not purpose:
        return [{"error": "Missing required parameters: location and purpose"}]

    url = "https://bayut.p.rapidapi.com/properties/list"
    headers = {
        "x-rapidapi-host": "bayut.p.rapidapi.com",
        "x-rapidapi-key": os.getenv("RAPIDAPI_KEY")
    }

    loc_key = location.strip().lower()
    location_id = location_map.get(loc_key, "5002")

    params = {
        "locationExternalIDs": location_id,
        "purpose": f"for-{purpose}",
        "hitsPerPage": "20"
    }

    if budget is not None:
        try:
            params["maxPrice"] = int(budget)
        except ValueError:
            pass

    if property_type:
        category_id = PROPERTY_TYPE_IDS.get(property_type.strip().lower())
        if category_id:
            params["categoryExternalID"] = category_id

    # Make initial API request
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()
        listings = data.get("hits", [])
    except Exception as e:
        return [{"error": f"API request failed: {e}"}]

    # If no results and searching in generic "Dubai" — try popular villa areas
    if not listings and location.lower() == "dubai" and property_type and property_type.lower() == "villa":
        for area in DUBAI_VILLA_NEIGHBORHOODS:
            fallback_params = params.copy()
            fallback_params["locationExternalIDs"] = location_map.get(area.lower(), "5002")
            try:
                response = requests.get(url, headers=headers, params=fallback_params, timeout=10)
                data = response.json()
                listings = data.get("hits", [])
                if listings:
                    break
            except:
                continue

    results = []
    for item in listings:
        # extract type
        category = item.get("category", [])
        type_name = category[0].get("name", "property") if category else "property"

        # extract location name (last in location list)
        loc_list = item.get("location", [])
        loc_name = loc_list[-1].get("name", "") if loc_list else ""

        # area
        raw_area = item.get("area") or item.get("size")
        try:
            size_sqm = float(raw_area) if raw_area is not None else 0.0
        except:
            size_sqm = 0.0

        results.append({
            "type": type_name,
            "purpose": purpose,
            "price": item.get("price"),
            "location": loc_name,
            "size": size_sqm
        })

    if not results:
        return [{"message": "No properties found."}]
    return results
