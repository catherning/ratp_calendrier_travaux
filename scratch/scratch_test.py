import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append("/home/kaprime/Perso/ratp_calendrier_travaux")

from src.services.navitia_client import fetch_line_reports

async def main():
    load_dotenv("/home/kaprime/Perso/ratp_calendrier_travaux/.env")
    api_key = os.getenv("NAVITIA_API_KEY", "")
    print(f"API key: {api_key[:5]}...")
    
    # RER A (C01374)
    data = await fetch_line_reports("C01374", api_key)
    disruptions = data.get("disruptions", [])
    print(f"Fetched {len(disruptions)} disruptions.")
    
    if disruptions:
        d = disruptions[0]
        print("\n--- SAMPLE DISRUPTION KEY FIELDS ---")
        for key in ["id", "status", "cause", "severity", "category", "tags", "exact_match", "title"]:
            print(f"{key}: {d.get(key)}")
        
        print("\n--- SEVERITY ---")
        print(d.get("severity"))
        
        print("\n--- MESSAGES ---")
        for m in d.get("messages", []):
            print(f"channel: {m.get('channel', {}).get('name')} | text: {m.get('text')}")
            
        print("\n--- PROPERTIES ---")
        print(d.get("properties"))
        
        print("\n--- IMPACTED OBJECTS ---")
        print(d.get("impacted_objects")[:2] if d.get("impacted_objects") else "None")

if __name__ == "__main__":
    asyncio.run(main())
