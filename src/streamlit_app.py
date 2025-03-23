import os
from pathlib import Path
import json

from datetime import datetime
import streamlit as st
from streamlit_calendar import calendar
# import streamlit.components.v1 as components

if os.getenv('STREAMLIT_SERVER') == 'true':
    os.chdir("/mount/src/ratp_calendrier_travaux/src")

st.set_page_config(
    page_title="Travaux RATP",
    layout="wide",
)

LINE_INFO = {
    "1": {"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Paris_transit_icons_-_M%C3%A9tro_1.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_1.svg.png","couleur":  "#FFCE00"},
    "2": {"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/d/da/Paris_transit_icons_-_M%C3%A9tro_2.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_2.svg.png","couleur":  "#0064B0"},
    "3": {"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/Paris_transit_icons_-_M%C3%A9tro_3.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_3.svg.png","couleur":  "#9F9825"},
    "4": {"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/7/76/Paris_transit_icons_-_M%C3%A9tro_4.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_4.svg.png","couleur":  "#C04191"},
    "5": {"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/54/Paris_transit_icons_-_M%C3%A9tro_5.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_5.svg.png","couleur":  "#F28E42"},
    "6": {"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Paris_transit_icons_-_M%C3%A9tro_6.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_6.svg.png","couleur":  "#83C491"},
    "7": {"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Paris_transit_icons_-_M%C3%A9tro_7.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_7.svg.png","couleur":  "#F3A4BA"},
    "8": {"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Paris_transit_icons_-_M%C3%A9tro_8.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_8.svg.png","couleur":  "#CEADD2"},
    "9": {"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Paris_transit_icons_-_M%C3%A9tro_9.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_9.svg.png","couleur":  "#D5C900"},
    "10":{"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/Paris_transit_icons_-_M%C3%A9tro_10.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_10.svg.png","couleur":"#E3B32A"},
    "11":{"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Paris_transit_icons_-_M%C3%A9tro_11.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_11.svg.png","couleur":"#8D5E2A"},
    "12":{"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Paris_transit_icons_-_M%C3%A9tro_12.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_12.svg.png","couleur":"#00814F"},
    "13":{"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Paris_transit_icons_-_M%C3%A9tro_13.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_13.svg.png","couleur":"#98D4E2"},
    "14":{"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Paris_transit_icons_-_M%C3%A9tro_14.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_14.svg.png","couleur":"#662483"},
    "15":{"logo":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Paris_transit_icons_-_M%C3%A9tro_15.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_15.svg.png","couleur":"#B90845"},
    "A": {"logo":"https://upload.wikimedia.org/wikipedia/commons/4/4a/Paris_transit_icons_-_RER_A.svg","couleur":"#E3051C"},
    "B": {"logo":"https://upload.wikimedia.org/wikipedia/commons/f/fd/Paris_transit_icons_-_RER_B.svg","couleur":"#5291CE"},
# https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Paris_transit_icons_-_M%C3%A9tro_16.svg/2048px-Paris_transit_icons_-_M%C3%A9tro_16.svg.png
}

NUM_COLS = 1
FIRST = True

DATA_FOLDER = "../data"
data_file_path = os.path.join(DATA_FOLDER, "data_20250323.json")


def filter_gare(gare,data): # ou construction_details union par ligne
    pass
    # Then
    # if gare in stations:
    #     return True


def get_stations_for_line(data, line):
    if line not in data:
        return []
    
    # Extraire toutes les stations de tous les chemins
    all_stations = []
    for path in data[line]["paths"]:
        all_stations.extend([(station_id, station_name) for station_id, station_name in path])
    
    # Éliminer les doublons tout en préservant l'ordre
    unique_stations = []
    unique_ids = set()
    for station_id, station_name in all_stations:
        if station_id not in unique_ids:
            unique_stations.append((station_id, station_name))
            unique_ids.add(station_id)
    
    return unique_stations

# Fonction pour trouver les travaux qui concernent une station
def find_travaux_for_station(data, line, station_id):
    if line not in data or "travaux" not in data[line]:
        return []
    
    return [
        travail for travail in data[line]["travaux"]
        if station_id in travail["stations_concernees"]
    ]

def create_st_calendar(calendar_events,resources):
    calendar_options = {
        "editable": False,
        "selectable": True,
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "dayGridMonth,resourceTimelineYear",
        },
        "initialView": "dayGridMonth",
        "resourceGroupField": "line",
        "resources": resources
    }
    custom_css="""
        .fc-event-past {
            opacity: 0.8;
        }
        .fc-event-time {
            font-style: italic;
        }
        .fc-event-title {
            font-weight: 700;
        }
        .fc-toolbar-title {
            font-size: 2rem;
        }
        .fc-button {
            background-color:#003ca6;
        }
    """
    cal = calendar(
        events=calendar_events,
        options=calendar_options,
        custom_css=custom_css,
        key='calendar', # Assign a widget key to prevent state loss
        )
    return cal


