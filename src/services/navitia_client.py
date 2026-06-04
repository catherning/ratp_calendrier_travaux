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

LINE_REPORTS_TTL = 300.0   # 5 minutes
PLACES_TTL = 600.0         # 10 minutes
JOURNEYS_TTL = 300.0       # 5 minutes


def _cache_get(cache: dict, key: str) -> dict | list | None:
    entry = cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    return None


def _cache_set(cache: dict, key: str, value, ttl: float) -> None:
    cache[key] = (value, time.monotonic() + ttl)


# ── Public functions ───────────────────────────────────────────────────────────

async def fetch_line_reports(navitia_id: str, api_key: str) -> dict:
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
    async with httpx.AsyncClient(timeout=12.0) as client:
        resp = await client.get(url, headers={"apikey": api_key})
        resp.raise_for_status()
        data: dict = resp.json()

    _cache_set(_line_reports_cache, navitia_id, data, LINE_REPORTS_TTL)
    return data


async def fetch_places(q: str, api_key: str, count: int = 15) -> list:
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

    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(url, headers={"apikey": api_key}, params=params)
        resp.raise_for_status()
        places: list = resp.json().get("places", [])

    _cache_set(_places_cache, cache_key, places, PLACES_TTL)
    return places


async def fetch_journeys(from_id: str, to_id: str, api_key: str) -> dict:
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
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers={"apikey": api_key}, params=params)
        resp.raise_for_status()
        data: dict = resp.json()

    _cache_set(_journeys_cache, cache_key, data, JOURNEYS_TTL)
    return data

