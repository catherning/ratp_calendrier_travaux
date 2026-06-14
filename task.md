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

## Phase 2: Fine-Grained Itinerary Filtering & Reason Extraction
- [x] Separate Summary & Detail Extraction in `src/domain/disruptions.py` (prioritize "moteur" for detailed description and "notification"/"title" for short titles)
- [x] Add `impacts_itinerary: bool | None = None` field to the `DisruptionDetail` Pydantic model
- [x] Update `/journey-disruptions` in `src/main.py` to return all line disruptions with proper itinerary impact flags set by `filter_for_journey()`
- [x] Add `impacts_itinerary?: boolean` to `DisruptionDetail` type definition in `frontend/lib/types.ts`
- [x] Implement the client-side `onlyDirectImpacts` filter toggle ("Uniquement sur mon trajet") in `frontend/app/page.tsx`
- [x] Render disruption description text always-visible and add "Hors trajet" header badge inside `frontend/components/DisruptionCard.tsx`
- [x] Add custom glassmorphism styles for `.disruption-card__outside-badge` inside `frontend/app/globals.css`
- [x] Add dedicated Apple Calendar export button (iCal formatted) in `frontend/components/DisruptionCard.tsx` and modal view in `frontend/app/page.tsx`
- [x] Add `.btn--apple` custom color scheme in `frontend/app/globals.css` with a high-end red glassmorphic design and the official brand SVG icon