# Display construction details by line
def show_dl_buttons(line, construction_id, construction_summary,google_link,additional_key=""):
    button_cols = st.columns([1,5])  # Create two columns for the buttons
    with button_cols[0]:
        ics_filename = f"event_ligne_{construction_summary}_{construction_id+1}.ics"
        ics_file_path = os.path.join(DATA_FOLDER, "event_ics/", ics_filename)
        if os.path.exists(ics_file_path):
            with open(ics_file_path, "rb") as ics_file:
                st.download_button(
                                label="![Outlook](https://upload.wikimedia.org/wikipedia/commons/thumb/d/df/Microsoft_Office_Outlook_%282018%E2%80%93present%29.svg/826px-Microsoft_Office_Outlook_%282018%E2%80%93present%29.svg.png) Ajouter à Outlook",
                                data=ics_file,
                                file_name=ics_filename,
                                mime="text/calendar",
                                key=f"ics_{line}_{construction_summary}_{construction_id}" + additional_key
                            )

    with button_cols[1]:
        if google_link:
            st.link_button("![Google](https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Google_Calendar_icon_%282020%29.svg/2048px-Google_Calendar_icon_%282020%29.svg.png) Ajouter à Google Calendar", google_link)

def create_streamlit_calendar_event(LINE_INFO, calendar_events, resources, line, travaux_unique_name, construction,construction_id):
    name = construction["summary"].split(" - ")[1]
    if name not in travaux_unique_name: 
        st.subheader(name)
        travaux_unique_name.add(name)
        resources.append({"id": name, "line": f"Ligne {line}", "title": name})
                    
    calendar_events.append(
                            {
                        "title": construction["summary"],
                        "start": construction["date_debut"],
                        "end": construction["date_fin"],
                        "resourceId": name,
                        "backgroundColor":LINE_INFO[line]["couleur"],
                        "borderColor":LINE_INFO[line]["couleur"],
                        "line":line,
                        "construction_id":construction_id,
                        "google_calendar":construction.get("google_calendar"),
                    },
                )

def create_line_header(LINE_INFO, line, line_details):
    col1, col2, col3 = st.columns([1, 12,5],vertical_alignment="center")
    with col1:
        st.image(LINE_INFO[line]["logo"],width=60)
    with col2:
        st.header(f"Ligne {line}",anchor=line)
    with col3:
        st.link_button("Page de référence RATP", line_details["link"],type="tertiary")

