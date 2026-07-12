"""
Async HTTP client for the Navitia / PRIM API.
All responses are cached in-process with a TTL to avoid hammering the API.
"""
import logging
import time
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

NAVITIA_BASE = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia"

# ── In-process TTL caches ──────────────────────────────────────────────────────
# Format: {key: (payload, expires_at_monotonic)}

_line_reports_cache: dict[str, tuple[dict, float]] = {}
_places_cache: dict[str, tuple[list, float]] = {}
_journeys_cache: dict[str, tuple[dict, float]] = {}
_line_stations_cache: dict[str, tuple[list, float]] = {}

LINE_REPORTS_TTL = 300.0   # 5 minutes
PLACES_TTL = 600.0         # 10 minutes
JOURNEYS_TTL = 300.0       # 5 minutes
LINE_STATIONS_TTL = 86400.0 # 24 hours (station lists are static)


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
    api_key: str,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """
    Fetch the stations and ordered routes for a line using route_schedules.
    navitia_id: short code like 'C01374'.
    Returns a dict with 'stations' (unique flat list) and 'routes' (ordered routes).
    """
    cached = _cache_get(_line_stations_cache, navitia_id)
    if cached is not None:
        logger.debug("Cache hit: line_stations for %s", navitia_id)
        return cached  # type: ignore[return-value]

    full_id = f"line:IDFM:{navitia_id}"
    url = f"{NAVITIA_BASE}/lines/{quote(full_id, safe='')}/route_schedules"
    params = {
        "from_datetime": "20260713T080000",
        "items_per_schedule": "2"
    }

    logger.info("Fetching line_stations (route_schedules) for %s", navitia_id)
    routes = []
    unique_stations_map = {}

    try:
        resp = await _get_with_fallback(url, headers={"apikey": api_key}, params=params, timeout=12.0, client=client)
        if resp.status_code == 200:
            data = resp.json()
            route_schedules = data.get("route_schedules", [])
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

                    # Deduplicate using station name for the unique flat stations list
                    if name not in unique_stations_map:
                        unique_stations_map[name] = station_info

                if len(route_path) > 1:
                    routes.append(route_path)
    except Exception as e:
        logger.error("Error fetching route_schedules for %s: %s", navitia_id, e)

    # Fallback to stop_points if no routes were parsed successfully
    if not routes:
        logger.warning("No route schedules found for %s, falling back to stop_points", navitia_id)
        url_fb = f"{NAVITIA_BASE}/lines/{quote(full_id, safe='')}/stop_points"
        try:
            resp_fb = await _get_with_fallback(url_fb, headers={"apikey": api_key}, timeout=12.0, client=client)
            if resp_fb.status_code == 200:
                data_fb = resp_fb.json()
                stop_points = data_fb.get("stop_points", [])
                for sp in stop_points:
                    name = sp.get("name", "").split("(")[0].strip()
                    stop_area_id = sp.get("stop_area", {}).get("id") or sp.get("id")

                    coord = sp.get("coord") or sp.get("stop_area", {}).get("coord")
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
                    if name not in unique_stations_map:
                        unique_stations_map[name] = station_info
        except Exception as e:
            logger.error("Error fallback fetching stop_points for %s: %s", navitia_id, e)

    result = {
        "stations": list(unique_stations_map.values()),
        "routes": routes
    }

    _cache_set(_line_stations_cache, navitia_id, result, LINE_STATIONS_TTL)
    return result

