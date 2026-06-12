"""
FastAPI application – RATP Travaux API.

Endpoints:
  GET /lines                                  → list all supported lines
  GET /places?q=<query>                       → proxy Navitia /places (stop area search)
  GET /disruptions?lines=4,A,H               → fetch + normalise disruptions
  GET /disruptions/{impact_id}/ics            → download ICS file
  GET /disruptions/{impact_id}/google-calendar → Google Calendar URL

Run locally:
  uv run uvicorn src.main:app --reload --port 8000
"""
import asyncio
from contextlib import asynccontextmanager
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import httpx

from src.domain.disruptions import (
    DisruptionDetail,
    find_disruption_in_raw,
    normalize_line_disruptions,
    filter_for_journey,
    JourneyDisruptionResponse,
    JourneyItinerary,
    ItinerarySection,
    _navitia_dt_to_iso,
)
from src.domain.lines import (
    ALL_CODES,
    LINE_REGISTRY,
    LineInfo,
    get_line,
)
from src.services.ics_generator import build_google_calendar_url, build_ics_bytes, build_bulk_ics_bytes
from src.services.navitia_client import fetch_line_reports, fetch_places, fetch_journeys


# ── Bootstrap ──────────────────────────────────────────────────────────────────

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG") == "true" else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("RATP_API_KEY") or ""
if not API_KEY:
    logger.warning("RATP_API_KEY is not set – API calls will fail.")
else:
    logger.info("API Key successfully loaded from environment.")

_allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")]

# ── App ────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Shared, thread-safe asynchronous client with reusable connection pool
    async with httpx.AsyncClient() as client:
        app.state.client = client
        yield

