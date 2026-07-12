import asyncio
import os
import sys
import httpx
from urllib.parse import quote
from dotenv import load_dotenv

sys.path.append("/home/kaprime/Perso/ratp_calendrier_travaux")

async def test_rer_a():
    load_dotenv("/home/kaprime/Perso/ratp_calendrier_travaux/.env")
    api_key = os.getenv("NAVITIA_API_KEY", "")

    line_navitia_id = "C01742" # RER A
    full_id = f"line:IDFM:{line_navitia_id}"
    
    url = f"https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/lines/{quote(full_id, safe='')}/route_schedules"
    params = {
        "from_datetime": "20260713T080000",
        "items_per_schedule": "1"
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers={"apikey": api_key}, params=params)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            route_schedules = data.get("route_schedules", [])
            print(f"Found {len(route_schedules)} route schedules for RER A:")
            for idx, rs in enumerate(route_schedules[:8]):
                rows = rs.get("table", {}).get("rows", [])
                if rows:
                    first = rows[0].get("stop_point", {}).get("name")
                    last = rows[-1].get("stop_point", {}).get("name")
                    print(f"  Schedule {idx+1}: {len(rows)} stations, from '{first}' to '{last}'")
        else:
            print("Failed", resp.text)

if __name__ == "__main__":
    asyncio.run(test_rer_a())
