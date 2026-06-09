# Revamp & Enhancements Checklist

## Backend & API Endpoints
- [x] Add `fetch_journeys` and in-process caching in `src/services/navitia_client.py`
- [x] Add name normalization and `filter_for_journey()` in `src/domain/disruptions.py`
- [x] Add `build_bulk_ics_bytes()` in `src/services/ics_generator.py`
- [x] Wire up `/journey-disruptions` and `/disruptions/ics` (bulk) in `src/main.py`
- [x] Update `/journey-disruptions` endpoint to return proposed route and stations (`JourneyDisruptionResponse`)
- [x] Refine itinerary filtering to ignore disruptions on other branches that do not touch the route's stations
- [x] Test all backend endpoints to verify correctness and parallel performance

## Frontend Dashboard
- [x] Add FullCalendar packages and interaction dependencies to `frontend/package.json` and install
- [x] Add autocomplete proxy methods and bulk ICS url formatting in `frontend/lib/api.ts`
- [x] Create premium interactive dashboard in `frontend/app/page.tsx` with Journey search, Line select grid, and Calendrier/Liste tabbed view
- [x] Fix autocomplete dropdown clipping bug by adding localized `style={{ overflow: "visible" }}` to Journey Planner card container
- [x] Add dynamic horizontal timeline route visualizer above disruptions list for the proposed journey itinerary
- [x] Add past/completed event filtering checkbox to hide or gray out expired disruptions
- [x] Add operational impact dropdown selector to filter by disruption effect/severity (All, Interrupted, Delays, etc.)
- [x] Upgrade Disruption cards and Modals to display both disruption Cause (e.g. "Travaux") and Effect (e.g. "Retards importants")
- [x] Design high-end dark glassmorphism styling and custom FullCalendar dark overrides in `frontend/app/globals.css`
- [x] Test and build Next.js frontend to ensure no build or compilation errors

## Cleanup & Deprecation
- [x] Delete `backend_app.py`, `streamlit_app.py`, and `utils.py` (inside `src/`)
- [x] Delete legacy GTFS folder/files (inside `data/`)

## Docker Deployment
- [x] Create production-grade backend `Dockerfile` for FastAPI
- [x] Create multi-stage, optimized frontend `Dockerfile` for Next.js
- [x] Create unified `docker-compose.yml` orchestrating both services with healthchecks
- [x] Add optimized `.dockerignore` filters for build context efficiency
- [x] Spin up Docker Compose build to verify successful compilation of both containers
