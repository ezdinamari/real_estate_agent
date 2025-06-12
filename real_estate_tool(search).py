# real_estate_tool.py
import os
import json
import requests
from google.adk.tools.mcp_tool.runtime import main, register_function

@register_function(
    name="search_properties",
    description="Search properties for rent or sale in Dubai using SerpAPI.",
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
    budget = args.get("budget", None)

    query = f"{purpose} apartment in {location} Dubai"
    params = {
        "q": query,
        "api_key": os.getenv("SERP_API_KEY"),
        "engine": "google_real_estate",
        "location": "Dubai",
        "hl": "en"
    }

    try:
        response = requests.get("https://serpapi.com/search", params=params)
        data = response.json()
    except Exception as e:
        return {"content": [f"Error fetching data from SerpAPI: {str(e)}"]}

    listings = data.get("real_estate_results", [])
    properties = []

    for r in listings:
        price_text = r.get("price", "")
        try:
            numeric_price = int("".join(filter(str.isdigit, price_text)))
        except:
            numeric_price = None

        if budget and numeric_price and numeric_price > budget:
            continue

        properties.append({
            "type": "apartment",
            "purpose": purpose,
            "price": price_text,
            "location": r.get("address", location),
            "size": r.get("size", "N/A")
        })

    if not properties:
        return {"content": ["No matching properties found. Try a different budget or location."]}

    return {"content": [json.dumps(p) for p in properties]}

if __name__ == "__main__":
    main()
