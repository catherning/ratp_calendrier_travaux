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