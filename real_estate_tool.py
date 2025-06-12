# real_estate_tool.py
import os
import json
import requests
from google.adk.tools.mcp_tool.runtime import main, register_function

@register_function(
    name="search_properties",
    description="Search properties for rent or sale in Dubai using Bayut via RapidAPI.",
    parameters={
        "type": "object",
        "properties": {
            "location": {"type": "string"},
            "purpose": {"type": "string", "enum": ["rent", "sale"]},
            "budget": {"type": "number"}
        },
        "required": ["location", "purpose"]
    }
)
def search_properties(args):
    location = args["location"]
    purpose = args["purpose"]
    budget = args.get("budget")

    url = "https://bayut.p.rapidapi.com/properties/list"
    headers = {
        "x-rapidapi-host": "bayut.p.rapidapi.com",
        "x-rapidapi-key": os.getenv("RAPIDAPI_KEY")
    }
    params = {
        "locationExternalIDs": "5002",                 # e.g. Dubai
        "purpose": f"for-{purpose}",
        "maxPrice": int(budget * 1_000_000) if budget else None,
        "hitsPerPage": "10"
    }

    resp = requests.get(url, headers=headers, params=params)
    data = resp.json()
    hits = data.get("hits", [])

    properties = []
    for r in hits:
        properties.append({
            "type": r.get("category", {}).get("label", "property"),
            "purpose": purpose,
            "price": r.get("price"),
            "location": r.get("location", [{}])[-1].get("name"),
            "size": r.get("area")
        })

    if not properties:
        return {"content": ["No listings found from Bayut."]}

    return {"content": [json.dumps(p) for p in properties]}

if __name__ == "__main__":
    main()
