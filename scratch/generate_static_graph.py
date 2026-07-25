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

async def generate_static_graph():
    load_dotenv()
    api_key = os.getenv("NAVITIA_API_KEY", "")
    if not api_key:
        print("ERROR: NAVITIA_API_KEY not found in .env")
        return

    os.makedirs("data", exist_ok=True)
    now_str = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    static_graph = {}

    async with httpx.AsyncClient() as client:
        for code, line_info in LINE_REGISTRY.items():
            print(f"Processing Line {code} ({line_info.name}) - Navitia ID: {line_info.navitia_id}...")
            full_id = f"line:IDFM:{line_info.navitia_id}"
            url = f"https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/lines/{quote(full_id, safe='')}/route_schedules"
            
            params = {
                "from_datetime": now_str,
                "items_per_schedule": "40"
            }
            
            try:
                resp = await client.get(url, headers={"apikey": api_key}, params=params, timeout=15.0)
                if resp.status_code != 200:
                    print(f"  [ERROR] Failed to fetch {code}: status {resp.status_code}")
                    continue
                
                data = resp.json()
                route_schedules = data.get("route_schedules", [])
                
                stations_db = {}
                
                for rs in route_schedules:
                    rows = rs.get("table", {}).get("rows", [])
                    path_ids = []
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
                        
                        if stop_area_id not in stations_db:
                            stations_db[stop_area_id] = {
                                "name": name,
                                "lat": lat,
                                "lon": lon,
                                "neighbors": set()
                            }
                        path_ids.append(stop_area_id)
                    
                    # Link consecutive stations
                    for i in range(len(path_ids) - 1):
                        id_a = path_ids[i]
                        id_b = path_ids[i+1]
                        stations_db[id_a]["neighbors"].add(id_b)
                        stations_db[id_b]["neighbors"].add(id_a)
                
                # Convert neighbors set to sorted list for JSON serialization
                serializable_stations = {}
                for st_id, info in stations_db.items():
                    serializable_stations[st_id] = {
                        "name": info["name"],
                        "lat": info["lat"],
                        "lon": info["lon"],
                        "neighbors": sorted(list(info["neighbors"]))
                    }
                
                static_graph[code] = {
                    "stations": serializable_stations
                }
                print(f"  Generated graph with {len(serializable_stations)} stations.")
                
            except Exception as e:
                print(f"  [ERROR] Exception processing line {code}: {e}")

        # Save to file
        output_file = "data/static_lines_graph.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(static_graph, f, indent=2, ensure_ascii=False)
            
        print(f"\n======================================")
        print(f"SUCCESS! Topological graph database generated and saved to {output_file}")
        print(f"Total lines saved: {len(static_graph)} / {len(LINE_REGISTRY)}")
        print(f"======================================")

if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_static_graph())
