# import requests
import os
import json
import csv
from pathlib import Path
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime
from dotenv import load_dotenv
from litellm import completion
import uuid
import pandas as pd
import logging
from utils import is_running_in_docker

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

from seleniumbase import SB

DATE_FORMAT = "%Y%m%dT%H%M%S"
DATA_FOLDER = "../data/"


def upload_outputs_to_gcs(data_file_path: str, ics_folder_path: str) -> None:
    """Upload generated artifacts to GCS when running in Docker/Cloud Run."""
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        logger.warning("GCS_BUCKET_NAME not set. Skipping GCS upload.")
        return

    try:
        from google.cloud import storage
    except ImportError:
        logger.error("google-cloud-storage is not installed. Skipping GCS upload.")
        return

    run_id = datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    gcs_prefix = os.getenv("GCS_BUCKET_PREFIX", "ratp_travaux").strip("/")
    run_prefix = f"{gcs_prefix}/runs/{run_id}"

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # Upload snapshot JSON
    data_filename = os.path.basename(data_file_path)
    bucket.blob(f"{run_prefix}/{data_filename}").upload_from_filename(data_file_path)

    # Upload ICS files for this run
    ics_dir = Path(ics_folder_path)
    if ics_dir.exists() and ics_dir.is_dir():
        for ics_file in ics_dir.glob("*.ics"):
            bucket.blob(f"{run_prefix}/event_ics/{ics_file.name}").upload_from_filename(str(ics_file))

    # Write metadata for traceability
    metadata = {
        "run_id": run_id,
        # "generated_at": datetime.now(datetime.timezone.utc).isoformat(timespec="seconds") + "Z",
        # "data_file": data_filename,
    }
    # bucket.blob(f"{run_prefix}/metadata.json").upload_from_string(
    #     json.dumps(metadata), content_type="application/json"
    # )

    # Update latest pointer for frontend readers
    bucket.blob(f"{gcs_prefix}/latest.json").upload_from_string(
        json.dumps(metadata), content_type="application/json"
    )
    logger.info(f"Uploaded run artifacts to gs://{bucket_name}/{run_prefix}")



def get_llm_json_response(prompt,model="mistral/mistral-small-latest") -> str:
    # TODO: use Vertex when deployed in GCP ?
    messages = [{ "content": prompt,"role": "user"}]

    try:
        response_dict = completion(model=model, messages=messages)
        response_dict = response_dict["choices"][0]["message"]["content"]
        logger.info(f"LLM response: {response_dict}")
    except Exception as e:
        logger.error(f"Error occurred while fetching LLM response: {e}")
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
    logger.info(f"Retrying construction detail extraction due to error: {error_msg}")
    logger.info(f"Original construction_details that failed: {construction_details}")
    
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
            response_lines = response.split("```") #BUG: doesn't work with LLM local fallback
            for el in response_lines:
                if el.strip().startswith("json"):
                    fixed_details = json.loads(el[4:])
                    logger.info(f"Successfully corrected construction details on attempt {attempt + 1}")
                    return fixed_details
            logger.info(f"Retry attempt {attempt + 1}: Could not extract JSON from response")
        except Exception as e:
            logger.error(f"Retry attempt {attempt + 1} failed: {e}")
            continue
    
    logger.error("All retry attempts failed. Skipping this construction detail.")
    return None

