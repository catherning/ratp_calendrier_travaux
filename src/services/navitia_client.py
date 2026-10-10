"""
Async HTTP client for the Navitia / PRIM API.
Traffic responses are cached in-process. Station graphs are permanent files
and are only rebuilt by explicit administrative updates.
"""
import asyncio
import logging
import time
from urllib.parse import quote

import httpx

from src.domain.line_graph import LineGraph, LineGraphBuilder
from src.services.line_graph_cache import read_graph, write_graph

logger = logging.getLogger(__name__)

NAVITIA_BASE = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia"

# ── In-process TTL caches ──────────────────────────────────────────────────────
# Format: {key: (payload, expires_at_monotonic)}

_line_reports_cache: dict[str, tuple[dict, float]] = {}
_places_cache: dict[str, tuple[list, float]] = {}
_journeys_cache: dict[str, tuple[dict, float]] = {}
_line_stations_locks: dict[str, asyncio.Lock] = {}

LINE_REPORTS_TTL = 300.0   # 5 minutes
PLACES_TTL = 600.0         # 10 minutes
JOURNEYS_TTL = 300.0       # 5 minutes


def _cache_get(cache: dict, key: str) -> dict | list | None:
    entry = cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    return None


MAX_CACHE_SIZE = 512


def _cache_set(cache: dict, key: str, value, ttl: float) -> None:
    if len(cache) >= MAX_CACHE_SIZE:
        now = time.monotonic()
        expired_keys = [k for k, v in cache.items() if now >= v[1]]
        for k in expired_keys:
            cache.pop(k, None)
        while len(cache) >= MAX_CACHE_SIZE:
            first_key = next(iter(cache))
            cache.pop(first_key, None)
    cache[key] = (value, time.monotonic() + ttl)


# ── Public functions ───────────────────────────────────────────────────────────

async def _get_with_fallback(
    url: str,
    headers: dict,
    params: dict | None = None,
    timeout: float = 10.0,
    client: httpx.AsyncClient | None = None,
) -> httpx.Response:
    if client is not None:
        return await client.get(url, headers=headers, params=params, timeout=timeout)
    async with httpx.AsyncClient(timeout=timeout) as local_client:
        return await local_client.get(url, headers=headers, params=params)


