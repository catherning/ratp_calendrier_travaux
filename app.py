import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime
import os
import json
from dotenv import load_dotenv

load_dotenv()

from seleniumbase import SB
os.environ['PYVIRTUALDISPLAY_DISPLAYFD'] = '0'
# os.environ['DISPLAY'] = "0"
from pyvirtualdisplay import Display

DATE_FORMAT = "%Y%m%dT%H%M%S"
    
    
def fetch_main_page(url):
    """Fetches the main RATP construction works page and extracts links to construction details."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch URL {url}: {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all relevant links (assuming they are in anchor tags with specific classes or patterns)
    links = []
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if '/travaux/' in href:  # Adjust this filter based on the actual structure of the RATP site
            links.append(f"https://www.ratp.fr{href}")

    return links

def get_llm_json_response(prompt):
    response = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {os.environ['MISTRAL_API_KEY']}"
        },
        json={
            "model": "mistral-tiny",
            "messages": [{"role": "user", "content": prompt}]
        }
    )

    response_dict = json.loads(response.text)
    response_dict = response_dict["choices"][0]["message"]["content"]
    try:
        details = json.loads(response_dict.split("```")[1][4:])
    except json.decoder.JSONDecodeError as e:
        raise json.decoder.JSONDecodeError
    return details

def parse_construction_page(source_text):
    """Parses a single construction page to extract dates, stations, and descriptions."""
    soup = BeautifulSoup(source_text, 'html.parser')

    if "pas de travaux" in soup.find('div', class_='article__accroche-content').text:
        return None
    

    # Example parsing logic:
    text = " ".join(soup.find("div",class_="article-content").get_text(strip=True).split("Pour adapter au mieux votre trajet")[:-1])
    prompt = (
        "Extrait les données des travaux qui vont avoir lieu sur la ligne de métro Parisien. L'objectif est de créer un fichier ics par type de travaux. "
        "Je veux donc en output une liste et avec chaque élément : le nom de l'événement, la date et heure de début, date et heure de fin, l'éventuelle récurrence si c'est pertinent."
        "Le format doit être un json pour être lisible en Python, je vais parser avec la librairie iCalendar."
        "S'il faut une récurrence, ça doit être avec la syntaxe RRULE de iCalendar 4.8.5. Les clés que peut avoir ce dictionnaire sont donc freq, interval, count"
        f"Les dates doivent être au format {DATE_FORMAT}"
        "Exemple d'input :"
        """
            "En raison de travaux de renouvellement des appareils de voie, la ligne 3 du métro sera fermée, entre les stations Pont de Levallois-Bécon et Wagram, du 15 au 20 février 2025 inclus entre 22h et 6h.
            Un service de bus de remplacement sera à votre disposition entre le terminus de Pont de Levallois-Bécon et la station Wagram, aux mêmes horaires que le métro."
        """
        "Output :"
        """
        ```json
        [{"date_debut": "20250215T220000",
        "date_fin": "20250220T060000",
        "summary":"Ligne 3 - Travaux entre Pont de Levallois-Bécon et Wagram",
        "stations":"Entre Pont de Levallois-Bécon et Wagram"}
        "rrule":{"freq":"weekly","count":10}
        ]
        ```
        """
        f"Le text à parser est le suivant : {text}"
        )
    max_retries = 3
    attempts = 0
    success = False

    while not success and attempts < max_retries:
        try:
            details = get_llm_json_response(prompt)
            success = True
        except json.decoder.JSONDecodeError as e:
            attempts += 1
            print(f'Attempt {attempts}: {e}')
            # Log error or take corrective measures

    if success:
        print('Operation succeeded!')
    else:
        print('All attempts failed.')
    return details

def create_ics_file(construction_details, output_folder,filename):
    """Creates an ICS file for the given construction details."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    c = Calendar()
    e = Event()

    # Populate event details
    c.add("prodid","-//Test RATP travaux//FR")         # Date the event was created (required)
    c.add("version","2.0")         # Date the event was created (required)
    e.add("summary",construction_details["summary"])
    e.add("dtstart",datetime.strptime(construction_details["date_debut"],DATE_FORMAT))
    e.add("dtend",datetime.strptime(construction_details["date_fin"],DATE_FORMAT))
    # e.description = f"Stations affected: {construction_details['stations']}"
    e.add("uid","12ef27g3eef92g370d")          # Unique identifier (required)
    e.add("dtstamp",datetime.now()  )         # Date the event was created (required)
    e.add("vtimezone","Europe/Paris")
    
    if "rrule" in construction_details.keys():
        pass # TODO:
        # e.add('rrule', {'freq': 'daily'})

    c.add_component(e)

    # Save to file
    filename = os.path.join(output_folder, f"{filename}.ics")
    with open(filename, 'wb') as f:
        f.write(c.to_ical())

def create_google_event(construction_details):
    """
    https://support.google.com/calendar/thread/81344786/how-do-i-generate-add-to-calendar-link-from-our-own-website?hl=en
    """
    title = construction_details["summary"].replace(' ','+')
    #&details=text
    url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}&dates={construction_details['date_debut']}/{construction_details['date_fin']}&ctz=Europe/Paris"
    if "rrule" in construction_details.keys():
        pass # TODO:
        # url += "&recur=RRULE:FREQ%3DWEEKLY"
    return url

if __name__ == "__main__":
    links = {i:f"https://www.ratp.fr/decouvrir/coulisses/modernisation-du-reseau/metro-ligne-{i}-travaux" for i in range(1, 15)}
    print(f"Found {len(links)} construction detail links.")

    # URL of the main RATP page
    display = Display(visible=1, size=(1440, 1880))
    display.start()
    
    # Use SeleniumBase with UC mode and headless mode (Xvfb for virtual display)
    with SB(uc=True, xvfb=True) as sb:
        for i,link in links.items():
            sb.uc_open(link)

            # Handle the cookie banner
            if i==1:
                try:
                    sb.wait_for_element('button[id="popin_tc_privacy_button"]', timeout=2)
                    sb.uc_click('button[id="popin_tc_privacy_button"]')
                    print("Cookie banner refused.")
                except Exception as e:
                    print("Cookie banner not found or could not be clicked:", str(e))

            # Ensure the page is fully loaded
            try:
                sb.wait_for_element("body", timeout=10)
                print("Page loaded successfully.")
            except Exception as e:
                print("Failed to load the main page:", str(e))

            # Extract the page source and parse it with BeautifulSoup
            page_source = sb.get_page_source()
            # soup = BeautifulSoup(page_source, "html.parser")

            details = parse_construction_page(page_source)

            if details:
                # # Step 3: Create ICS files
                # print("Creating ICS files...")
                output_folder = "ics_files"
                for j,construction_details in enumerate(details):
                    create_ics_file(construction_details, output_folder, f"event_ligne_{i}_{j}")
                    google_link = create_google_event(construction_details)

                # print(f"ICS files created in folder: {output_folder}")

    display.stop()