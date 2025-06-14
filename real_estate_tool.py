# real_estate_tool.py

import os
import requests
from google.adk.tools import FunctionTool
from typing import Optional
def fetch_properties(location: str, purpose: str, budget: Optional[float] = None):
    """Search for properties in Dubai given location, purpose ('rent' or 'sale'), and optional budget in AED."""
    if not location or not purpose:
        return [{"error": "Missing required parameters: location and purpose"}]

    url = "https://bayut.p.rapidapi.com/properties/list"
    headers = {
        "x-rapidapi-host": "bayut.p.rapidapi.com",
        "x-rapidapi-key": os.getenv("RAPIDAPI_KEY")
    }

    location_map = {
        "downtown dubai": "5002",
        "dubai": "5002"
    }

    location_id = location_map.get(location.lower(), "5002")

    params = {
        "locationExternalIDs": location_id,
        "purpose": f"for-{purpose}",
        #"hitsPerPage": "10",
    }

    if budget:
        try:
            if isinstance(budget, str):
                budget_value = float(budget.replace(",", ""))
            else:
                budget_value = float(budget)
            params["maxPrice"] = int(budget_value)
        except Exception as e:
            return [{"error": f"Invalid budget value: {budget} → {e}"}]

    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        listings = data.get("hits", [])

        results = []
        for item in listings:
            results.append({
                "type": item.get("category", [{}])[0].get("name", "property"),
                "purpose": purpose,
                "price": item.get("price"),
                "location": item.get("location", [{}])[-1].get("name", ""),
                "size": item.get("area")
            })

        return results if results else [{"message": "No properties found."}]
    except Exception as e:
        return [{"error": f"API request failed: {str(e)}"}]

# Expose the function as a tool
fetch_properties_tool = FunctionTool(fetch_properties)
