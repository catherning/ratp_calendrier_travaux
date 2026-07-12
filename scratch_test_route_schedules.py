import asyncio
import os
import sys
import httpx
from urllib.parse import quote
from dotenv import load_dotenv

sys.path.append("/home/kaprime/Perso/ratp_calendrier_travaux")

async def test_route_schedules():
    load_dotenv("/home/kaprime/Perso/ratp_calendrier_travaux/.env")
    api_key = os.getenv("NAVITIA_API_KEY", "")

    line_navitia_id = "C01374" # Metro 4
    full_id = f"line:IDFM:{line_navitia_id}"
    
    # Query route_schedules
    url = f"https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/lines/{quote(full_id, safe='')}/route_schedules"
    params = {
        "from_datetime": "20260713T080000",
        "items_per_schedule": "5"
    }
    
    print(f"Requesting: {url} with params {params}")
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers={"apikey": api_key}, params=params)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            route_schedules = data.get("route_schedules", [])
            print(f"Found {len(route_schedules)} route schedules!")
            if route_schedules:
                rs = route_schedules[0]
                print(f"\nRoute Schedule 1:")
                print(f"  Route ID: {rs.get('route', {}).get('id')}")
                print(f"  Route Name: {rs.get('route', {}).get('name')}")
                
                # Check rows
                rows = rs.get("table", {}).get("rows", [])
                print(f"  Number of rows (stations in order): {len(rows)}")
                if rows:
                    print("  Stations in true sequential route order:")
                    for idx, row in enumerate(rows):
                        stop_point = row.get("stop_point", {})
                        print(f"    {idx+1}: {stop_point.get('name')} (id: {stop_point.get('id')}, lat/lon: {stop_point.get('coord', {}).get('lat')}, {stop_point.get('coord', {}).get('lon')})")
        else:
            print("Failed:")
            print(resp.text)

if __name__ == "__main__":
    asyncio.run(test_route_schedules())
