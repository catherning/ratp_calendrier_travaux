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
from src.services.line_graph_cache import read_graph


async def generate_static_graph(codes: list[str], missing_only: bool = False) -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("NAVITIA_API_KEY")
    if not api_key:
        raise SystemExit("NAVITIA_API_KEY is required")
    failures: list[str] = []
    async with httpx.AsyncClient() as client:
        for code in codes:
            navitia_id = LINE_REGISTRY[code].navitia_id
            if missing_only and read_graph(navitia_id) is not None:
                print(f"Line {code}: already persisted, skipping", flush=True)
                continue
            print(f"Line {code}: generating...", flush=True)
            try:
                graph = await refresh_line_stations(navitia_id, api_key, client)
            except (httpx.HTTPError, ValueError, OSError) as exc:
                logging.error("Line %s: generation failed (%s): %s", code, type(exc).__name__, exc)
                failures.append(code)
                continue
            stations = graph["stations"]
            edges = sum(len(station["neighbors"]) for station in stations.values()) // 2
            print(f"Line {code}: {len(stations)} stations, {edges} links", flush=True)
    if failures:
        raise SystemExit(f"Generation failed for lines: {', '.join(failures)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lines", nargs="*", help="Line codes; defaults to all registered lines")
    parser.add_argument("--missing-only", action="store_true", help="Preserve existing valid graph files")
    args = parser.parse_args()
    codes = args.lines or list(LINE_REGISTRY)
    unknown = set(codes) - LINE_REGISTRY.keys()
    if unknown:
        parser.error(f"Unknown lines: {sorted(unknown)}")
    logging.basicConfig(level=logging.INFO)
    asyncio.run(generate_static_graph(codes, missing_only=args.missing_only))
