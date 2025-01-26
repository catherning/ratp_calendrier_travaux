import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime
import os

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

def parse_construction_page(url):
    """Parses a single construction page to extract dates, stations, and descriptions."""
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch URL {url}: {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extracting details (adjust these selectors based on the RATP page structure)
    details = {
        'dates': None,
        'stations': None,
        'description': []
    }

    # Example parsing logic:
    date_section = soup.find('div', class_='date-class')  # Adjust to actual class/HTML structure
    if date_section:
        details['dates'] = date_section.get_text(strip=True)

    station_section = soup.find('div', class_='station-class')  # Adjust to actual class/HTML structure
    if station_section:
        details['stations'] = station_section.get_text(strip=True)

    description_list = soup.find_all('li')  # Assuming descriptions are in <li> tags
    for item in description_list:
        details['description'].append(item.get_text(strip=True))

    return details

def create_ics_file(construction_details, output_folder):
    """Creates an ICS file for the given construction details."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for idx, description in enumerate(construction_details['description']):
        c = Calendar()
        e = Event()

        # Populate event details
        e.name = f"RATP Work: {description}"
        e.begin = datetime.now()  # Placeholder; replace with parsed start date
        e.end = datetime.now()   # Placeholder; replace with parsed end date
        e.description = f"Stations affected: {construction_details['stations']}"

        c.events.add(e)

        # Save to file
        filename = os.path.join(output_folder, f"event_{idx + 1}.ics")
        with open(filename, 'w') as f:
            f.writelines(c.serialize())

if __name__ == "__main__":
    links = [f"https://www.ratp.fr/decouvrir/coulisses/modernisation-du-reseau/metro-ligne-{i}-travaux" for i in range(1, 15)]
    print(f"Found {len(links)} construction detail links.")

    print("Parsing construction pages...")
    # all_construction_details = []
    # for link in links:
    #     print(f"Parsing {link}...")
    #     details = parse_construction_page(link)
    #     all_construction_details.append(details)

    # # Step 3: Create ICS files
    # print("Creating ICS files...")
    # output_folder = "ics_files"
    # for construction_details in all_construction_details:
    #     create_ics_file(construction_details, output_folder)

    # print(f"ICS files created in folder: {output_folder}")


    from seleniumbase import SB
    from bs4 import BeautifulSoup
    import os
    os.environ['PYVIRTUALDISPLAY_DISPLAYFD'] = '0'
    # os.environ['DISPLAY'] = "0"
    from pyvirtualdisplay import Display

    # URL of the main RATP page
    url = "https://www.ratp.fr/les-travaux-en-cours-et-a-venir"
    display = Display(visible=1, size=(1440, 1880))
    display.start()
    # Use SeleniumBase with UC mode and headless mode (Xvfb for virtual display)
    with SB(uc=True, xvfb=True) as sb:
        sb.uc_open(url)

        # Handle the cookie banner
        try:
            # Wait for the cookie accept button to be visible and click it
            sb.wait_for_element("//button[contains(text(), 'Accepter')]", timeout=10)
            sb.uc_click("//button[contains(text(), 'Accepter')]")
            print("Cookie banner accepted.")
        except Exception as e:
            print("Cookie banner not found or could not be clicked:", str(e))

        # Ensure the page is fully loaded
        try:
            sb.wait_for_element("body", timeout=10)  # Wait for the page body to be visible
            print("Page loaded successfully.")
        except Exception as e:
            print("Failed to load the main page:", str(e))

        # Extract the page source and parse it with BeautifulSoup
        page_source = sb.get_page_source()
        soup = BeautifulSoup(page_source, "html.parser")

        # Extract relevant links containing the specified text
        links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if 'travaux et fermetures sur la ligne' in a_tag.get_text(strip=True).lower():
                links.append(f"https://www.ratp.fr{href}")

        # Print the extracted links
        print(f"Found {len(links)} links:")
        for link in links:
            print(link)
