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

2. Install the required dependencies: Use uv
   ```
   uv sync
   ```

3. Run the backend application to scrape data and generate ICS files:
   ```
   uv run backend_app.py
   ```

4. Launch the Streamlit application:
   ```
   uv run streamlit run streamlit_app.py
   ```

## Usage

- After running the backend application, the `data/data.json` file will be populated with construction details.
- Open the Streamlit app in your web browser to view the construction details, download ICS files, and access Google Calendar links.

## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes. The code is not clean and it's mainly a PoC.

### TODO
- Add RER / Transilien lines
- Add Second LLM to check first LLM response is ok ?
- Add filtering to find the relevant construction work depending on the station (then on a travel plan)
- Add cron to update the folder with data every month ?