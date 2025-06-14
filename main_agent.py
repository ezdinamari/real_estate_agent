# main_agent.py

import os
from dotenv import load_dotenv
from real_estate_agent import run_real_estate_agent

load_dotenv()

if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        raise ValueError("Missing GOOGLE_API_KEY")
    if not os.getenv("RAPIDAPI_KEY"):
        raise ValueError("Missing RAPIDAPI_KEY")

    user_query = input("Enter your query: ")
    model_choice = input("Choose model (flash/pro): ").strip().lower()
    os.environ["GEMINI_MODEL"] = f"gemini-2.0-{model_choice}"

    run_real_estate_agent(user_query)

