# import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime
import os
import json
from dotenv import load_dotenv
from litellm import completion
import uuid

load_dotenv()

from seleniumbase import SB
os.environ['PYVIRTUALDISPLAY_DISPLAYFD'] = '0'
from pyvirtualdisplay import Display

DATE_FORMAT = "%Y%m%dT%H%M%S"

def get_llm_json_response(prompt,model="mistral/mistral-small-latest") -> str:
    messages = [{ "content": prompt,"role": "user"}]

    response = completion(model=model, messages=messages)

    response_dict = response.choices[0].message.content
    
    #TODO: use https://docs.litellm.ai/docs/completion/json_mode#pass-in-json_schema
    return response_dict

def parse_construction_page(source_text):
    """Parses a single construction page to extract dates, stations, and descriptions. """
    soup = BeautifulSoup(source_text, 'html.parser')

    if "pas de travaux" in soup.find('div', class_='article__accroche-content').text:
        return None
    

    # Example parsing logic:
    text_end = ["Pour adapter au mieux votre trajet","Pour adapter au mieux vos trajets"]
    text = " ".join(soup.find("div",class_="article-content").get_text(strip=True).split(text_end[0])[:-1])
    if text =="":
        text = " ".join(soup.find("div",class_="article-content").get_text(strip=True).split(text_end[1])[:-1])
        
    prompt = (
        "Extrait les données des travaux qui vont avoir lieu sur la ligne de métro Parisien. L'objectif est de créer un fichier ics par type de travaux. "
        "Je veux donc en output une liste et avec chaque élément : le nom de l'événement, la date et heure de début, date et heure de fin, l'éventuelle récurrence si c'est pertinent. "
        "Le format doit être un json pour être lisible en Python, je vais parser avec la librairie iCalendar. "
        f"Les dates doivent être au format {DATE_FORMAT}. "
        "Fais attention si c'est indiqué une date incluse ou excluse."
        "L'output json doit absolument être dans la bonne syntaxe. "
        "S'il faut une récurrence, ça doit être avec la syntaxe RRULE de iCalendar 4.8.5. Les clés que peut avoir ce dictionnaire sont donc <FREQ=daily|weekly>, <BYDAY=SU,MO,TU,WE,TH,FR,SA sans espaces>, <INTERVAL=integer>, <UNTIL=datetime>. "
        "INTERVAL peut être nécessaire s'il y a des travaux toutes les X semaines par exemple. Mais si la fréquence n'est pas régulière, il faut séparer en deux events, un avec un rrule, un sans."
        "Pour les stations, si c'est une liste de station, alors sépare par une virgule ','. Si c'est entre 2 stations, sépare par un pipe |. "
        "Pour le champ summary, ça va être utilisé pour créer le fichier ics, donc il ne faut pas des caractères incompatibles avec un nom de fichier, genre / ou |. "
        """Voici des examples en anglais pour les RRULEs : 
        Daily for 10 occurrences => RRULE:FREQ=DAILY;COUNT=10
        Daily until December 24, 1997 =>  RRULE:FREQ=DAILY;UNTIL=19971224T000000Z
        Every 10 days, 5 occurrences =>  RRULE:FREQ=DAILY;INTERVAL=10;COUNT=5
        Weekly until December 24, 1997 => RRULE:FREQ=WEEKLY;UNTIL=19971224T000000Z
        Weekly on Tuesday and Thursday for five weeks => RRULE:FREQ=WEEKLY;UNTIL=19971007T000000Z;WKST=SU;BYDAY=TU,TH
        """
        "Il vaut mieux utiliser une RRULE et des plages de date si possible que plusieurs éléments dans la liste, pour optimiser le traitement et réduire au mieux le nombre de fichiers. "
        
        "Exemple 1 d'input :"
        """
            "En raison de travaux de renouvellement des appareils de voie, la ligne 3 du métro sera fermée, entre les stations Pont de Levallois-Bécon et Wagram, du 15 au 20 février 2025 inclus entre 22h et 6h.
            Un service de bus de remplacement sera à votre disposition entre le terminus de Pont de Levallois-Bécon et la station Wagram, aux mêmes horaires que le métro. "
        """
        "Output :"
        """
        ```json
        [{"date_debut": "20250215T220000",
        "date_fin": "20250220T060000",
        "summary":"Ligne 3 - Travaux entre Pont de Levallois-Bécon et Wagram",
        "stations":"Pont de Levallois-Bécon | Wagram"}
        "rrule":{"freq":"weekly","count":10} 
        ]
        ```
        """
        
        "Exemple 2 d'input :"
        """
            "En raison de travaux de renouvellement des appareils de voie, la ligne 8 du métro sera fermée, sur toute la ligne, tous les dimanches du 1er janvier au 20 février 2025 inclus.
        """
        "Output :"
        """
        ```json
        [{"date_debut": "20250215T220000",
        "date_fin": "20250220T060000",
        "summary":"Ligne 3 - Travaux entre Pont de Levallois-Bécon et Wagram",
        "stations":"Pont de Levallois-Bécon | Wagram"}
        "rrule":{"freq":"weekly","count":10}
        ]
        ```
        """
        
        "Exemple 3 d'input :"
        """
            "En raison de travaux de renouvellement des appareils de voie, les 12, 13 avril et 18 mai 2025 : la ligne 6 sera fermée entre les stations Daumesnil et Nation ;.
        """
        "Attention : on peut optimiser et mettre le 12 et 13 dans un seul évent avec plage de date étendue, et le 18 de manière séparée! Donc Output avec 2 éléments et non 3 dans la liste:"
        """
        ```json
        [
            {"date_debut": "20250412T000000",
            "date_fin": "20250413T230000",
            "summary":"Ligne 6 - Travaux entre Daumesnil et Nation",
            "stations":"Daumesnil | Nation"
            {"date_debut": "20250518T000000",
            "date_fin": "20250519T000000",
            "summary":"Ligne 6 - Travaux entre Daumesnil et Nation",
            "stations":"Daumesnil | Nation"
        ]
        ```
        """
        f"Le text à parser est le suivant : {text}"
        )
    # TODO: try https://github.com/kvh/recurrent to convert to rrule
    max_retries = 4
    attempts = 0
    success = False

    while not success and attempts < max_retries:
        try:
            response = get_llm_json_response(prompt).split("```")
            for el in response:
                if el[:4]=="json":
                    details = json.loads(el[4:])                
                    success = True
                    break
            attempts +=1
        except json.decoder.JSONDecodeError as e:
            attempts += 1
            print(f'Attempt {attempts}: {e}')
            # Log error or take corrective measures

    if success:
        for i in range(len(details)):
            details[i]["summary"] = details[i]["summary"].replace("/","-")
        print('Operation succeeded!')
    else:
        print('All attempts failed.')
        return None
    return details

