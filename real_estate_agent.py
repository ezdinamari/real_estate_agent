# real_estate_agent.py

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
# 1. Neighborhood ↔ Top Schools mapping (expand as needed):
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
    # Add more neighborhoods and schools as you find them...
}

# ---------------------
# 2. Extract neighborhood & budget & purpose from user query:
def extract_neighborhood(query: str) -> Optional[str]:
    """Return the first matching neighborhood key (lowercase) if found, else None."""
    q = query.lower()
    for nb in NEIGHBORHOOD_SCHOOLS.keys():
        if nb in q:
            return nb
    return None

def extract_budget(query: str) -> Optional[float]:
    """
    Extract budget from patterns like 'under 5M AED' or 'under 5000000 AED'.
    Returns budget in AED (float), or None.
    """
    q = query.lower()
    # Look for "under X M AED" or "under X million AED"
    m = re.search(r"under\s+([\d\.]+)\s*M(?:illion)?\s*AED", q, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1)) * 1_000_000
        except:
            pass
    # Alternatively plain number:
    m2 = re.search(r"under\s+([\d,]+)\s*AED", q, re.IGNORECASE)
    if m2:
        try:
            # Remove commas
            num = m2.group(1).replace(",", "")
            return float(num)
        except:
            pass
    return None

def extract_purpose(query: str) -> str:
    """Return 'rent' if the query mentions rent, else 'sale'."""
    q = query.lower()
    if "rent" in q:
        return "rent"
    else:
        return "sale"

# ---------------------
# 3. Format results & convert sizes
def format_property(item: Dict, neighborhood: str) -> str:
    """
    Given a single property dict from fetch_properties,
    format a human-friendly line, converting size (sqm → sqft).
    """
    price = item.get("price")
    size_sqm = item.get("size", 0) or 0.0
    try:
        size_sqft = round(size_sqm * 10.7639, 2)
    except:
        size_sqft = None

    type_name = item.get("type", "Property")
    loc_name = item.get("location", neighborhood.title())
    if price is None:
        price_str = "N/A"
    else:
        price_str = f"{price:,.0f}"
    size_str = f"{size_sqft:,} sq.m." if size_sqft else "N/A"

    return f"- 🏘️ {type_name} in {loc_name}: AED {price_str}, Size: {size_str}"

# ---------------------
# 4. Summarization with LLM
async def summarize_listings(user_query: str, listings: List[Tuple[str, Dict]]) -> None:
    """
    Use an LLM to produce a friendly summary/recommendation based on gathered listings.
    `listings`: List of tuples (neighborhood_key, property_dict).
    This function creates a temporary LlmAgent to ask Gemini to summarize.
    """
    # Prepare a system prompt for summarization:
    system_prompt = """
You are a real estate assistant. A user asked:
\"\"\"{}\"\"\"
Below is a JSON array of property listings (with neighborhood). Please:
- Summarize the key insights (e.g., price range, best deals).
- Mention neighborhood context and nearby schools.
- If no listings, suggest adjusting budget or neighborhood.
Respond in a friendly conversational style.
""".strip().format(user_query)

    # Prepare the JSON data to send as user message:
    # Build a list of simplified dicts for clarity:
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
    # Send as a JSON string in the prompt:
    user_message = {
        "listings": simple_list,
        # Also include school info per neighborhood
        "schools": {nb: NEIGHBORHOOD_SCHOOLS.get(nb, []) for nb, _ in listings}
    }
    # Create an agent for summarization
    agent = LlmAgent(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-pro"),
        name="real_estate_summarizer",
        instruction=system_prompt,
        tools=[]  # no tools needed for summarization step
    )
    # Run the agent with the JSON as text. We can embed JSON in the content.
    session_service = InMemorySessionService()
    session = await session_service.create_session(state={}, app_name='real_estate_summary', user_id='summarizer')
    runner = Runner(app_name='real_estate_summary', agent=agent, session_service=session_service)

    # Compose the message: we embed the JSON as part of the user text.
    message_text = "Here are the listings data:\n" + json.dumps(user_message, indent=2)
    content = types.Content(role="user", parts=[types.Part(text=message_text)])
    print("\n🤖 Asking LLM to summarize results...")
    events = runner.run_async(session_id=session.id, user_id=session.user_id, new_message=content)
    async for event in events:
        if event.content and event.content.parts:
            part = event.content.parts[0]
            # Usually summarization returns plain text
            if part.text:
                print(part.text)

# ---------------------
# 5. Main orchestration entrypoint
def run_real_estate_agent(user_query: str):
    """
    Entry point: parses query, fetches properties (one or many neighborhoods),
    then summarizes with LLM.
    """
    neighborhood = extract_neighborhood(user_query)
    budget = extract_budget(user_query)
    purpose = extract_purpose(user_query)

    # Determine neighborhoods to search
    if neighborhood:
        neighborhoods_to_search = [neighborhood]
        print(f"📍 Searching in specified neighborhood: {neighborhood.title()}")
    else:
        neighborhoods_to_search = list(NEIGHBORHOOD_SCHOOLS.keys())
        print("📍 No specific neighborhood mentioned; searching all family-friendly neighborhoods.")

    print(f"💰 Budget: {'None' if budget is None else f'Under {budget:,.0f} AED'}")
    print(f"🎯 Purpose: {purpose.title()}\n")

    # Collect listings
    all_results: List[Tuple[str, Dict]] = []
    for nb in neighborhoods_to_search:
        props = fetch_properties(location=nb, purpose=purpose, budget=budget)
        if isinstance(props, list) and props:
            # If the fetch_properties returns e.g. [{"error": "..."}], still include for summarization
            for prop in props:
                all_results.append((nb, prop))

    # If none found at all:
    if not all_results:
        print("😔 No properties found in any family-friendly area under those criteria.")
        print("You may try increasing budget or specifying a different neighborhood.")
        return

    # Sort by price ascending if price available
    def price_key(tup):
        prop = tup[1]
        p = prop.get("price")
        try:
            return float(p)
        except:
            return float('inf')
    all_results.sort(key=price_key)

    # Limit to top N for summarization (e.g., top 20)
    top_results = all_results[:20]
    # Print a brief listing summary before LLM summarization
    print("🔍 Top listings gathered (preliminary):")
    for nb, prop in top_results:
        line = format_property(prop, nb)
        print(line)

    # Now call summarization asynchronously
    # Since run_real_estate_agent is sync, we need to run the async summarization
    asyncio.run(summarize_listings(user_query, top_results))
