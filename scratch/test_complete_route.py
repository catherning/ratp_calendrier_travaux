import os
import httpx
import datetime
from dotenv import load_dotenv

def test():
    load_dotenv()
    api_key = os.getenv("NAVITIA_API_KEY", "")
    now_str = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    
    url = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/lines/line:IDFM:C01374/route_schedules"
    params = {
        "from_datetime": now_str,
        "items_per_schedule": "25"
    }
    
    r = httpx.get(url, headers={"apikey": api_key}, params=params)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        route_schedules = r.json().get("route_schedules", [])
        print(f"Found {len(route_schedules)} route schedules")
        for idx, rs in enumerate(route_schedules):
            rows = rs.get("table", {}).get("rows", [])
            if rows:
                first = rows[0].get("stop_point", {}).get("name")
                last = rows[-1].get("stop_point", {}).get("name")
                print(f"  Schedule {idx+1}: {len(rows)} stations, from '{first}' to '{last}'")
                if len(rows) >= 28: # Metro 4 has 29 stations
                    print(f"    COMPLETE ROUTE DETECTED!")
                    print(f"    Stations: {[row.get('stop_point', {}).get('name') for row in rows]}")

if __name__ == "__main__":
    test()
