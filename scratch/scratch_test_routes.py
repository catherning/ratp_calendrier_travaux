import asyncio
import os
import sys
import httpx
from urllib.parse import quote
from dotenv import load_dotenv

sys.path.append("/home/kaprime/Perso/ratp_calendrier_travaux")

async def test_routes():
    load_dotenv("/home/kaprime/Perso/ratp_calendrier_travaux/.env")
    api_key = os.getenv("NAVITIA_API_KEY", "")

    line_navitia_id = "C01374" # Metro 4
    full_id = f"line:IDFM:{line_navitia_id}"
    
    async with httpx.AsyncClient() as client:
        # Test 1: Query routes with depth=2
        url_depth = f"https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/lines/{full_id}/routes?depth=2"
        print(f"\n--- Testing Route 1: {url_depth} ---")
        resp = await client.get(url_depth, headers={"apikey": api_key})
        if resp.status_code == 200:
            data = resp.json()
            routes = data.get("routes", [])
            print(f"Found {len(routes)} routes")
            for idx, r in enumerate(routes[:2]):
                stop_points = r.get("stop_points", [])
                print(f"Route {idx+1} ({r.get('name')}): nested stop points count = {len(stop_points)}")
                if stop_points:
                    print("SUCCESS! depth=2 worked.")
                    for j, sp in enumerate(stop_points[:5]):
                        print(f"  {j+1}: {sp.get('name')}")
        else:
            print(f"Failed with {resp.status_code}")

        # Test 2: Query /routes/{route_id}/stop_points
        url_list = f"https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/lines/{full_id}/routes"
        resp = await client.get(url_list, headers={"apikey": api_key})
        if resp.status_code == 200:
            routes = resp.json().get("routes", [])
            if routes:
                route_id = routes[0].get("id")
                encoded_route_id = quote(route_id, safe="")
                # Try routes/{route_id}/stop_points
                url_sub = f"https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/routes/{encoded_route_id}/stop_points"
                print(f"\n--- Testing Route 2: {url_sub} ---")
                resp_sub = await client.get(url_sub, headers={"apikey": api_key})
                print(f"Status Code: {resp_sub.status_code}")
                if resp_sub.status_code == 200:
                    data_sub = resp_sub.json()
                    stop_points = data_sub.get("stop_points", [])
                    print(f"Found {len(stop_points)} ordered stop points for route {route_id}!")
                    for j, sp in enumerate(stop_points[:10]):
                        print(f"  {j+1}: {sp.get('name')} (id: {sp.get('id')})")
                else:
                    print(resp_sub.text)

if __name__ == "__main__":
    asyncio.run(test_routes())
