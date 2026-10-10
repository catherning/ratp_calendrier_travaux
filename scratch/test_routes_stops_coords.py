import os
import httpx
from dotenv import load_dotenv
from urllib.parse import quote

def test():
    load_dotenv()
    api_key = os.getenv("NAVITIA_API_KEY", "")
    
    # Test for Metro 4 (C01374) and Metro 8 (C01378)
    for line_code, navitia_id in [("4", "C01374"), ("8", "C01378")]:
        full_id = f"line:IDFM:{navitia_id}"
        url_routes = f"https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/lines/{quote(full_id, safe='')}/routes"
        
        print(f"\n======================================")
        print(f"Fetching routes for Line {line_code} ({navitia_id})")
        r_routes = httpx.get(url_routes, headers={"apikey": api_key})
        print(f"Routes status: {r_routes.status_code}")
        
        if r_routes.status_code == 200:
            routes = r_routes.json().get("routes", [])
            print(f"Found {len(routes)} routes")
            
            # Take the first route with stop points if possible
            for idx, rt in enumerate(routes):
                route_id = rt.get("id")
                url_stops = f"https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/routes/{quote(route_id, safe='')}/stop_points"
                r_stops = httpx.get(url_stops, headers={"apikey": api_key})
                
                if r_stops.status_code == 200:
                    stops = r_stops.json().get("stop_points", [])
                    print(f"  Route {idx+1}: {rt.get('name')} -> {len(stops)} stops found")
                    if stops:
                        # Print first 3 and last 2 stops
                        print("    First stops:")
                        for sp in stops[:3]:
                            print(f"      - {sp.get('name')} ({sp.get('coord', {})})")
                        print("    Last stops:")
                        for sp in stops[-2:]:
                            print(f"      - {sp.get('name')} ({sp.get('coord', {})})")
                        break
                else:
                    print(f"  Route {idx+1} stops request failed with {r_stops.status_code}")

if __name__ == "__main__":
    test()
