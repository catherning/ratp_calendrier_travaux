# RATP Calendrier Travaux

## Presentation 
### English
This project is designed to scrape construction details for the Paris metro system, generate ICS files for calendar events, and provide a user-friendly interface using Streamlit.
It came from a personal need: there are already several calendar information on the official pages https://www.ratp.fr/decouvrircoulisses/modernisation-du-reseau, but the complexity of the planning made me want to add the construction work information on my own personal and work calendars to better plan my following weeks. Thus an app to convert the construction work information into Outlook ics files and Google Calendar links.

### French
Ce projet est conçu pour récupérer les détails des travaux sur les lignes de métro et RER à Paris, générer des fichiers ICS pour les travaux, et fournir une interface conviviale en utilisant Streamlit.
Il est né d'un besoin personnel : il existe déjà plusieurs sites d'informations sur les pages officielles https://www.ratp.fr/decouvrircoulisses/modernisation-du-reseau, mais la complexité du planning des travaux m'a donné envie d'ajouter les informations sur les lignes qui me concernent quotidiennement dans mes propres calendriers personnels et professionnels afin de mieux planifier mes semaines. C'est ainsi qu'est née l'application permettant de convertir les informations relatives aux travaux de construction en fichiers ics Outlook et en liens Google Calendar.

## Project Structure

- **pyproject.lock**: Lists the dependencies required for the project, including Streamlit, BeautifulSoup, and any other libraries used in `backend_app.py` and `streamlit_app.py`.


- **data/data.json**: Stores the construction details in JSON format, including event summaries, start and end dates, and Google Calendar URLs.
  

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd ratp_calendrier_travaux
   ```
Download files from https://prim.iledefrance-mobilites.fr/fr/jeux-de-donnees/offre-horaires-tc-gtfs-idfm to data/

2. Install the required dependencies: Use uv
   ```
   uv sync
   ```

4. Run the backend application to scrape data and generate ICS files:
   ```
   uv run backend_app.py
   ```

5. Launch the Streamlit application:
   ```
   uv run streamlit run streamlit_app.py
   ```

## Usage

- After running the backend application, the `data/data.json` file will be populated with construction details.
- Open the Streamlit app in your web browser to view the construction details, download ICS files, and access Google Calendar links.

## Docker Compose frontend map key

The frontend map uses a CARTO Basemaps key, separate from `NAVITIA_API_KEY`. Add it as `CARTO_API_KEY` in the project-root `.env` file before building the frontend with Docker Compose. Compose passes it to the Next.js build as `NEXT_PUBLIC_CARTO_API_KEY`; this value is included in browser code, so restrict the key to your site's allowed hostnames in the CARTO dashboard. Never use the Navitia key for CARTO.

```sh
docker compose up --build
```



## Persistent station graphs and administration

The map graph is built **only by an explicit administration update**, from Navitia
`/lines/{id}/vehicle_journeys`, using the ordered `stop_times` of the
`base_schedule`. All pages are read, without a current-day filter, to include
branches and short turns. Schedule-table rows and geographic proximity are
not used to infer station order.

Platforms are grouped by `stop_area.id`. Duplicate paths, reverse paths, short
turns and express paths that are subsequences of more complete paths are
discarded before creating symmetric station links. Express links on partially
overlapping paths are also removed when another simple path explicitly supplies
the intermediate stations. Links belonging to loops are preserved; no graph-wide
transitive reduction is used. Distinct branches are retained.
Missing/invalid coordinates reject the build rather than connect
stations across a missing stop.

This is a **station-adjacency graph inferred from scheduled service**, not rail
geometry. An express-only section cannot reveal unserved intermediate stations;
a direct bypass with exactly the same endpoints as an omnibus section is also
not distinguishable from express service using stop sequences alone.

Graphs are stored as **permanent JSON files**, with a schema version and an
update timestamp. They do not expire after 30 days and are not deleted when
the backend restarts. The public `GET /lines/stations?lines=1,4,A` only reads
these files: **it never calls Navitia**, even when data is missing or old.
Reads run outside the event loop, do not wait for an update to finish, and
observe the latest file on the next request (including across backend workers).

The default directory is
`$XDG_DATA_HOME/ratp-calendrier-travaux/line_graphs/` (`~/.local/share/` when
`XDG_DATA_HOME` is unset). Set `LINE_GRAPH_DATA_DIR` to a writable **persistent
volume** in production. The old `LINE_GRAPH_CACHE_DIR` remains supported as a
fallback for existing deployments; existing versioned files are compatible.
Compose already mounts `line-graphs` at `/app/data/line_graphs`, so files survive
backend container recreation. Do not delete that volume on redeployment.
Legacy `static_lines_graph.json` files are no longer read, since their links
were inferred from schedule-table rows.

For installations using the previous default `~/.cache/` directory, copy the
validated, versioned JSON files into the new data directory before starting
the new backend, or temporarily set `LINE_GRAPH_DATA_DIR` to the old directory.
An empty data directory returns HTTP **503** until an administrator populates it;
there is deliberately no slow on-demand initialization by a visitor.

### Protected update endpoint

Set a strong, random `ADMIN_API_KEY` in the **backend environment only**.
An empty key disables the endpoint (HTTP 503). Never put it in a
`NEXT_PUBLIC_*` variable, a browser request, a public URL, or source control.
The update endpoint expects this key in the `X-Admin-Key` header:

```sh
curl --fail-with-body --max-time 1800 \
  -X POST 'https://YOUR_BACKEND/admin/lines/stations/refresh?lines=1,4,A' \
  -H "X-Admin-Key: $ADMIN_API_KEY"
