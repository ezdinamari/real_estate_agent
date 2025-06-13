import asyncio
import os
import logging
from dotenv import load_dotenv
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from real_estate_tool import fetch_properties_tool  # Import the tool

load_dotenv()
logging.basicConfig(level=logging.INFO)

async def get_agent_async():
    print("Initializing Real Estate Agent with tool...")

    agent = LlmAgent(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-pro"),
        name="real_estate_assistant",
        instruction="""You are a helpful real estate assistant focused on Dubai properties.
        You have access to a tool called `fetch_properties` that takes:
        - location (string)
        - purpose (string: "rent" or "sale")
        - budget (number, optional)
        Use this tool to help users search for apartments.""",
        tools=[fetch_properties_tool],  # Directly include the tool
    )

    print("Agent initialized successfully.")
    return agent

async def async_main(user_query):
    session_service = InMemorySessionService()
    session = await session_service.create_session(state={}, app_name='real_estate_app', user_id='user1')

    content = types.Content(role='user', parts=[types.Part(text=user_query)])
    agent = await get_agent_async()
    runner = Runner(app_name='real_estate_app', agent=agent, session_service=session_service)

    print("Running agent...")

    try:
        events = runner.run_async(
            session_id=session.id,
            user_id=session.user_id,
            new_message=content
        )
        async for event in events:
            if event.content and event.content.parts:
                part = event.content.parts[0]
                if part.function_call:
                    print(f"\n🔧 Calling tool: {part.function_call.name} with arguments {part.function_call.args}")
                elif part.function_response:
                    print("\n📦 Tool response:")
                    for item in part.function_response.response["result"]["content"]:
                        print(f"- {item.text}")
                else:
                    print("🤖", part.text)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        raise ValueError("Missing GOOGLE_API_KEY")
    if not os.getenv("RAPIDAPI_KEY"):
        raise ValueError("Missing RAPIDAPI_KEY")

    user_query = input("Enter your query: ")
    model_choice = input("Choose model (flash/pro): ").strip()
    os.environ["GEMINI_MODEL"] = f"gemini-2.0-{model_choice}"
    
    asyncio.run(async_main(user_query))
