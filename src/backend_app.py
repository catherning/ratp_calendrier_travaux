# import requests
import os
import json
import csv
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime
from dotenv import load_dotenv
from litellm import completion
import uuid
import pandas as pd
# from playwright.sync_api import sync_playwright
# import ssl
# ssl._create_default_https_context = ssl._create_unverified_context

load_dotenv()

from seleniumbase import SB
os.environ['PYVIRTUALDISPLAY_DISPLAYFD'] = '0'
from pyvirtualdisplay import Display

DATE_FORMAT = "%Y%m%dT%H%M%S"
DATA_FOLDER = "../data/"

def get_llm_json_response(prompt,model="mistral/mistral-small-latest") -> str:
    # TODO: use Vertex when deployed in GCP ?
    messages = [{ "content": prompt,"role": "user"}]

    try:
        response = completion(model=model, messages=messages)
    except:
        # Fallback to local model if available
        try:
            from transformers import pipeline
            pipe = pipeline("text-generation", model="../../SmolLM-360M")
            resp = pipe(prompt)
            response_dict = resp[0]['generated_text']
        except ImportError:
            # If transformers not available, return error message
            response_dict = '{"error": "LLM service unavailable and no fallback model"}'
    
    #TODO: use https://docs.litellm.ai/docs/completion/json_mode#pass-in-json_schema
    return response_dict

def retry_construction_detail_with_error(construction_details, error, all_works_text, max_retries=2):
    # TODO: see if can refactor to have a general LLM call with retry with method parse_construction_page. Change the model here to a more powerful one if needed, and keep the smaller one for the first attempt in parse_construction_page
    """
    Retry LLM parsing when ICS file creation fails due to malformed construction_details.
    Provides error context to the LLM to correct the issue.
    
    Args:
        construction_details: The failed construction details dict
        error: The exception that was raised
        all_works_text: The original HTML text extracted from the page
        max_retries: Number of retry attempts
        
    Returns:
        Fixed construction_details dict or None if retry fails
    """
    error_msg = str(error)
    print(f"Retrying construction detail extraction due to error: {error_msg}")
    print(f"Original construction_details that failed: {construction_details}")
    
    corrective_prompt = (
        "Une tentative de créer un fichier ics a échoué avec l'erreur suivante: "
        f"{error_msg}\n\n"
        "Les données extraites précédemment étaient:\n"
        f"{json.dumps(construction_details, ensure_ascii=False, indent=2)}\n\n"
        "Voici le texte original à parser:\n"
        f"{all_works_text}\n\n"
        "Corrige les données extraites pour que toutes les clés requises soient présentes et bien formatées. "
        "Assure-toi que:\n"
        "1. date_debut et date_fin sont au format YYYYMMDDTHHMMSS\n"
        "2. summary ne contient pas de caractères incompatibles avec un nom de fichier (pas de / ou |)\n"
        "3. Toutes les clés obligatoires sont présentes: date_debut, date_fin, date_text, summary, stations\n"
        "4. Si present, rrule doit avoir seulement les clés: freq, byday, interval, until, count\n"
        "Retourne UNIQUEMENT le JSON corrigé dans un bloc ```json ... ```"
    )
    
    for attempt in range(max_retries):
        try:
            response = get_llm_json_response(corrective_prompt)
            response_lines = response.split("```")
            for el in response_lines:
                if el.strip().startswith("json"):
                    fixed_details = json.loads(el[4:])
                    print(f"Successfully corrected construction details on attempt {attempt + 1}")
                    return fixed_details
            print(f"Retry attempt {attempt + 1}: Could not extract JSON from response")
        except Exception as e:
            print(f"Retry attempt {attempt + 1} failed: {e}")
            continue
    
    print("All retry attempts failed. Skipping this construction detail.")
    return None