async def fetch_line_reports(
    navitia_id: str,
    api_key: str,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """
    Fetch the line_reports payload for one line.
    navitia_id: short code like 'C01374' (without the 'line:IDFM:' prefix).
    Returns the raw JSON dict from Navitia.
    """
    cached = _cache_get(_line_reports_cache, navitia_id)
    if cached is not None:
        logger.debug("Cache hit: line_reports for %s", navitia_id)
        return cached  # type: ignore[return-value]

    full_id = f"line:IDFM:{navitia_id}"
    url = f"{NAVITIA_BASE}/line_reports/lines/{quote(full_id, safe='')}/line_reports"

    logger.info("Fetching line_reports for %s", navitia_id)
    resp = await _get_with_fallback(url, headers={"apikey": api_key}, timeout=12.0, client=client)
    resp.raise_for_status()
    data: dict = resp.json()

    _cache_set(_line_reports_cache, navitia_id, data, LINE_REPORTS_TTL)
    return data


async def fetch_places(
    q: str,
    api_key: str,
    count: int = 15,
    client: httpx.AsyncClient | None = None,
) -> list:
    """
    Search for stop areas matching the query string.
    Returns a list of Navitia 'place' objects.
    """
    cache_key = f"{q.strip().lower()}:{count}"
    cached = _cache_get(_places_cache, cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    url = f"{NAVITIA_BASE}/places"
    params = {
        "q": q,
        "type[]": "stop_area",
        "count": count,
        "disable_geojson": "true",
    }

    resp = await _get_with_fallback(url, headers={"apikey": api_key}, params=params, timeout=8.0, client=client)
    resp.raise_for_status()
    places: list = resp.json().get("places", [])

    _cache_set(_places_cache, cache_key, places, PLACES_TTL)
    return places


async def fetch_journeys(
    from_id: str,
    to_id: str,
    api_key: str,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """
    Fetch journeys between from_id and to_id.
    Returns the raw JSON dict from Navitia.
    """
    cache_key = f"{from_id}:{to_id}"
    cached = _cache_get(_journeys_cache, cache_key)
    if cached is not None:
        logger.debug("Cache hit: journeys from %s to %s", from_id, to_id)
        return cached  # type: ignore[return-value]

    url = f"{NAVITIA_BASE}/journeys"
    params = {
        "from": from_id,
        "to": to_id,
        "disable_geojson": "true",
    }

    logger.info("Fetching journeys from %s to %s", from_id, to_id)
    resp = await _get_with_fallback(url, headers={"apikey": api_key}, params=params, timeout=15.0, client=client)
    resp.raise_for_status()
    data: dict = resp.json()

    _cache_set(_journeys_cache, cache_key, data, JOURNEYS_TTL)
    return data


async def fetch_line_stations(
    navitia_id: str,
) -> LineGraph:
    """Read the permanent graph only. Never call Navitia on a public request."""
    entry = await asyncio.to_thread(read_graph, navitia_id)
    if entry is None:
        raise FileNotFoundError(f"No persisted station graph for {navitia_id}")
    return entry[0]


class GraphRefreshInProgress(RuntimeError):
    pass


async def refresh_line_stations(
    navitia_id: str,
    api_key: str,
    client: httpx.AsyncClient | None = None,
) -> LineGraph:
    """Replace the graph only after a complete build and successful disk write."""
    lock = _line_stations_locks.setdefault(navitia_id, asyncio.Lock())
    if lock.locked():
        raise GraphRefreshInProgress(f"Graph refresh already running for {navitia_id}")
    async with lock:
        graph = await _fetch_line_graph(navitia_id, api_key, client)
        await asyncio.to_thread(write_graph, navitia_id, graph, time.time())
        return graph


async def _fetch_line_graph(
    navitia_id: str, api_key: str, client: httpx.AsyncClient | None,
) -> LineGraph:
    full_id = quote(f"line:IDFM:{navitia_id}", safe="")
    url = f"{NAVITIA_BASE}/lines/{full_id}/vehicle_journeys"
    builder = LineGraphBuilder()
    received = 0
    total: int | None = None
    logger.info("Building base-schedule station graph for %s", navitia_id)
    # No since/until filter: include branches and short turns outside today's service.
    for page in range(1000):
        response = await _get_with_fallback(
            url, headers={"apikey": api_key},
            params={
                "count": 1000, "start_page": page, "depth": 2,
                "data_freshness": "base_schedule", "disable_geojson": "true",
            },
            timeout=60.0, client=client,
        )
        response.raise_for_status()
        data = response.json()
        journeys = data.get("vehicle_journeys", [])
        pagination = data.get("pagination", {})
        reported_total = pagination.get("total_result")
        if not isinstance(reported_total, int) or reported_total < 1:
            raise ValueError("Missing or empty vehicle_journeys pagination")
        if total is not None and total != reported_total:
            raise ValueError("Navitia dataset changed during graph pagination")
        total = reported_total
        if not journeys:
            raise ValueError("Incomplete vehicle_journeys pagination")
        for journey in journeys:
            if not journey.get("stop_times"):
                journey_id = journey.get("id")
                if not journey_id:
                    raise ValueError("Vehicle journey without stop_times or identity")
                detail = await _get_with_fallback(
                    f"{NAVITIA_BASE}/vehicle_journeys/{quote(journey_id, safe='')}",
                    headers={"apikey": api_key},
                    params={"depth": 2, "disable_geojson": "true", "data_freshness": "base_schedule"},
                    timeout=60.0, client=client,
                )
                detail.raise_for_status()
                matches = [
                    item for item in detail.json().get("vehicle_journeys", [])
                    if item.get("id") == journey_id
                ]
                if len(matches) != 1:
                    raise ValueError(f"Missing vehicle journey detail for {journey_id}")
                journey = matches[0]
                if not journey.get("stop_times"):
                    logger.warning(
                        "Ignoring empty vehicle journey %s for line %s: "
                        "no stop_times in collection or detail",
                        journey_id, navitia_id,
                    )
                    continue
                logger.info("Recovered stop_times from detail for %s", journey_id)
            builder.add_journey(journey)
        received += len(journeys)
        if received == total:
            graph = builder.build()
            logger.info(
                "Built station graph for %s: %d journeys, %d distinct paths, %d stations",
                navitia_id, received, len(builder.paths), len(graph["stations"]),
            )
            return graph
        if received > total:
            raise ValueError("Inconsistent vehicle_journeys pagination")
    raise ValueError("Too many vehicle_journeys pages; graph was not cached")
