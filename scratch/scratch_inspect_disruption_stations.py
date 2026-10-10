import asyncio
import os
import sys
import httpx
from urllib.parse import quote
from dotenv import load_dotenv

async def inspect():
    load_dotenv("/home/kaprime/Perso/ratp_calendrier_travaux/.env")
    api_key = os.getenv("NAVITIA_API_KEY", "")

    # Lines to check: Line 8 (C01378) and RER A (C01742)
    async with httpx.AsyncClient() as client:
        # We can call our local FastAPI endpoint! It's running on port 8000!
        url = "http://127.0.0.1:8000/disruptions?lines=8,A"
        resp = await client.get(url)
        if resp.status_code == 200:
            disruptions = resp.json()
            print(f"Total disruptions fetched: {len(disruptions)}")
            for idx, d in enumerate(disruptions):
                print(f"\n--- Disruption {idx+1} (Line {d.get('line_code')}) ---")
                print(f"Summary: {d.get('summary')}")
                print(f"Stations in payload: {d.get('stations')}")
                print(f"Text description: {d.get('text')}")
        else:
            print("Failed to call local /disruptions", resp.text)

if __name__ == "__main__":
    asyncio.run(inspect())
