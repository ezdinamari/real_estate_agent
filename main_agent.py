import asyncio
import os
import json
import re
import logging
import requests
from dotenv import load_dotenv
from google.genai import types
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import MCPTool, ToolFunction, ToolFunctionSpec

# Load environment variables from .env file
load_dotenv()

# Enable debug logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')



# --- Agent Initialization ---
async def get_agent_async():
    print("Initializing Real Estate Agent with tool...")
    tool = RealEstateSearchTool()

    root_agent = LlmAgent(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        name='real_estate_assistant',
        instruction='Help users search for apartments or houses for rent or sale in Dubai. Extract location, purpose, and budget if provided.',
        tools=[tool],
    )

    print("Agent and tool initialized successfully.")
    return root_agent


# --- Main Logic ---
async def async_main(user_query):
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        state={}, app_name='real_estate_app', user_id='user_real_estate'
    )

    # Basic query parsing (optional pre-structuring)
    match = re.search(r"Find\s+(apartment|house)s?\s+(for\s+(rent|sale))\s+in\s+([\w\s]+)(?:\s+under\s+(\d+\.?\d*)\s*M\s*AED)?", user_query, re.IGNORECASE)
    if match:
        property_type, purpose, location, budget = match.groups()[0], match.groups()[2], match.groups()[3], match.groups()[4]
        structured_query = f"Find {property_type}s for {purpose} in {location}" + (f" under {budget}M AED" if budget else "")
    else:
        structured_query = user_query

    print(f"User Query: '{structured_query}'")
    content = types.Content(role='user', parts=[types.Part(text=structured_query)])

    # Get agent with embedded tool
    root_agent = await get_agent_async()

    runner = Runner(
        app_name='real_estate_app',
        agent=root_agent,
        session_service=session_service,
    )

    print("Running agent...")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            events_async = runner.run_async(
                session_id=session.id,
                user_id=session.user_id,
                new_message=content
            )
            async for event in events_async:
                print(f"Event received: {event}")
                if event.content.parts and event.content.parts[0].function_response:
                    response = event.content.parts[0].function_response.response['result']['content']
                    print("Property Options:")
                    for item in response:
                        try:
                            data = json.loads(item.text.replace("'", "\""))
                            print(f"- Type: {data.get('type', 'N/A')}, Purpose: {data.get('purpose', 'N/A')}, "
                                  f"Price: {data.get('price', 'N/A')}, Location: {data.get('location', 'N/A')}, "
                                  f"Size: {data.get('size', 'N/A')} sq.ft.")
                        except Exception as e:
                            print(f"- Raw: {item.text}")
            break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                print("Retrying...")
            else:
                print("Max retries reached. Please try again later.")


# --- Entry Point ---
if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    if not os.getenv("SERP_API_KEY"):
        raise ValueError("SERP_API_KEY environment variable not set.")

    user_query = input("Enter your query: ")
    model_choice = input("Choose model (flash/pro): ")
    os.environ["GEMINI_MODEL"] = f"gemini-2.0-{model_choice}"

    asyncio.run(async_main(user_query))