app = FastAPI(
    title="RATP Travaux API",
    description="Proxies Navitia line_reports and converts disruptions to ICS / Google Calendar.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.client


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/lines", summary="List all supported transit lines")
def get_lines() -> list[dict]:
    """Return metadata for all supported Métro, RER and Transilien lines."""
    result = []
    for code in ALL_CODES:
        info = LINE_REGISTRY[code]
        result.append({
            "code": info.code,
            "navitia_id": info.navitia_id,
            "name": info.name,
            "mode": info.mode,
            "color": info.color,
            "text_color": info.text_color,
            "logo_url": info.logo_url,
        })
    return result


@app.get("/places", summary="Search for stop areas by name")
async def get_places(
    q: str = Query(..., min_length=2, description="Search query, e.g. 'Nation'"),
    client: httpx.AsyncClient = Depends(get_client),
) -> list[dict]:
    """Proxy Navitia /places, filtering to stop_areas only."""
    try:
        raw_places = await fetch_places(q, API_KEY, client=client)
    except Exception as exc:
        logger.error("Navitia /places error: %s", exc)
        raise HTTPException(status_code=502, detail="Error reaching Navitia API")

    result = []
    for place in raw_places:
        stop_area = place.get("stop_area", {})
        result.append({
            "id": place.get("id"),
            "name": stop_area.get("name", place.get("name", "")),
            "label": stop_area.get("label", place.get("name", "")),
            "coord": stop_area.get("coord", {}),
        })
    return result


@app.get("/disruptions", summary="Fetch disruptions for selected lines")
async def get_disruptions(
    lines: str = Query(..., description="Comma-separated line codes, e.g. '4,A,H'"),
    client: httpx.AsyncClient = Depends(get_client),
) -> list[DisruptionDetail]:
    """
    Fetch Navitia line_reports for each requested line (in parallel),
    normalise and return a flat list of DisruptionDetail objects.
    """
    codes = [c.strip() for c in lines.split(",") if c.strip()]
    if not codes:
        raise HTTPException(status_code=422, detail="No valid line codes provided")

    unknown = [c for c in codes if c not in LINE_REGISTRY]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown line codes: {unknown}")

    async def _fetch_one(code: str) -> list[DisruptionDetail]:
        line_info: LineInfo = LINE_REGISTRY[code]
        try:
            raw = await fetch_line_reports(line_info.navitia_id, API_KEY, client=client)
            return normalize_line_disruptions(raw, line_info)
        except Exception as exc:
            logger.error("Failed to fetch disruptions for line %s: %s", code, exc)
            return []

    results_per_line = await asyncio.gather(*[_fetch_one(c) for c in codes])
    flat = [d for sub in results_per_line for d in sub]

    # Sort chronologically
    flat.sort(key=lambda d: d.date_debut)
    return flat


@app.get("/journey-disruptions", summary="Get disruptions impacting a specific journey", response_model=JourneyDisruptionResponse)
async def get_journey_disruptions(
    from_stop: str = Query(..., alias="from", description="From stop area ID"),
    to_stop: str = Query(..., alias="to", description="To stop area ID"),
    client: httpx.AsyncClient = Depends(get_client),
) -> JourneyDisruptionResponse:
    """
    Calculate journey, find used lines and stop points, and return relevant disruptions and proposed itinerary.
    """
    try:
        journeys_data = await fetch_journeys(from_stop, to_stop, API_KEY, client=client)
    except Exception as exc:
        logger.error("Navitia journeys error: %s", exc)
        raise HTTPException(status_code=502, detail="Error reaching Navitia journeys API")

    journeys = journeys_data.get("journeys", [])
    if not journeys:
        return JourneyDisruptionResponse(itinerary=None, disruptions=[])

    # Extract lines and their stops from the first (best) journey
    best_journey = journeys[0]
    line_stops_map: dict[str, list[dict]] = {}

    # Parse sections into ItinerarySections
    sections_list = []
    for section in best_journey.get("sections", []):
        sec_type = section.get("type", "")
        mode = None
        line_code = None
        line_color = None
        line_text_color = None

        display_info = section.get("display_informations", {})
        if display_info:
            line_code = display_info.get("code")
            line_color = display_info.get("color")
            line_text_color = display_info.get("text_color")
            physical_mode = display_info.get("physical_mode", "").lower()
            commercial_mode = display_info.get("commercial_mode", "").lower()
            if "métro" in physical_mode or "metro" in physical_mode or "métro" in commercial_mode or "metro" in commercial_mode:
                mode = "metro"
            elif "rer" in physical_mode or "rer" in commercial_mode:
                mode = "rer"
            elif "train" in physical_mode or "transilien" in physical_mode or "train" in commercial_mode or "transilien" in commercial_mode:
                mode = "train"
            elif "tram" in physical_mode or "tramway" in physical_mode or "tram" in commercial_mode or "tramway" in commercial_mode:
                mode = "tram"
            else:
                mode = "bus"
        else:
            mode = section.get("mode")

        from_name = section.get("from", {}).get("name", "").split("(")[0].strip()
        to_name = section.get("to", {}).get("name", "").split("(")[0].strip()

        if not from_name:
            from_name = "Départ"
        if not to_name:
            to_name = "Arrivée"

        sections_list.append(
            ItinerarySection(
                type=sec_type,
                mode=mode,
                line_code=line_code,
                line_color=line_color,
                line_text_color=line_text_color,
                from_name=from_name,
                to_name=to_name,
                duration=section.get("duration", 0),
            )
        )

        # Build line stops map for disruptions
        if sec_type == "public_transport" and line_code and line_code in LINE_REGISTRY:
            stops = []
            for sdt in section.get("stop_date_times", []):
                sp = sdt.get("stop_point", {})
                if sp:
                    stops.append({
                        "id": sp.get("id"),
                        "name": sp.get("name", "").split("(")[0].strip()
                    })
            if line_code not in line_stops_map:
                line_stops_map[line_code] = []
            line_stops_map[line_code].extend(stops)

    journey_itinerary = JourneyItinerary(
        duration=best_journey.get("duration", 0),
        departure_time=_navitia_dt_to_iso(best_journey.get("departure_date_time", "")),
        arrival_time=_navitia_dt_to_iso(best_journey.get("arrival_date_time", "")),
        sections=sections_list,
    )

    # For each line, fetch its disruptions, filter them, and accumulate
    all_relevant_disruptions: list[DisruptionDetail] = []
    seen_ids = set()

    async def _fetch_and_filter(line_code: str, stops: list[dict]):
        line_info = LINE_REGISTRY[line_code]
        try:
            raw = await fetch_line_reports(line_info.navitia_id, API_KEY, client=client)
            disruptions = normalize_line_disruptions(raw, line_info)
            relevant = filter_for_journey(disruptions, stops)
            for d in relevant:
                if d.id not in seen_ids:
                    seen_ids.add(d.id)
                    all_relevant_disruptions.append(d)
        except Exception as exc:
            logger.error("Error processing line %s for journey: %s", line_code, exc)

    await asyncio.gather(*[_fetch_and_filter(code, stops) for code, stops in line_stops_map.items()])

    # Sort chronologically
    all_relevant_disruptions.sort(key=lambda d: d.date_debut)

    return JourneyDisruptionResponse(
        itinerary=journey_itinerary,
        disruptions=all_relevant_disruptions,
    )


@app.get("/disruptions/ics", summary="Download bulk ICS for multiple disruptions")
async def get_bulk_ics(
    ids: str = Query(..., description="Comma-separated disruption detail IDs, e.g. 'uuid__p0,uuid__p1'"),
    lines: str = Query(..., description="Comma-separated line codes corresponding to the IDs"),
    client: httpx.AsyncClient = Depends(get_client),
) -> Response:
    """Generate and return a bulk ICS calendar file for selected disruptions."""
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    line_list = [l.strip() for l in lines.split(",") if l.strip()]

    if len(id_list) != len(line_list):
        raise HTTPException(status_code=422, detail="Mismatched ids and lines count")

    disruptions_to_export: list[DisruptionDetail] = []
    from collections import defaultdict
    line_to_items = defaultdict(list)

    for compound_id, line_code in zip(id_list, line_list):
        if line_code not in LINE_REGISTRY:
            continue
        try:
            impact_id, p_str = compound_id.split("__p")
            period_index = int(p_str)
            line_to_items[line_code].append((impact_id, period_index, compound_id))
        except ValueError:
            continue

    async def _fetch_line_items(line_code: str, items: list):
        line_info = LINE_REGISTRY[line_code]
        try:
            raw = await fetch_line_reports(line_info.navitia_id, API_KEY, client=client)
            for impact_id, period_index, compound_id in items:
                detail = find_disruption_in_raw(raw, impact_id, period_index, line_info)
                if detail:
                    disruptions_to_export.append(detail)
        except Exception as exc:
            logger.error("Failed to fetch bulk item for line %s: %s", line_code, exc)

    await asyncio.gather(*[_fetch_line_items(code, items) for code, items in line_to_items.items()])

    if not disruptions_to_export:
        raise HTTPException(status_code=404, detail="No valid disruptions found to export")

    ics_bytes = build_bulk_ics_bytes(disruptions_to_export)
    return Response(
        content=ics_bytes,
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="travaux_ratp_export.ics"'},
    )


@app.get("/disruptions/{impact_id}/ics", summary="Download ICS for a disruption")
async def get_disruption_ics(
    impact_id: str,
    line: str = Query(..., description="Line code, e.g. '4'"),
    period: int = Query(0, ge=0, description="application_period index"),
    client: httpx.AsyncClient = Depends(get_client),
) -> Response:
    """Generate and return an ICS calendar file for the given disruption."""
    line_info = get_line(line)
    if line_info is None:
        raise HTTPException(status_code=404, detail=f"Unknown line: {line}")

    try:
        raw = await fetch_line_reports(line_info.navitia_id, API_KEY, client=client)
    except Exception as exc:
        logger.error("Navitia error for ICS %s: %s", impact_id, exc)
        raise HTTPException(status_code=502, detail="Error reaching Navitia API")

    detail = find_disruption_in_raw(raw, impact_id, period, line_info)
    if detail is None:
        raise HTTPException(status_code=404, detail="Disruption not found")

    ics_bytes = build_ics_bytes(
        summary=detail.summary,
        date_debut=detail.date_debut,
        date_fin=detail.date_fin,
        description=detail.text,
        location=detail.stations if detail.stations != "toute la ligne" else "",
    )

    safe_name = detail.summary[:60].replace(" ", "_").replace("—", "-") + ".ics"
    return Response(
        content=ics_bytes,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@app.get("/disruptions/{impact_id}/google-calendar", summary="Get Google Calendar URL")
async def get_google_calendar_url(
    impact_id: str,
    line: str = Query(..., description="Line code, e.g. '4'"),
    period: int = Query(0, ge=0, description="application_period index"),
    client: httpx.AsyncClient = Depends(get_client),
) -> dict:
    """Return the Google Calendar 'add event' URL for the given disruption."""
    line_info = get_line(line)
    if line_info is None:
        raise HTTPException(status_code=404, detail=f"Unknown line: {line}")

    try:
        raw = await fetch_line_reports(line_info.navitia_id, API_KEY, client=client)
    except Exception as exc:
        logger.error("Navitia error for GCal %s: %s", impact_id, exc)
        raise HTTPException(status_code=502, detail="Error reaching Navitia API")

    detail = find_disruption_in_raw(raw, impact_id, period, line_info)
    if detail is None:
        raise HTTPException(status_code=404, detail="Disruption not found")

    url = build_google_calendar_url(
        summary=detail.summary,
        date_debut=detail.date_debut,
        date_fin=detail.date_fin,
        description=detail.text,
    )
    return {"url": url}


@app.get("/health", include_in_schema=False)
def health() -> dict:
    return {"status": "ok"}