def parse_construction_page(source_text,path):
    """Parses a single construction page to extract dates, stations, and descriptions. """
    soup = BeautifulSoup(source_text, 'html.parser')

    all_works = ""

    accroche_div = soup.find('div', class_='article__accroche-content')
    if accroche_div is not None:
        accroche_text = accroche_div.get_text(" ", strip=True).lower()
        if "pas de travaux" in accroche_text:
            return None

        squeezed_blocks = [text.get_text(strip=True) for text in soup.find_all("div", class_="squeezecnt")]
        all_works = " ||| ".join(squeezed_blocks).strip()
    else:
        logger.warning("Could not find expected RATP structure. Trying bonjour-ratp structure.")

    if not all_works:
        bonjour_container = soup.select_one("div.er2njhn.h1hztsyi")
        if bonjour_container is not None:
            all_works = bonjour_container.get_text(" ", strip=True)

    if not all_works:
        logger.error("Could not extract construction content from page; skipping this line.")
        return None

    # Prompt compact, mais strict sur le format pour stabiliser la sortie du LLM.
    prompt = (
        "Tu extrais des infos de travaux RATP et retournes une liste JSON d'evenements. "
        "Reponds UNIQUEMENT avec un bloc ```json ... ```, sans texte hors du bloc. "
        "Chaque evenement contient obligatoirement: date_debut, date_fin, date_text, summary, stations. "
        f"date_debut et date_fin doivent etre au format {DATE_FORMAT}. "
        "date_text est une paraphrase humaine du passage source (inclus/exclus, heures et nuances respectees). "
        "summary doit etre compatible nom de fichier (interdit: / et |). "
        "stations: "
        "- liste de stations => separees par virgule ',' ; "
        "- entre 2 stations => separees par ' | '. "
        "Si recurrence utile, ajoute rrule (objet) avec uniquement ces cles possibles: "
        "freq (daily|weekly), byday (SU,MO,TU,WE,TH,FR,SA sans espaces), interval (int), until (datetime), count (int). "
        "Ne jamais utiliser la cle BYWEEKDAY. "
        "Si frequence non reguliere, cree plusieurs evenements plutot qu'une rrule incorrecte. "
        "Essaie de minimiser le nombre d'evenements en fusionnant les plages compatibles. "
        "Si le texte indique qu'il n'y a pas de travaux, retourne []. "
        "Exemple recurrence hebdo: [{\"date_debut\":\"20250105T220000\",\"date_fin\":\"20250106T060000\",\"date_text\":\"Tous les dimanches du 5 janvier au 16 fevrier 2025 a partir de 22h\",\"summary\":\"Ligne 8 - Travaux sur toute la ligne\",\"stations\":\"toute la ligne\",\"rrule\":{\"freq\":\"weekly\",\"byday\":\"SU\",\"until\":\"20250216T235900\"}}]. "
        "Exemple dates irregulieres: [{\"date_debut\":\"20250412T000000\",\"date_fin\":\"20250413T230000\",\"date_text\":\"Les 12 et 13 avril 2025\",\"summary\":\"Ligne 6 - Travaux entre Daumesnil et Nation\",\"stations\":\"Daumesnil | Nation\"},{\"date_debut\":\"20250518T000000\",\"date_fin\":\"20250519T000000\",\"date_text\":\"Le 18 mai 2025\",\"summary\":\"Ligne 6 - Travaux entre Daumesnil et Nation\",\"stations\":\"Daumesnil | Nation\"}]. "
        f"Texte a parser: {all_works}"
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
            logger.error(f'Attempt {attempts}: {e}')
            # Log error or take corrective measures

    if success:
        for i in range(len(details)):
            details[i]["summary"] = details[i]["summary"].replace("/","-") # ne pas avoir de / entre les stations
            # details[i]["stations_concernes"] = get_stations_between(path,details[i]["stations"])
            # details[i]["stations_concernes"] = get_stations_between(path,details[i]["station_start"],details[i]["station_end"])
            logger.info(f'Construction work information extracted: {details[i]}')
    else:
        logger.error('All attempts failed.')
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
        try:
            construction_details["rrule"]["byday"] = construction_details["rrule"]["byday"].replace(" ","") 
        except AttributeError:
            construction_details["rrule"]["byday"] = ",".join(construction_details["rrule"]["byday"])
            
        rule = construction_details["rrule"].copy()
        rule["byday"] = rule["byday"].split(",") 
        try:
            rule["until"]=datetime.strptime(rule["until"],DATE_FORMAT)
        except KeyError:
            pass
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
    
    logger.info(f"Structure de la ligne {route_name}:")
    for i, path in enumerate(paths):
        logger.info(f"Branche {i+1}:")
        for j, (station_id, station_name) in enumerate(path):
            logger.info(f"  {j+1:2d}. {station_name}")
    
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

    
def scrape_data(data,graphs):
    # Use SeleniumBase in headless mode directly; do not rely on an external X display.
    with SB(uc=True, headless=True) as sb:
        
        first_bonjour_ratp_page = True
        for i,(line_name,line_info) in enumerate(data.items()):
            logger.info(f"Processing line {line_name} with URL: {line_info['link']} ")
            sb.uc_open(line_info["link"])

            # Handle the cookie banner
            if i==0:
                try:
                    sb.wait_for_element('button[id="popin_tc_privacy_button_3"]', timeout=5)
                    sb.uc_click('button[id="popin_tc_privacy_button_3"]')
                    logger.info("Cookie banner accepted. ")
                except Exception as e:
                    logger.warning("Cookie banner not found or could not be clicked: %s", e)
            elif "bonjour-ratp" in line_info["link"] and first_bonjour_ratp_page:
                try:
                    sb.wait_for_element('button[id="didomi-notice-agree-button"]', timeout=5)
                    sb.uc_click('button[id="didomi-notice-agree-button"]')
                    logger.info("Cookie banner accepted. ")
                except Exception as e:
                    logger.warning("Cookie banner not found or could not be clicked: %s", e)
                first_bonjour_ratp_page = False

            # Ensure the page is fully loaded
            try:
                sb.wait_for_element("body", timeout=10)
                logger.info(f"Page for line {line_name} loaded successfully. ")
            except Exception as e:
                logger.error("Failed to load the main page: %s", e)

            # Extract the page source and parse it with BeautifulSoup
            page_source = sb.get_page_source()

            result = parse_construction_page(page_source,graphs[str(line_name)])

            if result:
                details, all_works = result
                # # Step 3: Create ICS files
                # logger.info("Creating ICS files... ")
                for j,construction_details in enumerate(details):
                    try:
                        create_ics_file(construction_details, DATA_FOLDER + "event_ics", f"event_ligne_{construction_details['summary']}_{j+1}")
                        details[j]["google_calendar"] = create_google_event(construction_details)
                    except Exception as e:
                        logger.error("L'event n'a pas pu être créé! Syntaxe incorrecte: %s", e)
                        logger.error("Construction details that caused the error: %s", construction_details)
                        # Retry with LLM feedback
                        fixed_details = retry_construction_detail_with_error(construction_details, e, all_works)
                        if fixed_details:
                            try:
                                create_ics_file(fixed_details, DATA_FOLDER + "event_ics", f"event_ligne_{fixed_details['summary']}_{j+1}")
                                details[j] = fixed_details
                                details[j]["google_calendar"] = create_google_event(fixed_details)
                            except Exception as retry_error:
                                logger.error(f"Retry failed for construction detail: {retry_error}")
                        else:
                            logger.error(f"Could not fix construction detail via LLM retry. Skipping.")
                        
                data[line_name]["construction_list"] = details
            # else:
            #     no_work.append(i)
    return data
    

def main(generate_graphs=False,crawl_construction_data=True) -> None:
    # TODO: tester les pages au format https://www.bonjour-ratp.fr/actualites/articles/bulletin-travaux-25-avril/
    # et https://www.ratp.fr/les-travaux-en-cours-et-a-venir
    # data = {}
    data = {i:{"link":f"https://www.ratp.fr/decouvrir/coulisses/modernisation-du-reseau/metro-ligne-{i}-travaux"} for i in range(1, 15)}
    data["A"] = {"link":"https://www.ratp.fr/decouvrir/coulisses/modernisation-du-reseau/rer-a-travaux"}
    data["B"] = {"link":"https://www.ratp.fr/decouvrir/coulisses/modernisation-du-reseau/rer-b-travaux"}
    data["C"] = {"link":"https://www.bonjour-ratp.fr/actualites/articles/ligne-rerc-dates-et-horaires-des-fermetures/"}
    data["D"] = {"link":"https://www.bonjour-ratp.fr/actualites/articles/ligne-rerd-dates-et-horaires-des-fermetures/"}

    
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
                logger.error(f"La ligne {line} n'a pas été trouvée.")
                
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
            
    
    logger.info(f"Found {len(data)} construction detail links.")
    data_output_path = None
    if crawl_construction_data:
        data = scrape_data(data,graphs)
        data = {k:v for k,v in data.items() if "construction_list" in v.keys()}
    
        # now = datetime.now().strftime("%Y%m%d")
        data_output_path = DATA_FOLDER + f"data.json"
        with open(data_output_path, "w") as f:
            json.dump(data,f)
    else:
        with open(DATA_FOLDER + "data.json", "r") as f:
            data = json.load(f)
        for line, details in data.items():
            for work in details["construction_list"]:
                work["stations_concernes"] = get_stations_between(paths[line],work["stations"])
                
        # now = datetime.now().strftime("%Y%m%d")
        data_output_path = DATA_FOLDER + f"data.json"
        with open(data_output_path, "w", encoding="utf-8") as f:
            json.dump(data,f, ensure_ascii=False)

    if is_running_in_docker() and data_output_path:
        upload_outputs_to_gcs(
            data_file_path=data_output_path,
            ics_folder_path=DATA_FOLDER + "event_ics",
        )
            
    logger.info("Finished")


if __name__ == "__main__":
    main(generate_graphs=False,crawl_construction_data=True)