def main():

    with open(data_file_path, "r") as f:
        data = json.load(f)

    if 'expand_all' not in st.session_state:
        st.session_state.expand_all = False

    st.title("Calendrier des travaux RATP")

    with st.sidebar:
        st.header("Présentation")
        st.text("Cette page présente les prochains travaux qui auront lieu sur les différentes lignes du métro/RER (A et B uniquement) parisien.")
        st.markdown("**Des boutons sont disponibles pour récupérer les dates de travaux sous forme d'événements Outlook ou Google Calendar à ajouter dans votre calendrier. Vous pouvez également cliquer sur un événement du calendrier pour retrouver ces boutons.**")
        st.warning("Les informations des événements sont partiellement interprétées et générées par l'IA MistralAI  et peuvent contenir des inexactitudes. Veuillez vérifier les détails auprès des sources officielles de la RATP.")
        st.warning("Cette application n'est pas affiliée à la RATP ou la SNCF, ni soutenues par elles. Il s'agit d'un projet démo indépendant partant d'un besoin personnel.")
        st.markdown("*Date de dernière mise à jour des données: 18/02/2025*")
    
    
    # Premier niveau de filtre : sélection de la ligne
    
    calendar_events = []
    resources = []
    no_work_lines = list(LINE_INFO.keys())
    selected_line = st.selectbox("Sélectionnez une ligne", no_work_lines)
    
    if selected_line:
            # Obtenir les stations pour la ligne sélectionnée
            stations = get_stations_for_line(data, selected_line)
            station_names = [station[1] for station in stations]  # Noms des stations pour l'affichage
            station_ids = [station[0] for station in stations]    # IDs des stations pour le traitement
            
            # Deuxième niveau de filtre : sélection de la station
            selected_station_index = st.selectbox(
                "Sélectionnez une station", 
                range(len(station_names)),
                format_func=lambda i: station_names[i]
            )
            
            if selected_station_index is not None:
                selected_station_id = station_ids[selected_station_index]
                selected_station_name = station_names[selected_station_index]
                
                # Trouver les travaux concernant cette station
                travaux = find_travaux_for_station(data, selected_line, selected_station_id)
                
                # Afficher les résultats
                st.subheader(f"Travaux concernant la station {selected_station_name}")
                
                if travaux:
                    for travail in travaux:
                        with st.expander(f"{travail['description']} ({travail['date_debut']} - {travail['date_fin']})"):
                            st.write(f"**Période**: Du {travail['date_debut']} au {travail['date_fin']}")
                            
                            # Calculer les stations concernées (noms)
                            stations_names = []
                            for s_id in travail['stations_concernees']:
                                for idx, (station_id, station_name) in enumerate(stations):
                                    if station_id == s_id:
                                        stations_names.append(station_name)
                                        break
                            
                            st.write(f"**Stations concernées**: {', '.join(stations_names)}")
                            
                            # Bouton de téléchargement
                            st.markdown(f"[Télécharger le calendrier ICS]({travail['download_link']})")
                else:
                    st.info("Aucun travaux ne concerne cette station actuellement.")
    
    
    # Show all works
    for line, line_details in data.items():
        construction_details = line_details["construction_list"]
        
        # Check if there are any future construction details
        future_events_exist = False
        for construction in construction_details:
            date_fin = datetime.strptime(construction['date_fin'], '%Y%m%dT%H%M%S')
            if date_fin >= datetime.now():
                future_events_exist = True
                no_work_lines.remove(line)
                break

        if future_events_exist:
            create_line_header(LINE_INFO, line, line_details)
            
            travaux_unique_name = set()
            
            with st.popover(f"![logo]({LINE_INFO[line]["logo"]}) Détails des travaux",use_container_width =True):#, expanded=st.session_state.expand_all):
                for i, construction in enumerate(construction_details):
                    
                    # Filter out finished construction work
                    date_fin = datetime.strptime(construction['date_fin'], '%Y%m%dT%H%M%S')
                    if date_fin<datetime.now():
                        continue

                    create_streamlit_calendar_event(LINE_INFO, calendar_events, resources, line, travaux_unique_name, construction,i)
                    
                    st.write(construction["date_text"])
                    
                    # Download ICS file and Google Calendar link in same row
                    show_dl_buttons(line, i, construction.get("summary"),construction.get("google_calendar"))
            
    st.write("")
    st.write("---")
    st.write("")
    st.header("Vue calendaire")

    cal_event = create_st_calendar(calendar_events,resources)
    if cal_event and cal_event["callback"] =="eventClick":
        line = cal_event["eventClick"]["event"]["extendedProps"]["line"]
        construction_id = cal_event["eventClick"]["event"]["extendedProps"]["construction_id"]
        summary = cal_event["eventClick"]["event"]["title"]
        google_calendar = cal_event["eventClick"]["event"]["extendedProps"]["google_calendar"]
        st.subheader(summary)
        show_dl_buttons(line, construction_id, summary,google_calendar,additional_key="2")
        
    st.write("---")
    st.header("Lignes sans futurs travaux")
    cols = st.columns(len(no_work_lines))
    for i,col in enumerate(cols):
        col.image(LINE_INFO[no_work_lines[i]]["logo"],width=40)
    
    
if __name__=="__main__":
    main()