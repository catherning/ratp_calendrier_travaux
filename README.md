# RATP Calendrier Travaux

This project is designed to scrape construction details for the Paris metro system, generate ICS files for calendar events, and provide a user-friendly interface using Streamlit.

## Project Structure

- **backend_app.py**: Contains the main logic for scraping construction details, creating ICS files, and generating Google Calendar URLs. It includes functions for parsing HTML, creating ICS files, and handling the main execution flow.
  
- **streamlit_app.py**: The entry point for the Streamlit application. It loads the data from `data/data.json`, displays the construction details, provides download links for the ICS files, and includes buttons for Google Calendar URLs.
  
- **data/data.json**: Stores the construction details in JSON format, including event summaries, start and end dates, and Google Calendar URLs.
  
- **requirements.txt**: Lists the dependencies required for the project, including Streamlit, BeautifulSoup, and any other libraries used in `backend_app.py`.

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

Feel free to submit issues or pull requests for improvements or bug fixes.

# TODO
- Add RER / Transilien lines
- Add filtering to find the relevant construction work depending on the station (then on a travel plan)
- Add rrule
- Add cron to update the folder with data regularly ?