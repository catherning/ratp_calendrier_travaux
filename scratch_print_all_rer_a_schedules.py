import asyncio
import os
import sys
import httpx
from urllib.parse import quote
from dotenv import load_dotenv

async def check_all_schedules():
    load_dotenv("/home/kaprime/Perso/ratp_calendrier_travaux/.env")
    api_key = os.getenv("NAVITIA_API_KEY", "")

    line_navitia_id = "C01742" # RER A
    full_id = f"line:IDFM:{line_navitia_id}"
    
    url = f"https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/lines/{quote(full_id, safe='')}/route_schedules"
    params = {
        "from_datetime": "20260724T080000",
        "items_per_schedule": "1"
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers={"apikey": api_key}, params=params)
        if resp.status_code == 200:
            data = resp.json()
            route_schedules = data.get("route_schedules", [])
            print(f"Found {len(route_schedules)} route schedules.")
            for idx, rs in enumerate(route_schedules):
                rows = rs.get("table", {}).get("rows", [])
                names = []
                for row in rows:
                    sp = row.get("stop_point", {})
                    names.append(sp.get("name", "").split("(")[0].strip())
                
                print(f"\nSchedule {idx+1} ({len(rows)} stations):")
                print(" -> ".join(names))
        else:
            print("Failed", resp.text)

if __name__ == "__main__":
    asyncio.run(check_all_schedules())
