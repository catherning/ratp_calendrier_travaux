import asyncio
import os
import sys
import httpx
from dotenv import load_dotenv

sys.path.append("/home/kaprime/Perso/ratp_calendrier_travaux")

async def test_stop_points():
    load_dotenv("/home/kaprime/Perso/ratp_calendrier_travaux/.env")
    api_key = os.getenv("NAVITIA_API_KEY", "")
    print(f"API key: {api_key[:5]}...")

    line_navitia_id = "C01374" # Metro 4
    full_id = f"line:IDFM:{line_navitia_id}"
    url = f"https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/lines/{full_id}/stop_points"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers={"apikey": api_key})
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            stop_points = data.get("stop_points", [])
            print(f"Found {len(stop_points)} stop points.")
            if stop_points:
                sp = stop_points[0]
                print("\nSample Stop Point structure:")
                for k, v in sp.items():
                    if k in ["id", "name", "label", "coord", "stop_area"]:
                        print(f"  {k}: {v}")
        else:
            print(resp.text)

if __name__ == "__main__":
    asyncio.run(test_stop_points())
