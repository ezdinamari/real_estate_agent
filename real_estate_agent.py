import re
import os
import asyncio
import json
import logging
from typing import Optional, Tuple, List, Dict

from dotenv import load_dotenv
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from real_estate_tool import fetch_properties  # direct import of the function

load_dotenv()
logging.basicConfig(level=logging.INFO)

# ---------------------
# 1. Neighborhood ↔ Top Schools mapping
NEIGHBORHOOD_SCHOOLS: Dict[str, List[str]] = {
    "arabian ranches": [
        "JESS (Jumeirah English Speaking School)",
        "Nord Anglia International School",
        "Ranches Primary School",
        "Ranches Nursery"
    ],
    "dubai hills estate": [
        "GEMS World Academy",
        "Safa Community School",
        "Kings' School Al Barsha",
        "GEMS Wellington Academy",
        "GEMS International School",
        "Brighton College Dubai",
        "Dubai Heights Academy",
        "GEMS New Millennium School"
    ],
    "mirdif": [
        "GEMS Royal Dubai School",
        "Dar Al Marefa",
        "Uptown International School"
    ],
    "jumeirah": [
        "Dubai International Academy",
        "Jumeirah College",
        "GEMS Jumeirah Primary School"
    ],
    "palm jumeirah": [
        "Dubai American Academy",
        "Swiss International Scientific School"
    ],
    "al furjan": [
        "Arbor School"
    ],
    "emirates hills": [
        "Dubai British School",
        "Emirates International School",
        "GEMS Wellington Academy"
    ],
}

# ---------------------
# 2. Extractors
def extract_neighborhood(query: str) -> Optional[str]:
    q = query.lower()
    for nb in NEIGHBORHOOD_SCHOOLS.keys():
        if nb in q:
            return nb
    return None

def extract_budget(query: str) -> Optional[float]:
    q = query.lower()
    m = re.search(r"under\s+([\d\.]+)\s*M(?:illion)?\s*AED", q, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1)) * 1_000_000
        except:
            pass
    m2 = re.search(r"under\s+([\d,]+)\s*AED", q, re.IGNORECASE)
    if m2:
        try:
            num = m2.group(1).replace(",", "")
            return float(num)
        except:
            pass
    return None

def extract_purpose(query: str) -> str:
    return "rent" if "rent" in query.lower() else "sale"

def extract_property_type(query: str) -> Optional[str]:
    q = query.lower()

    if "villa" in q or "villas" in q:
        return "villa"
    elif "apartment" in q or "flat" in q:
        return "apartment"
    elif "townhouse" in q:
        return "townhouse"
    elif "land" in q and "industrial" in q:
        return "industrial land"
    elif "land" in q and "mixed use" in q:
        return "mixed use land"
    elif "land" in q:
        return "land"
    elif "floor" in q:
        return "floor"
    elif "building" in q:
        return "building"
    elif "penthouse" in q:
        return "penthouse"
    elif "office" in q:
        return "office"
    elif "warehouse" in q:
        return "warehouse"
    elif "shop" in q:
        return "shop"
    elif "labour camp" in q:
        return "labour camp"
    elif "bulk unit" in q:
        return "bulk unit"
    elif "factory" in q:
        return "factory"
    elif "showroom" in q:
        return "showroom"
    elif "other commercial" in q:
        return "other commercial"
    return None

# ---------------------
# 3. Format result
def format_property(item: Dict, neighborhood: str) -> str:
    price = item.get("price")
    size_sqm = item.get("size", 0) or 0.0
    try:
        size_sqft = round(size_sqm * 10.7639, 2)
    except:
        size_sqft = None

    type_name = item.get("type", "Property")
    loc_name = item.get("location", neighborhood.title())
    url = item.get("url")

    price_str = "N/A" if price is None else f"{price:,.0f}"
    size_str = f"{size_sqft:,} sq.ft." if size_sqft else "N/A"
    url_str = f"\n    🔗 {url}" if url else ""

    return f"- 🏘️ {type_name} in {loc_name}: AED {price_str}, Size: {size_str}{url_str}"

# ---------------------
# 4. LLM summarization
async def summarize_listings(user_query: str, listings: List[Tuple[str, Dict]]) -> None:
    system_prompt = """
You are a real estate assistant. A user asked:
\"\"\"{}\"\"\"
Below is a JSON array of property listings (with neighborhood). Please:
- Summarize the key insights (e.g., price range, best deals).
- Mention neighborhood context and nearby schools.
- If no listings, suggest adjusting budget or neighborhood.
Respond in a friendly conversational style.
""".strip().format(user_query)

    simple_list = []
    for nb, prop in listings:
        entry = {
            "neighborhood": nb,
            "type": prop.get("type"),
            "location": prop.get("location"),
            "price": prop.get("price"),
            "size_sqm": prop.get("size"),
        }
        simple_list.append(entry)

    user_message = {
        "listings": simple_list,
        "schools": {nb: NEIGHBORHOOD_SCHOOLS.get(nb, []) for nb, _ in listings}
    }

    agent = LlmAgent(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-pro"),
        name="real_estate_summarizer",
        instruction=system_prompt,
        tools=[]
    )
    session_service = InMemorySessionService()
    session = await session_service.create_session(state={}, app_name='real_estate_summary', user_id='summarizer')
    runner = Runner(app_name='real_estate_summary', agent=agent, session_service=session_service)

    message_text = "Here are the listings data:\n" + json.dumps(user_message, indent=2)
    content = types.Content(role="user", parts=[types.Part(text=message_text)])
    print("\n🤖 Asking LLM to summarize results...")
    events = runner.run_async(session_id=session.id, user_id=session.user_id, new_message=content)
    async for event in events:
        if event.content and event.content.parts:
            part = event.content.parts[0]
            if part.text:
                print(part.text)

# ---------------------
# 5. Main agent entry
def run_real_estate_agent(user_query: str):
    neighborhood = extract_neighborhood(user_query)
    budget = extract_budget(user_query)
    purpose = extract_purpose(user_query)
    property_type = extract_property_type(user_query)

    if neighborhood:
        neighborhoods_to_search = [neighborhood]
        print(f"📍 Searching in specified neighborhood: {neighborhood.title()}")
    else:
        neighborhoods_to_search = list(NEIGHBORHOOD_SCHOOLS.keys())
        print("📍 No specific neighborhood mentioned; searching all family-friendly neighborhoods.")

    print(f"💰 Budget: {'None' if budget is None else f'Under {budget:,.0f} AED'}")
    print(f"🎯 Purpose: {purpose.title()}")
    print(f"🏗️ Property Type: {property_type or 'Any'}\n")

    all_results: List[Tuple[str, Dict]] = []
    for nb in neighborhoods_to_search:
        props = fetch_properties(location=nb, purpose=purpose, budget=budget, category=property_type)
        if isinstance(props, list) and props:
            for prop in props:
                all_results.append((nb, prop))

    if not all_results:
        print("😔 No properties found in any family-friendly area under those criteria.")
        print("You may try increasing budget or specifying a different neighborhood.")
        return

    def price_key(tup):
        prop = tup[1]
        p = prop.get("price")
        try:
            return float(p)
        except:
            return float('inf')

    all_results.sort(key=price_key)
    top_results = all_results[:20]
    print("🔍 Top listings gathered (preliminary):")
    for nb, prop in top_results:
        line = format_property(prop, nb)
        print(line)

    asyncio.run(summarize_listings(user_query, top_results))
