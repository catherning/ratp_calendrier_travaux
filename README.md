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

- **backend_app.py**: Contains the main logic for scraping construction details, creating ICS files, and generating Google Calendar URLs. It includes functions for parsing HTML, creating ICS files, and handling the main execution flow.
  
- **streamlit_app.py**: The entry point for the Streamlit application. It loads the data from `data/data.json`, displays the construction details, provides download links for the ICS files, and includes buttons for Google Calendar URLs.
  
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
Install xephyr :
`sudo apt-get update && sudo apt-get -y install xserver-xephyr`

Install chrome 
```
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i ./google-chrome*.deb
sudo apt-get install -f
```

# TODO: don't use seleniumbase which is overkill ? => playwright ?
In this case: 
```
uv run playwright install
```

3. Download the GTFS files
TODO:

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
- Add filtering to find the relevant construction work depending on the station (then on a travel plan)
   - Pistes : https://prim.iledefrance-mobilites.fr/fr/jeux-de-donnees/lignes-gtfs
   - https://prim.iledefrance-mobilites.fr/fr/jeux-de-donnees/offre-horaires-tc-gtfs-idfm?tab=vue_personnalisee
   - https://github.com/psrc/transit_service_analyst/wiki/transit_service_analyst-documentation
   - https://github.com/remix/partridge
   - https://github.com/mrcagney/gtfs_kit
   - Ou scraping de https://www.ma-ligne.co/ en dernier recours ou demander à ChatGPT d'avoir la liste des lignes
- Add RER / Transilien lines
- Add backend cron to update the folder with data every week
- Revamp front: change from streamlit? 
- CICD ?
- Add Second LLM to check first LLM response is ok ?
- Check accessibility
- Expose API endpoint on construction work? only if there's other use cases
- Store history of construction works?  
- Use https://github.com/ToroData/Streamlit-App-KeepAlive for streamlit

#### Security (do first)
  -  Rotate the Mistral API key — a real key is in .env which could be accidentally exposed
  -  Remove --server.enableXsrfProtection false from .devcontainer/devcontainer.json — disables CSRF protection even for shared Codespaces
#### Backend (src/backend_app.py)
- Bugs (crashers)
  -  Fix get_llm_json_response fallback: response is never assigned when the API call fails, causing NameError on line ~35; the fallback also produces a completely different object structure
  -  Fix bare except: blocks in scrape_data/scrape_data2 (~lines 456, 474) that reference unbound e — any ICS creation error raises a second NameError, masking the original
  -  Guard rrule["byday"] access (~line 168) — crashes with KeyError when LLM returns an rrule without byday (e.g., simple daily recurrences)
  -  Fix or delete scrape_data2 — calls sync_playwright but the import is commented out, making it a silent dead function
- Correctness
  -  Move print(f'Construction work information extracted: {details[i]}') inside the loop (~line 153) — currently only prints the last element
  -  Replace e.add("vtimezone", "Europe/Paris") with proper timezone-aware datetime objects — VTIMEZONE is a calendar component, not an event property
  -  Fix LLM prompt examples — both JSON examples are missing a comma between "stations" and "rrule", which may teach the LLM to produce invalid JSON
- Code quality
  -  Replace relative DATA_FOLDER = "../data/" with a path relative to __file__ — current code breaks if not run from src/
  -  Add tests for GTFS path-finding functions (get_stations_graph_by_line, get_ordered_station_paths) — complex logic, zero test coverage
-  Resolve # TODOs and pass functions

#### Frontend (src/streamlit_app.py)
- Bugs (crashers)
  -  Fix travail['download_link'] KeyError in the station-filter UI (~line 241) — field does not exist in the current data format
  -  Guard no_work_lines.remove(line) (~line 261) — raises ValueError if data contains a line not present in LINE_INFO
- Correctness
  -  Convert date_debut/date_fin from %Y%m%dT%H%M%S to ISO 8601 before passing to streamlit-calendar — FullCalendar.js may misparse the current format
  -  Use date_text field for human-readable date display in the station-filter expander instead of raw 20260301T220000 strings
- Code quality / UX 
  -  Deduplicate the "show all" and station-filter UIs — both render simultaneously, creating visual redundancy
  -  Add line "15" (Grand Paris Express) to LINE_INFO if it should be supported, or cap the backend scrape range to match
- Infrastructure / Config
  -  Fix .devcontainer/devcontainer.json Python version: image uses python:1-3.11-bullseye but pyproject.toml requires >=3.12
  -  Fix devcontainer postAttachCommand and openFiles paths — both reference streamlit_app.py at the project root, not src/streamlit_app.py
  -  Switch devcontainer updateContentCommand from pip3 install to uv sync to respect the lockfile
  -  Clean up pyproject.toml: remove python-certifi-win32 (Windows-only), pyautogui (unused), mistral-inference (pulls local model weights but only API is used); add pandas as an explicit dependency; move ipykernel/pytest/pytest-playwright to [project.optional-dependencies.dev]
  -  Clean up data/ folder: remove or archive old data_YYYYMMDD.json files; establish a clear naming convention; remove committed .ics files that should be gitignored
  -  Fix README.md: update file paths (src/backend_app.py, src/streamlit_app.py), fix lockfile name (uv.lock not pyproject.lock), and update run commands accordingly