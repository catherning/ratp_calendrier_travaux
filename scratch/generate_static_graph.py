"""Prepopulate the same validated persistent graphs used by the API."""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.domain.lines import LINE_REGISTRY
from src.services.navitia_client import refresh_line_stations


async def generate_static_graph(codes: list[str]) -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("NAVITIA_API_KEY")
    if not api_key:
        raise SystemExit("NAVITIA_API_KEY is required")
    async with httpx.AsyncClient() as client:
        for code in codes:
            graph = await refresh_line_stations(
                LINE_REGISTRY[code].navitia_id, api_key, client,
            )
            stations = graph["stations"]
            edges = sum(len(station["neighbors"]) for station in stations.values()) // 2
            print(f"Line {code}: {len(stations)} stations, {edges} links")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lines", nargs="*", help="Line codes; defaults to all registered lines")
    args = parser.parse_args()
    codes = args.lines or list(LINE_REGISTRY)
    unknown = set(codes) - LINE_REGISTRY.keys()
    if unknown:
        parser.error(f"Unknown lines: {sorted(unknown)}")
    logging.basicConfig(level=logging.INFO)
    asyncio.run(generate_static_graph(codes))