```

Line codes are explicit, validated before updating, and deduplicated.
Updates are sequential within a batch to limit Navitia load. The request waits
until each update is built, validated and **successfully written to disk**:

```json
{
  "lines": {
    "2": {"status": "updated", "station_count": 25, "link_count": 24}
  }
}
```

HTTP 200 means all requested files were updated. HTTP 502 reports at least one
failure, with per-line `updated`/`failed` outcomes; successful files remain updated
and failed lines keep their previous files. HTTP 409 reports an update already
running for a requested line in the same backend process. Use a single updater
instance/process to avoid concurrent refreshes across replicas.
Writes use a temporary file, flush and atomic replacement, so readers never
see a partially written graph. Failures are logged and never disguised as
successful updates. Invalid credentials return HTTP 401.
The old public `?refresh=true` is rejected (HTTP 422).
No admin page or frontend call to the update endpoint is added.

### Calling it now and later with Cloud Scheduler

Now: call the protected POST from an administrator's terminal or a trusted
server-side deployment task. The local prepopulation script below is another
option and requires only the Navitia key.

Later: configure an **HTTP POST Cloud Scheduler job**, for example monthly, with
the endpoint URL, explicit line codes and the `X-Admin-Key` header over HTTPS.
Prefer one job per line with staggered schedules: reconstruction can take several
minutes, so configure the service timeout and Scheduler attempt deadline accordingly
(HTTP Scheduler permits at most 30 minutes). Retry non-2xx responses, and monitor
the reported per-line outcomes. This change does not create any cloud resources.
Keep the admin secret restricted to trusted operators/scheduler configuration;
IAM/OIDC authentication can replace the shared secret in a later deployment.

**Cloud Run's local container filesystem is ephemeral**, even if the path is
called `data/`. Before using Cloud Scheduler with Cloud Run, mount a durable,
shared data source (for example a Cloud Storage volume), configure
`LINE_GRAPH_DATA_DIR` and verify its atomic-write semantics, or adapt this
file store to Cloud Storage object writes. The Compose named volume is durable
for the current deployment; the Cloud Run storage integration is not implemented
by this change.

If the vehicle-journey collection omits `stop_times`, the builder requests that
journey's detail before deciding whether it is usable. Definitions still empty
in the detail are ignored with a warning; no links are inferred from them.
Invalid coordinates and failed detail requests still reject the build.

The frontend loads each selected line independently and draws it as soon as
its graph arrives. A slow or failed line does not hide the others. The map view
shows loading progress, lists failed lines and provides a retry button.

To prepopulate selected lines before serving the frontend, run
`uv run python -m scratch.generate_static_graph 2 7 A`.
Omit line codes to refresh all registered lines. This script uses the same
builder and permanent file store as the API, not the legacy static-graph algorithm.

Only administrative updates require multiple Navitia requests. Visitor loads
always read the stored files. To run the optional live line-2 and RER-A tests:

```sh
RUN_NAVITIA_GRAPH_SMOKE=1 uv run pytest tests/test_line_graph.py -k live
```

The live test requires `NAVITIA_API_KEY` in the environment or the project `.env`.

## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes. The code is not clean and it's mainly a PoC.

### TODO
- Use https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/line_reports/lines/line%3AIDFM%3AC01374/line_reports? instead of scraping!
v2   - https://prim.iledefrance-mobilites.fr/fr/apis/idfm-navitia-line_reports-v2
   - https://prim.iledefrance-mobilites.fr/playground/play.html?request=https%3A%2F%2Fprim.iledefrance-mobilites.fr%2Fmarketplace%2Fv2%2Fnavitia%2Fjourneys%3Ffrom%3Dstop_area%253AIDFM%253A71590%26to%3Dstop_area%253AIDFM%253A71311%26
  - https://prim.iledefrance-mobilites.fr/fr/aide-et-contact/documentation/prise-en-main-des-api/api-information-trafic-travaux/api-calculateur-ile-de-france-mobilites-messages-info-trafic-
- Add RER / Transilien lines
- Revamp front: change from streamlit? 
- CICD ?
- Check accessibility
- Expose API endpoint on construction work? only if there's other use cases
- Store history of construction works?  
- Use https://github.com/ToroData/Streamlit-App-KeepAlive for streamlit
- Where to use NEXT_PUBLIC_API_URL for deployment?


# Full revamp
Revised Target Architecture
┌─────────────────────────────────────────┐
│  Frontend  (e.g. Next.js / plain React)  │
│  - Journey input with stop autocomplete  │
│  - Line multiselect                      │
│  - Calendar view (FullCalendar directly) │
│  - ICS download / Google Calendar links  │
└──────────────┬──────────────────────────┘
               │  REST / JSON
               ▼
┌─────────────────────────────────────────┐
│  Backend API  (FastAPI)                  │
│                                          │
│  GET  /places?q=...                      │
│         → proxy Navitia /places          │
│                                          │
│  GET  /disruptions?lines=1,A,H,...       │
│         → Navitia /line_reports (cached) │
│         → filter + normalize             │
│                                          │
│  GET  /journey-disruptions               │
│          ?from=stop_area:IDFM:71590      │
│          &to=stop_area:IDFM:71311        │
│         → Navitia /journeys              │
│         → collect lines + stops          │
│         → /line_reports per line         │
│         → filter_for_journey()           │
│                                          │
│  GET  /disruptions/{id}/ics              │
│         → generate ICS bytes on-demand   │
│                                          │
│  GET  /disruptions/{id}/google-calendar  │
│         → return Google Calendar URL     │
└──────────────┬──────────────────────────┘
               │  HTTPS + apikey header
               ▼
     Navitia API  (prim.iledefrance-mobilites.fr)
       /places, /journeys, /line_reports

## Migration Path (phased)
- 1	Extract API client + domain logic from backend_app.py into src/services/ and src/domain/. Wire up FastAPI with /disruptions and /places.
- 2	Add /journey-disruptions endpoint + filter_for_journey().
- 3	Add /ics endpoint (single + bulk).
- 4	Replace Streamlit frontend with React/Next.js calling the new API.
- 5	Drop scraping code, GTFS files, LLM dependencies, Cloud Run Job, GCS storage.

## Summary
- Drop: scraping, LLM parsing, GTFS files, Cloud Run Job, GCS storage, Streamlit
Keep and restructure: disruption_to_construction_details(), is_relevant_disruption(), fetch_line_reports(), ICS + Google Calendar generation
- Add: FastAPI app with /places, /disruptions, /journey-disruptions, /ics endpoints; in-process functools.lru_cache or cachetools.TTLCache for Navitia calls
- New frontend: Next.js calling your own FastAPI (API key never leaves the server)
- Expand lines scope: all Métro + RER + Transilien lines (Navitia API supports them all, just add the line IDs to your LINE_INFO equivalent)

# Public data doc
- https://data.iledefrance-mobilites.fr/api/datasets/1.0/offre-horaires-tc-gtfs-idfm/attachments/opendata_gtfs_pdf/