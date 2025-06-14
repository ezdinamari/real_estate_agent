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
    "warehouse": "8",
    "labour camp": "12",
    "bulk unit": "18",
    "floor": "21",
    "building": "14",
    "factory": "11",
    "industrial land": "22",
    "mixed use land": "23",
    "showroom": "10",
    "land": "9",  # general land
    "other commercial": "24"  # optional catch-all
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


def fetch_properties(location: str, purpose: str, budget: Optional[float] = None, category: Optional[str] = None) -> List[Dict]:
    """
    Search for properties in Dubai given a location, purpose ('rent' or 'sale'), and optional budget in AED.
    Returns a list of dicts, each with keys: type, purpose, price, location, size (area in sqm), url.
    """
    if not location or not purpose:
        return [{"error": "Missing required parameters: location and purpose"}]

    url = "https://bayut.p.rapidapi.com/properties/list"
    headers = {
        "x-rapidapi-host": "bayut.p.rapidapi.com",
        "x-rapidapi-key": os.getenv("RAPIDAPI_KEY")
    }

    loc_key = location.strip().lower()
    location_id = location_map.get(loc_key, "5002")  # default to Dubai

    params = {
        "locationExternalIDs": location_id,
        "purpose": f"for-{purpose}",
        "hitsPerPage": "20",
    }

    if category:
        cat_id = PROPERTY_TYPE_IDS.get(category.lower())
        if cat_id:
            params["categoryExternalID"] = cat_id

    if budget is not None:
        try:
            params["maxPrice"] = int(budget)
        except Exception:
            pass  # Ignore invalid budget input

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
        listings = data.get("hits", [])
    except Exception as e:
        return [{"error": f"API request failed: {e}"}]

    results = []
    for item in listings:
        category = item.get("category", [])
        type_name = category[0].get("name", "property") if category else "property"

        loc_list = item.get("location", [])
        loc_name = loc_list[-1].get("name", "") if loc_list else ""

        raw_area = item.get("area") or item.get("size") or 0
        try:
            size_sqm = float(raw_area)
        except:
            size_sqm = 0.0

        cover = item.get("coverPhoto", {}).get("url", "")

        external_id = item.get("externalID")
        bayut_url = f"https://www.bayut.com/property/details-{external_id}.html" if external_id else ""

        results.append({
            "type": type_name,
            "purpose": purpose,
            "price": item.get("price"),
            "location": loc_name,
            "size": size_sqm,
            "url": bayut_url
        })

    if not results:
        return [{"message": "No properties found."}]
    return results