def create_ics_file(construction_details, output_folder,filename) -> None:
    """Creates an ICS file for the given construction details. """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    c = Calendar()
    e = Event()

    # Populate event details
    c.add("prodid","-//Test RATP travaux//FR")         # Date the event was created (required)
    c.add("version","2.0")         # Date the event was created (required)
    e.add("summary",construction_details["summary"])
    e.add("dtstart",datetime.strptime(construction_details["date_debut"],DATE_FORMAT))
    # e.description = f"Stations affected: {construction_details['stations']}"
    e.add("uid",uuid.uuid4())          # Unique identifier (required)
    e.add("dtstamp",datetime.now()  )         # Date the event was created (required)
    e.add("vtimezone","Europe/Paris")
    
    if "rrule" in construction_details.keys(): 
        construction_details["rrule"] = construction_details["rrule"].replace(" ","") 
        rule = construction_details["rrule"].copy()
        rule["byday"] = rule["byday"].split(",") 
        rule["until"]=datetime.strptime(rule["until"],DATE_FORMAT)
        e.add('rrule', rule)
    else:
        e.add("dtend",datetime.strptime(construction_details["date_fin"],DATE_FORMAT))

    c.add_component(e)

    # Save to file
    filename = os.path.join(output_folder, f"{filename}.ics")
    with open(filename, 'wb') as f:
        f.write(c.to_ical())

def create_google_event(construction_details) -> str:
    """
    https://support.google.com/calendar/thread/81344786/how-do-i-generate-add-to-calendar-link-from-our-own-website?hl=en
    """
    title = construction_details["summary"].replace(' ','+')
    #&details=text
    url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}&dates={construction_details['date_debut']}/{construction_details['date_fin']}&ctz=Europe/Paris"
    if "rrule" in construction_details.keys():
        rule = construction_details["rrule"]
        url += f"&recur=RRULE:FREQ%3D{rule['freq'].upper()};BYDAY={rule['byday'].upper()};UNTIL%3D{rule['until']}"
        if "interval" in rule:
            url+= f";INTERVAL%3D{rule['interval']}"
    return url

def main() -> None:
    # data = {}
    data = {i:{"link":f"https://www.ratp.fr/decouvrir/coulisses/modernisation-du-reseau/metro-ligne-{i}-travaux"} for i in range(1, 15)}
    data["A"] = {"link":"https://www.ratp.fr/decouvrir/coulisses/modernisation-du-reseau/rer-a-travaux"}
    data["B"] = {"link":"https://www.ratp.fr/decouvrir/coulisses/modernisation-du-reseau/rer-b-travaux"}
    
    # TODO: prendre de cette page  https://www.bonjour-ratp.fr/actualites/articles/bulletin-travaux-14fev/
    print(f"Found {len(data)} construction detail links. ")
    
    # URL of the main RATP page
    with  Display(visible=1, size=(1440, 1880)) as display:
        # Use SeleniumBase with UC mode and headless mode (Xvfb for virtual display)
        with SB(uc=True, xvfb=True) as sb:
            for i,(line_name,line_info) in enumerate(data.items()):
                sb.uc_open(line_info["link"])

                # Handle the cookie banner
                if i==0:
                    try:
                        sb.wait_for_element('button[id="popin_tc_privacy_button"]', timeout=2)
                        sb.uc_click('button[id="popin_tc_privacy_button"]')
                        print("Cookie banner refused. ")
                    except Exception as e:
                        print("Cookie banner not found or could not be clicked:", str(e))

                # Ensure the page is fully loaded
                try:
                    sb.wait_for_element("body", timeout=10)
                    print(f"Page for line {line_name} loaded successfully. ")
                except Exception as e:
                    print("Failed to load the main page:", str(e))

                # Extract the page source and parse it with BeautifulSoup
                page_source = sb.get_page_source()

                details = parse_construction_page(page_source)

                if details:
                    # # Step 3: Create ICS files
                    # print("Creating ICS files... ")
                    output_folder = "data"
                    for j,construction_details in enumerate(details):
                        try:
                            create_ics_file(construction_details, output_folder, f"event_ligne_{construction_details['summary']}")
                            details[j]["google_calendar"] = create_google_event(construction_details)
                        except:
                            print("L'event n'a pas pu être créé! Syntaxe incorrecte")
                    data[line_name]["construction_list"] = details
                # else:
                #     no_work.append(i)
            
            data = {k:v for k,v in data.items() if "construction_list" in v.keys()}
    with open("data/data2.json", "w") as f:
        json.dump(data,f)
    print("Finished")

if __name__ == "__main__":
    main()