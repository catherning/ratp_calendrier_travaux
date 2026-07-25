import os
import sys
import httpx
import json
import datetime
from urllib.parse import quote
from dotenv import load_dotenv

# Add workspace to path to import domain lines
sys.path.append("/home/kaprime/Perso/ratp_calendrier_travaux")
from src.domain.lines import LINE_REGISTRY

async def generate_static_tracks():
    load_dotenv()
    api_key = os.getenv("NAVITIA_API_KEY", "")
    if not api_key:
        print("ERROR: NAVITIA_API_KEY not found in .env")
        return

    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)

    now_str = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    static_db = {}

    async with httpx.AsyncClient() as client:
        for code, line_info in LINE_REGISTRY.items():
            print(f"\nProcessing Line {code} ({line_info.name}) - Navitia ID: {line_info.navitia_id}...")
            full_id = f"line:IDFM:{line_info.navitia_id}"
            url = f"https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/lines/{quote(full_id, safe='')}/route_schedules"
            
            params = {
                "from_datetime": now_str,
                "items_per_schedule": "40" # Request plenty of schedules to cover all terminus runs and branches
            }
            
            try:
                resp = await client.get(url, headers={"apikey": api_key}, params=params, timeout=15.0)
                if resp.status_code != 200:
                    print(f"  [ERROR] Failed to fetch {code}: status {resp.status_code}")
                    continue
                
                data = resp.json()
                route_schedules = data.get("route_schedules", [])
                print(f"  Found {len(route_schedules)} route schedules.")
                
                # Extract all raw route sequences
                raw_routes = []
                unique_stations_map = {}
                
                for rs in route_schedules:
                    rows = rs.get("table", {}).get("rows", [])
                    if not rows:
                        continue
                    
                    route_path = []
                    for row in rows:
                        sp = row.get("stop_point", {})
                        name = sp.get("name", "").split("(")[0].strip()
                        stop_area_id = sp.get("stop_area", {}).get("id") or sp.get("id")
                        
                        coord = sp.get("coord")
                        if not coord or "lat" not in coord or "lon" not in coord:
                            continue
                        
                        try:
                            lat = float(coord["lat"])
                            lon = float(coord["lon"])
                        except ValueError:
                            continue
                            
                        station_info = {
                            "id": stop_area_id,
                            "name": name,
                            "lat": lat,
                            "lon": lon
                        }
                        route_path.append(station_info)
                        
                        # Accumulate in unique flat stations
                        if name not in unique_stations_map:
                            unique_stations_map[name] = station_info
                    
                    if len(route_path) > 1:
                        raw_routes.append(route_path)
                
                if not raw_routes:
                    print(f"  [WARNING] No routes extracted for line {code}")
                    continue
                
                # Deduplicate and keep only "maximal" routes (i.e., remove any route that is a subset of another route)
                # This keeps main tracks and avoids drawing short-turn lines
                maximal_routes = []
                # Sort by route length descending
                raw_routes.sort(key=len, reverse=True)
                
                for route in raw_routes:
                    # Check if this route is already a subset of any route we kept
                    is_subset = False
                    route_station_ids = [s["id"] for s in route]
                    
                    for kept in maximal_routes:
                        kept_station_ids = [s["id"] for s in kept]
                        # Check if route_station_ids is a sublist of kept_station_ids
                        # We do a simple sublist check
                        for i in range(len(kept_station_ids) - len(route_station_ids) + 1):
                            if kept_station_ids[i:i+len(route_station_ids)] == route_station_ids:
                                is_subset = True
                                break
                        if is_subset:
                            break
                    
                    if not is_subset:
                        maximal_routes.append(route)
                
                print(f"  Merged down to {len(maximal_routes)} maximal physical route tracks.")
                for idx, r in enumerate(maximal_routes):
                    print(f"    Track {idx+1}: {len(r)} stations, from '{r[0]['name']}' to '{r[-1]['name']}'")
                
                static_db[code] = {
                    "stations": list(unique_stations_map.values()),
                    "routes": maximal_routes
                }
                
            except Exception as e:
                print(f"  [ERROR] Exception processing line {code}: {e}")
                
        # Write to static JSON file
        output_file = "data/static_lines_routes.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(static_db, f, indent=2, ensure_ascii=False)
            
        print(f"\n======================================")
        print(f"SUCCESS! Static tracks database generated and saved to {output_file}")
        print(f"Total lines saved: {len(static_db)} / {len(LINE_REGISTRY)}")
        print(f"======================================")

if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_static_tracks())
