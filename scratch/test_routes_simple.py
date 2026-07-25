import os
import httpx
from dotenv import load_dotenv

def test():
    load_dotenv()
    api_key = os.getenv("NAVITIA_API_KEY", "")
    
    # Metro 4
    url = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/lines/line:IDFM:C01374/routes?depth=2"
    r = httpx.get(url, headers={"apikey": api_key})
    print(f"Status Code: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        routes = data.get("routes", [])
        print(f"Found {len(routes)} routes")
        for idx, rt in enumerate(routes):
            stops = [sp.get("name") for sp in rt.get("stop_points", [])]
            print(f"\nRoute {idx+1}: {rt.get('name')} (id: {rt.get('id')})")
            print(f"  Stops ({len(stops)}): {stops}")

if __name__ == "__main__":
    test()
