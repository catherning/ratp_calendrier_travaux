import asyncio
import os
import sys
from fastapi.testclient import TestClient

sys.path.append("/home/kaprime/Perso/ratp_calendrier_travaux")

from src.main import app

def test_endpoint():
    # TestClient calls the lifespan events (which sets app.state.client)
    with TestClient(app) as client:
        # Query stations for Line 4 and RER A
        response = client.get("/lines/stations?lines=4,A")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("\nKeys returned (should be '4' and 'A'):")
            print(list(data.keys()))
            
            for code in ["4", "A"]:
                line_data = data.get(code, {})
                stations = line_data.get("stations", [])
                routes = line_data.get("routes", [])
                print(f"\nLine {code}: found {len(stations)} unique stations, and {len(routes)} routes.")
                if stations:
                    print(f"Sample station on Line {code}:")
                    print(f"  ID: {stations[0]['id']}")
                    print(f"  Name: {stations[0]['name']}")
                    print(f"  Lat/Lon: {stations[0]['lat']}, {stations[0]['lon']}")
                if routes:
                    print(f"Sample Route 1 on Line {code} has {len(routes[0])} stations.")
                    print(f"  Path: " + " -> ".join([s['name'] for s in routes[0][:3]]) + " ... " + " -> ".join([s['name'] for s in routes[0][-2:]]))
        else:
            print("Error details:")
            print(response.text)

if __name__ == "__main__":
    test_endpoint()