def parse_construction_page(source_text,path):
    """Parses a single construction page to extract dates, stations, and descriptions. """
    soup = BeautifulSoup(source_text, 'html.parser')

    if "pas de travaux" in soup.find('div', class_='article__accroche-content').text:
        return None
    

    # Example parsing logic:
    all_works = " ||| ".join([text.get_text(strip=True) for text in soup.find_all("div",class_="squeezecnt")])
    prompt = (
        "Extrait les données des travaux qui vont avoir lieu sur la ligne de métro Parisien. L'objectif est de créer un fichier ics par type de travaux. "
        "Je veux donc en output une liste et avec chaque élément : le nom de l'événement, la date et heure de début, date et heure de fin, l'éventuelle récurrence si c'est pertinent. "
        "Le format doit être un json pour être lisible en Python, je vais parser avec la librairie iCalendar. "
        f"Je veux deux 3 champs de date : date_debut, date_fin avec un formattage datetime {DATE_FORMAT} et un champ date_text pour un affichage plus humain qui paraphrase le texte d'origine. "
        "Fais attention si c'est indiqué une date incluse ou excluse et aux heures."
        "L'output json doit absolument être dans la bonne syntaxe. "
        "S'il faut une récurrence, ça doit être avec la syntaxe RRULE de iCalendar 4.8.5. Les clés que peut avoir ce dictionnaire sont donc <FREQ=daily|weekly>, <BYDAY=SU,MO,TU,WE,TH,FR,SA sans espaces>, <INTERVAL=integer>, <UNTIL=datetime>. "
        "Attention, respecte ces clés, on ne peut pas avoir d'autres clés, dont BYWEEKDAY."
        "INTERVAL peut être nécessaire s'il y a des travaux toutes les X semaines par exemple. Mais si la fréquence n'est pas régulière, il faut séparer en deux events, un avec un rrule, un sans."
        "Pour les stations, si c'est une liste de station, alors sépare par une virgule ','. Si c'est entre 2 stations, sépare par un pipe |. "
        "Pour le champ summary, ça va être utilisé pour créer le fichier ics, donc il ne faut pas des caractères incompatibles avec un nom de fichier, genre / ou |. "
        "Si le texte indique qu'il n'y a pas de travaux, retourne un json avec liste vide. "
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
            "En raison de travaux de renouvellement des appareils de voie, la ligne 3 du métro sera fermée, entre les stations Pont de Levallois - Bécon et Wagram, du 15 au 20 février 2025 inclus entre 22h et 6h.
            Un service de bus de remplacement sera à votre disposition entre le terminus de Pont de Levallois - Bécon et la station Wagram, aux mêmes horaires que le métro. "
        """
        "Output :"
        """
        ```json
        [{"date_debut": "20250215T220000",
        "date_fin": "20250220T060000",
        "date_text": "Du 15 au 20 février 2025 inclus entre 22h et 6h",
        "summary":"Ligne 3 - Travaux entre Pont de Levallois - Bécon et Wagram",
        "stations":"Pont de Levallois - Bécon | Wagram"
        "rrule":{"freq":"weekly","count":10} 
        ]
        ```
        """
        
        "Exemple 2 d'input :"
        """
            "En raison de travaux de renouvellement des appareils de voie, la ligne 8 du métro sera fermée, sur toute la ligne, tous les dimanches du 1er janvier au 20 février 2025 inclus à partir de 22h.
        """
        "Output :"
        """
        ```json
        [{"date_debut": "20250215T220000",
        "date_fin": "20250220T060000",
        "date_text": "tous les dimanches du 1er janvier au 20 février 2025 inclus à partir de 22h",
        "summary":"Ligne 3 - Travaux entre Pont de Levallois - Bécon et Wagram",
        "stations":"Pont de Levallois - Bécon | Wagram"
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
            "date_text":"Les 12, 13 avril 2025",
            "summary":"Ligne 6 - Travaux entre Daumesnil et Nation",
            "stations":"Daumesnil | Nation"
            },
            {"date_debut": "20250518T000000",
            "date_fin": "20250519T000000",
            "date_text":"Le 18 mai 2025",
            "summary":"Ligne 6 - Travaux entre Daumesnil et Nation",
            "stations":"Daumesnil | Nation"
            }
        ]
        ```
        """
        f"Le text à parser est le suivant : {all_works}"
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
            details[i]["summary"] = details[i]["summary"].replace("/","-") # ne pas avoir de / entre les stations
            
        # details[i]["stations_concernes"] = get_stations_between(path,details[i]["stations"])
        # details[i]["stations_concernes"] = get_stations_between(path,details[i]["station_start"],details[i]["station_end"])
        print(f'Construction work information extracted: {details[i]}')
    else:
        print('All attempts failed.')
        return None
    return details, all_works

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
        construction_details["rrule"]["byday"] = construction_details["rrule"]["byday"].replace(" ","") 
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

    
def get_stations_graph_by_line(route_name,routes,trips,stop_times,stops):

    """Récupère le graphe des stations pour une ligne donnée (ex: 'M1' pour la ligne 1)"""
   
    # 1. Trouver l'ID de la ligne
    if route_name.isnumeric():
        agency = "IDFM:Operator_100" # RATP
    else:
        agency = "IDFM:71" # RER. XXX: Later IDFM:1046,Transilien 
        
    route_id = routes.loc[(routes["route_short_name"] == route_name) & (routes["agency_id"]==agency), "route_id"].values
    if len(route_id) == 0:
        return f"Ligne {route_name} non trouvée."
   
    route_id = route_id[0]
    
    # 2. Trouver tous les trip_id associés à cette ligne
    line_trips = trips.loc[trips["route_id"] == route_id, ["trip_id","trip_headsign"]] # 
    if len(line_trips) == 0:
        return f"Aucun trajet trouvé pour la ligne {route_name}."
    
    # 3. Récupérer tous les arrêts pour ces trajets
    all_stops = stop_times.loc[stop_times["trip_id"].isin(line_trips["trip_id"]), ["trip_id", "stop_id", "stop_sequence"]]
    
    # 4. Compter le nombre de stations par trajet
    trip_station_counts = all_stops.groupby("trip_id").size().reset_index(name="station_count")
    trip_station_counts = trip_station_counts.sort_values("station_count", ascending=False)
    
    # 5. Identifier le trajet avec le plus de stations
    main_trip_id = trip_station_counts.iloc[0]["trip_id"]
    main_stops = all_stops.loc[all_stops["trip_id"] == main_trip_id, ["stop_id", "stop_sequence"]]
    main_stops = main_stops.sort_values("stop_sequence")
    main_stop_ids = set(main_stops["stop_id"])
    main_headsign = line_trips[line_trips["trip_id"]==main_trip_id]["trip_headsign"]

    # 6. Trouver les trajets qui ont des stations uniques (branches)
    branch_trips = []
    
    distinct_headsigns = list(line_trips["trip_headsign"].unique())
    distinct_headsigns.remove(main_headsign.values[0])

    for headsign in distinct_headsigns:
        # Filtrer les trips ayant ce headsign et prendre un sample représentatif
        relevant_trips = line_trips[line_trips["trip_headsign"] == headsign]
        
        # Prendre le trip avec le plus grand nombre d'arrêts (évite les services courts)
        trip_id = relevant_trips.loc[relevant_trips["trip_id"].map(
            lambda x: len(all_stops[all_stops["trip_id"] == x])
        ).idxmax(), "trip_id"]

        # Vérifier les nouveaux stops
        trip_stops = all_stops.loc[all_stops["trip_id"] == trip_id, "stop_id"]
        unique_stops = set(trip_stops) - main_stop_ids
        
        if len(unique_stops) > 0:
            branch_trips.append(trip_id)
            main_stop_ids.update(unique_stops)


    # 7. Construire le graphe des stations
    # Combiner le trajet principal et les branches
    selected_trips = [main_trip_id] + branch_trips
    selected_stops = all_stops.loc[all_stops["trip_id"].isin(selected_trips)]
    
    # Créer un dictionnaire pour le graphe
    station_graph = {}
    
    # Traiter chaque trajet pour construire les connexions
    for trip_id in selected_trips:
        trip_stations = selected_stops.loc[selected_stops["trip_id"] == trip_id].sort_values("stop_sequence")
        
        # Utiliser shift pour créer des paires de stations adjacentes
        prev_stations = trip_stations["stop_id"].iloc[:-1].reset_index(drop=True)
        next_stations = trip_stations["stop_id"].iloc[1:].reset_index(drop=True)
        
        # Créer un DataFrame avec les connexions
        connections = pd.DataFrame({
            "prev": prev_stations,
            "next": next_stations
        })
        
        # Ajouter les connexions au graphe
        for _, conn in connections.iterrows():
            prev_id = conn["prev"]
            next_id = conn["next"]
            
            if prev_id not in station_graph:
                station_graph[prev_id] = {"next": set(), "prev": set()}
            if next_id not in station_graph:
                station_graph[next_id] = {"next": set(), "prev": set()}
                
            station_graph[prev_id]["next"].add(next_id)
            station_graph[next_id]["prev"].add(prev_id)
    
    # 8. Enrichir avec les noms des stations
    stop_names = dict(zip(stops["stop_id"], stops["stop_name"]))
    
    for stop_id in station_graph:
        station_graph[stop_id]["name"] = stop_names.get(stop_id, "Station inconnue")
    
    return station_graph


def get_ordered_station_paths(station_graph):
    """Génère les chemins ordonnés à partir du graphe de stations"""
    # TODO: get full line, not just branch
    
    # Trouver les stations de terminus (début de ligne)
    terminus_stations = [stop_id for stop_id, data in station_graph.items()
                         if not data["prev"] or len(data["prev"]) == 0]
    
    paths = []
    
    # Pour chaque terminus, construire un chemin
    for start_station in terminus_stations:
        path = []
        
        # File d'attente pour le parcours en largeur
        queue = [(start_station, [])]
        visited = set()
        
        while queue:
            current, current_path = queue.pop(0)
            if current in visited:
                continue
            
            visited.add(current)
            new_path = current_path + [current]
            
            # Si c'est une station terminale (pas de station suivante)
            if not station_graph[current]["next"]:
                paths.append(new_path)
            else:
                # Ajouter les stations suivantes à la file
                for next_station in station_graph[current]["next"]:
                    if next_station not in visited:
                        queue.append((next_station, new_path))
    
    # Convertir les IDs en noms de stations
    named_paths = []
    for path in paths:
        named_path = [(station_id, station_graph[station_id]["name"]) for station_id in path]
        named_paths.append(named_path)
    
    return named_paths

def display_line_structure(route_name,routes,trips,stop_times,stops):
    """Affiche la structure d'une ligne avec toutes ses branches"""
    graph = get_stations_graph_by_line(route_name,routes,trips,stop_times,stops)
    
    if isinstance(graph, str):  # C'est un message d'erreur
        return graph
    
    paths = get_ordered_station_paths(graph)
    
    print(f"Structure de la ligne {route_name}:")
    for i, path in enumerate(paths):
        print(f"Branche {i+1}:")
        for j, (station_id, station_name) in enumerate(path):
            print(f"  {j+1:2d}. {station_name}")
        print()
    
    return graph, paths


def get_stations_between(path,stations):
    try:
        start,end = stations.split(" | ")
        stations_concernes = []
        include=False
        for branch in path:
            if len(stations_concernes)!=0:
                break
            for station in branch:
                if station[1]==start or include:
                    stations_concernes.append(station[1])
                    include=True
                if station[1]==end:
                    break
    except ValueError:
        if "toute la ligne" in stations.lower():
            stations_concernes = [st[1] for st in path[0]]
        else:
            stations_concernes = [stations]
    return stations_concernes

def refuse_cookies(page):
    try:
        page.locator('button[id="popin_tc_privacy_button_3"]').click(timeout=2000)
        print("Cookie banner accepted.")
    except Exception as e:
        print("Cookie banner not found or could not be clicked:", str(e))

def get_page_content(sb,line_info,line_name,i):
    sb.goto(line_info["link"])
    if i==0:
        refuse_cookies(sb)
    sb.wait_for_selector("body", timeout=10000)
    print(f"Page for line {line_name} loaded successfully.")
    return sb.content()

def scrape_data2(data,graphs):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # slowmo=50
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        for i,(line_name,line_info) in enumerate(data.items()):
            try:
                page_source = get_page_content(page,line_info,line_name,i)
                result = parse_construction_page(page_source,graphs[str(line_name)])
                if result:
                    details, all_works = result
                    for j,construction_details in enumerate(details):
                        try:
                            create_ics_file(construction_details, DATA_FOLDER + "event_ics", f"event_ligne_{construction_details['summary']}_{j+1}")
                            details[j]["google_calendar"] = create_google_event(construction_details)
                        except Exception as e:
                            print("L'event n'a pas pu être créé! Syntaxe incorrecte:", str(e))
                            print("Construction details that caused the error:", construction_details)
                            # Retry with LLM feedback
                            fixed_details = retry_construction_detail_with_error(construction_details, e, all_works)
                            if fixed_details:
                                try:
                                    create_ics_file(fixed_details, DATA_FOLDER + "event_ics", f"event_ligne_{fixed_details['summary']}_{j+1}")
                                    details[j] = fixed_details
                                    details[j]["google_calendar"] = create_google_event(fixed_details)
                                except Exception as retry_error:
                                    print(f"Retry failed for construction detail: {retry_error}")
                            else:
                                print(f"Could not fix construction detail via LLM retry. Skipping.")

                    data[line_name]["construction_list"] = details
            except Exception as e:
                print(f"Failed to process line {line_name}: {e}")
        context.close()
        browser.close()
        return data
    
def scrape_data(data,graphs):
    with Display(visible=1, size=(1440, 1880)) as display:
        # Use SeleniumBase with UC mode and headless mode (Xvfb for virtual display)
        with SB(uc=True, xvfb=True) as sb:
            for i,(line_name,line_info) in enumerate(data.items()):
                sb.uc_open(line_info["link"])

                # Handle the cookie banner
                if i==0:
                    try:
                        sb.wait_for_element('button[id="popin_tc_privacy_button_3"]', timeout=2)
                        sb.uc_click('button[id="popin_tc_privacy_button_3"]')
                        print("Cookie banner accepted. ")
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

                result = parse_construction_page(page_source,graphs[str(line_name)])

                if result:
                    details, all_works = result
                    # # Step 3: Create ICS files
                    # print("Creating ICS files... ")
                    for j,construction_details in enumerate(details):
                        try:
                            create_ics_file(construction_details, DATA_FOLDER + "event_ics", f"event_ligne_{construction_details['summary']}_{j+1}")
                            details[j]["google_calendar"] = create_google_event(construction_details)
                        except Exception as e:
                            print("L'event n'a pas pu être créé! Syntaxe incorrecte:", str(e))
                            print("Construction details that caused the error:", construction_details)
                            # Retry with LLM feedback
                            fixed_details = retry_construction_detail_with_error(construction_details, e, all_works)
                            if fixed_details:
                                try:
                                    create_ics_file(fixed_details, DATA_FOLDER + "event_ics", f"event_ligne_{fixed_details['summary']}_{j+1}")
                                    details[j] = fixed_details
                                    details[j]["google_calendar"] = create_google_event(fixed_details)
                                except Exception as retry_error:
                                    print(f"Retry failed for construction detail: {retry_error}")
                            else:
                                print(f"Could not fix construction detail via LLM retry. Skipping.")
                            
                    data[line_name]["construction_list"] = details
                # else:
                #     no_work.append(i)
    return data
    

def main(generate_graphs=False,crawl_construction_data=True) -> None:
    # TODO: prendre de cette page  https://www.bonjour-ratp.fr/actualites/articles/bulletin-travaux-14fev/
    data = {i:{"link":f"https://www.ratp.fr/decouvrir/coulisses/modernisation-du-reseau/metro-ligne-{i}-travaux"} for i in range(1, 15)}
    data["A"] = {"link":"https://www.ratp.fr/decouvrir/coulisses/modernisation-du-reseau/rer-a-travaux"}
    data["B"] = {"link":"https://www.ratp.fr/decouvrir/coulisses/modernisation-du-reseau/rer-b-travaux"}

    
    if generate_graphs or not os.path.exists(DATA_FOLDER + "graph.json") or not os.path.exists(DATA_FOLDER + "graph_paths.json"):
        folder = DATA_FOLDER + "IDFM-gtfs/"
        routes = pd.read_csv(folder+"routes.txt")
        trips = pd.read_csv(folder+"trips.txt")
        stop_times = pd.read_csv(folder+"stop_times.txt")
        stops = pd.read_csv(folder+"stops.txt")
    
        graphs = {}
        paths = {}
        for line in data.keys():
            try:
                graphs[line],paths[line] = display_line_structure(str(line),routes, trips, stop_times, stops)
            except ValueError:
                print(f"La ligne {line} n'a pas été trouvée.")
                
        def set_default(obj):
            if isinstance(obj, set):
                return list(obj)
            raise TypeError

                
        with open(DATA_FOLDER + "graph.json", "w") as f:
            json.dump(graphs,f,default=set_default)
            
        with open(DATA_FOLDER + "graph_paths.json", "w") as f:
            json.dump(paths,f,default=set_default)
    else:
        with open(DATA_FOLDER + "graph.json", "r") as f:
            graphs = json.load(f)
            
        with open(DATA_FOLDER + "graph_paths.json", "r") as f:
            paths = json.load(f)
            
    
    print(f"Found {len(data)} construction detail links. ")
    if crawl_construction_data:
        data = scrape_data(data,graphs)
        data = {k:v for k,v in data.items() if "construction_list" in v.keys()}
    
        now = datetime.now().strftime("%Y%m%d")
        with open(DATA_FOLDER + f"data_{now}.json", "w") as f:
            json.dump(data,f)
    else:
        with open(DATA_FOLDER + "data.json", "r") as f:
            data = json.load(f)
        for line, details in data.items():
            for work in details["construction_list"]:
                work["stations_concernes"] = get_stations_between(paths[line],work["stations"])
                
        now = datetime.now().strftime("%Y%m%d")
        with open(DATA_FOLDER + f"data_{now}.json", "w", encoding="utf-8") as f:
            json.dump(data,f, ensure_ascii=False)
            
    print("Finished")


if __name__ == "__main__":
    main(generate_graphs=False,crawl_construction_data=True)