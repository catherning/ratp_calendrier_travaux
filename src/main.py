"""
FastAPI application – RATP Travaux API.

Endpoints:
  GET /lines                                  → list all supported lines
  GET /places?q=<query>                       → proxy Navitia /places (stop area search)
  GET /disruptions?lines=4,A,H               → fetch + normalise disruptions
  GET /disruptions/{impact_id}/ics            → download ICS file (single or grouped)
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
    DisruptionPeriod,
    find_disruption_in_raw,
    find_disruption_detail_with_all_periods,
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
from src.services.navitia_client import fetch_line_reports, fetch_places, fetch_journeys, fetch_line_stations


# ── Bootstrap ──────────────────────────────────────────────────────────────────

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG") == "true" else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("NAVITIA_API_KEY") or ""
if not API_KEY:
    logger.warning("NAVITIA_API_KEY is not set – API calls will fail.")
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
    version="3.0.0",
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


# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_navitia_journey(journey: dict) -> tuple[JourneyItinerary, dict[str, list[dict]]]:
    """Parse a raw Navitia journey into a JourneyItinerary model and return a line stops map."""
    sections_list = []
    line_stops_map: dict[str, list[dict]] = {}

    for section in journey.get("sections", []):
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
        duration=journey.get("duration", 0),
        departure_time=_navitia_dt_to_iso(journey.get("departure_date_time", "")),
        arrival_time=_navitia_dt_to_iso(journey.get("arrival_date_time", "")),
        sections=sections_list,
        impacted_disruption_ids=[]
    )

    return journey_itinerary, line_stops_map


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


@app.get("/lines/stations", summary="Fetch stations for selected lines")
async def get_lines_stations(
    lines: str = Query(..., description="Comma-separated line codes, e.g. '1,4,A'"),
    client: httpx.AsyncClient = Depends(get_client),
) -> dict[str, dict]:
    """
    Fetch the stations and ordered routes for each requested line.
    Returns a dict mapping line code to dict with 'stations' and 'routes'.
    """
    codes = [c.strip() for c in lines.split(",") if c.strip()]
    if not codes:
        raise HTTPException(status_code=422, detail="No valid line codes provided")

    unknown = [c for c in codes if c not in LINE_REGISTRY]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown line codes: {unknown}")

    async def _fetch_one_stations(code: str) -> tuple[str, dict]:
        line_info = LINE_REGISTRY[code]
        try:
            res = await fetch_line_stations(line_info.navitia_id, API_KEY, client=client)
            return code, res
        except Exception as exc:
            logger.error("Failed to fetch stations for line %s: %s", code, exc)
            return code, {"stations": [], "routes": []}

    results = await asyncio.gather(*[_fetch_one_stations(c) for c in codes])
    return {code: res for code, res in results}


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
    normalise and return a list of grouped DisruptionDetail objects.
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


@app.get("/journey-disruptions", summary="Get disruptions impacting up to 5 calculated journeys", response_model=JourneyDisruptionResponse)
async def get_journey_disruptions(
    from_stop: str = Query(..., alias="from", description="From stop area ID"),
    to_stop: str = Query(..., alias="to", description="To stop area ID"),
    client: httpx.AsyncClient = Depends(get_client),
) -> JourneyDisruptionResponse:
    """
    Calculate up to 5 alternative journeys, find used lines and stop points, and
    return relevant disruptions and proposed itineraries with specific impact mappings.
    """
    try:
        journeys_data = await fetch_journeys(from_stop, to_stop, API_KEY, client=client)
    except Exception as exc:
        logger.error("Navitia journeys error: %s", exc)
        raise HTTPException(status_code=502, detail="Error reaching Navitia journeys API")

    journeys = journeys_data.get("journeys", [])
    if not journeys:
        return JourneyDisruptionResponse(itinerary=None, itineraries=[], disruptions=[])

    itineraries_list = []
    line_stops_by_itinerary = []

    # Parse up to 5 itineraries
    for j in journeys[:5]:
        itinerary, line_stops = parse_navitia_journey(j)
        itineraries_list.append(itinerary)
        line_stops_by_itinerary.append(line_stops)

    # Collect all unique line codes used across any of the itineraries
    all_used_line_codes = set()
    for line_stops in line_stops_by_itinerary:
        all_used_line_codes.update(line_stops.keys())

    # Fetch disruptions for all unique lines (in parallel)
    disruptions_by_line: dict[str, list[DisruptionDetail]] = {}

    async def _fetch_line_disruptions(line_code: str):
        line_info = LINE_REGISTRY[line_code]
        try:
            raw = await fetch_line_reports(line_info.navitia_id, API_KEY, client=client)
            disruptions = normalize_line_disruptions(raw, line_info)
            disruptions_by_line[line_code] = disruptions
        except Exception as exc:
            logger.error("Error fetching disruptions for line %s: %s", line_code, exc)
            disruptions_by_line[line_code] = []

    await asyncio.gather(*[_fetch_line_disruptions(code) for code in all_used_line_codes])

    # De-duplicate disruptions globally across all lines using disruption ID
    all_disruptions_map: dict[str, DisruptionDetail] = {}

    # Map which disruptions impact which itineraries
    for idx, (itinerary, line_stops) in enumerate(zip(itineraries_list, line_stops_by_itinerary)):
        impacted_ids = []
        for line_code, stops in line_stops.items():
            line_disruptions = disruptions_by_line.get(line_code, [])
            relevant_disruptions = filter_for_journey(line_disruptions, stops)
            
            for d in line_disruptions:
                if d.id not in all_disruptions_map:
                    all_disruptions_map[d.id] = d
                
            for rd in relevant_disruptions:
                impacted_ids.append(rd.id)
                
        itinerary.impacted_disruption_ids = list(set(impacted_ids))

    # Set back-compatible impacts_itinerary flag based on the best (first) itinerary
    best_impacted_ids = set(itineraries_list[0].impacted_disruption_ids) if itineraries_list else set()
    for d_id, d in all_disruptions_map.items():
        d.impacts_itinerary = (d_id in best_impacted_ids)

    all_relevant_disruptions = list(all_disruptions_map.values())
    all_relevant_disruptions.sort(key=lambda d: d.date_debut)

    return JourneyDisruptionResponse(
        itinerary=itineraries_list[0] if itineraries_list else None,
        itineraries=itineraries_list,
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
            # Handle if it's just the impact_id without __p
            line_to_items[line_code].append((compound_id, 0, compound_id))

    async def _fetch_line_items(line_code: str, items: list):
        line_info = LINE_REGISTRY[line_code]
        try:
            raw = await fetch_line_reports(line_info.navitia_id, API_KEY, client=client)
            for impact_id, period_index, compound_id in items:
                # If there's an exact compound_id match, let's fetch it, or fallback to retrieving all periods
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
    period: int | None = Query(None, description="application_period index. If omitted, exports all periods in a single calendar file."),
    client: httpx.AsyncClient = Depends(get_client),
) -> Response:
    """Generate and return an ICS calendar file for the given disruption (single or multi-period grouped)."""
    line_info = get_line(line)
    if line_info is None:
        raise HTTPException(status_code=404, detail=f"Unknown line: {line}")

    try:
        raw = await fetch_line_reports(line_info.navitia_id, API_KEY, client=client)
    except Exception as exc:
        logger.error("Navitia error for ICS %s: %s", impact_id, exc)
        raise HTTPException(status_code=502, detail="Error reaching Navitia API")

    # If period index is supplied, download that specific period only
    if period is not None and period >= 0:
        detail = find_disruption_in_raw(raw, impact_id, period, line_info)
        if detail is None:
            raise HTTPException(status_code=404, detail="Disruption period not found")

        ics_bytes = build_ics_bytes(
            summary=detail.summary,
            date_debut=detail.date_debut,
            date_fin=detail.date_fin,
            description=detail.text,
            location=detail.stations if detail.stations != "toute la ligne" else "",
        )

        safe_name = detail.summary[:60].replace(" ", "_").replace("—", "-") + f"_p{period}.ics"
        return Response(
            content=ics_bytes,
            media_type="text/calendar",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
        )

    # Otherwise, download ALL periods of this disruption as a single unified file
    detail_all = find_disruption_detail_with_all_periods(raw, impact_id, line_info)
    if detail_all is None:
        raise HTTPException(status_code=404, detail="Disruption not found")

    events = []
    for p in detail_all.periods:
        events.append(DisruptionDetail(
            id=f"{detail_all.impact_id}__p{p.period_index}",
            impact_id=detail_all.impact_id,
            period_index=p.period_index,
            line_code=detail_all.line_code,
            line_navitia_id=detail_all.line_navitia_id,
            line_name=detail_all.line_name,
            line_color=detail_all.line_color,
            line_text_color=detail_all.line_text_color,
            summary=f"{detail_all.summary} ({p.period_index + 1}/{len(detail_all.periods)})" if len(detail_all.periods) > 1 else detail_all.summary,
            date_debut=p.date_debut,
            date_fin=p.date_fin,
            text=detail_all.text,
            stations=detail_all.stations,
            cause=detail_all.cause,
            effect=detail_all.effect,
            periods=[]
        ))

    ics_bytes = build_bulk_ics_bytes(events)
    safe_name = detail_all.summary[:60].replace(" ", "_").replace("—", "-") + "_grouped.ics"
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
