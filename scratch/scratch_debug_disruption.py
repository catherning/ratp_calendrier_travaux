import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append("/home/kaprime/Perso/ratp_calendrier_travaux")

from src.services.navitia_client import fetch_line_reports
from src.domain.lines import LINE_REGISTRY
from src.domain.disruptions import _extract_stations, is_relevant_disruption

async def main():
    load_dotenv("/home/kaprime/Perso/ratp_calendrier_travaux/.env")
    api_key = os.getenv("NAVITIA_API_KEY", "")
    
    line_info = LINE_REGISTRY["A"]
    raw = await fetch_line_reports(line_info.navitia_id, api_key)
    
    print(f"Total disruptions fetched for RER A: {len(raw.get('disruptions', []))}")
    for idx, d in enumerate(raw.get('disruptions', [])):
        if not is_relevant_disruption(d):
            continue
        summary = d.get("severity", {}).get("name", "Unknown summary")
        # Try to get messages
        msg_text = ""
        for m in d.get("messages", []):
            if m.get("channel", {}).get("name") == "title":
                msg_text = m.get("text", "")
        if not msg_text and d.get("messages"):
            msg_text = d["messages"][0].get("text", "")
            
        stations = _extract_stations(d)
        print(f"\nDisruption {idx}:")
        print(f"  Summary: {summary}")
        print(f"  Message text: {msg_text[:120]}")
        print(f"  Extracted stations: '{stations}'")
        print(f"  Impacted Objects Count: {len(d.get('impacted_objects', []))}")
        
        # Print first few impacted objects
        for o_idx, obj in enumerate(d.get('impacted_objects', [])[:5]):
            pt = obj.get("pt_object", {})
            sec = obj.get("impacted_section", {})
            print(f"    Obj {o_idx}:")
            if pt:
                print(f"      pt_object: {pt.get('id')} | {pt.get('name')}")
            if sec:
                print(f"      section: from={sec.get('from', {}).get('name')} to={sec.get('to', {}).get('name')}")

if __name__ == "__main__":
    asyncio.run(main())
