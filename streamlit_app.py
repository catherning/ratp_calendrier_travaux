import streamlit as st
import json
import os
from datetime import datetime
from streamlit_calendar import calendar
# import streamlit.components.v1 as components

# Load data from data.json
data_file_path = os.path.join("data", "data.json")

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
first = True
calendar_events = []
resources = []
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
    """
    cal = calendar(
        events=calendar_events,
        options=calendar_options,
        custom_css=custom_css,
        key='calendar', # Assign a widget key to prevent state loss
        )
    return cal

# def scroll(element_id):
#     scroll_code = f"""
#         <script>
#             var element = window.parent.document.getElementById("{element_id}");
#             element.scrollIntoView({{behavior: 'smooth'}});
#         </script>
#     """.format(element_id)
#     return scroll_code

with open(data_file_path, "r") as f:
    data = json.load(f)

st.title("Calendrier des travaux RATP")

with st.sidebar:
    st.text("Cette page présente les prochains travaux qui auront lieu sur les différentes lignes du métro/RER parisien.")
    st.markdown("**Des boutons sont disponibles pour récupérer les dates de travaux sous forme d'événements Outlook ou Google Calendar à ajouter dans votre calendrier.**")

# Display construction details by line
for line, line_details in data.items():
    construction_details = line_details["construction_list"]
    num_columns = len(construction_details)

    if construction_details:
        placeholder = st.container()
        col1, col2, col3 = placeholder.columns([1, 12,5])
        with col1:
            st.image(LINE_INFO[line]["logo"])
        with col2:
            st.header(f"Ligne {line}",anchor=line)
        with col3:
            st.link_button("Page de référence RATP", line_details["link"],type="tertiary")
        
        travaux_unique_name = set()
        count_finished = 0
        
        with st.expander("Détails des travaux", expanded=first,):
            for i, construction in enumerate(construction_details):
                
                
                date_fin = datetime.strptime(construction['date_fin'], '%Y%m%dT%H%M%S')
                if date_fin<datetime.now():
                    count_finished+=1
                    continue
                else:
                    first=False

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
                        "line":line,
                        "resourceId": name,
                        "backgroundColor":LINE_INFO[line]["couleur"],
                        "borderColor":LINE_INFO[line]["couleur"]
                    },
                )
                
                st.write(construction["date_text"])
                
                # Download ICS file and Google Calendar link in same row
                button_cols = st.columns([2,5])  # Create two columns for the buttons
                with button_cols[0]:
                    ics_filename = f"event_ligne_{construction['summary']}_{i+1}.ics"
                    ics_file_path = os.path.join("data", ics_filename)
                    if os.path.exists(ics_file_path):
                        with open(ics_file_path, "rb") as ics_file:
                            st.download_button(
                                label="Ajouter à Outlook",
                                data=ics_file,
                                file_name=ics_filename,
                                mime="text/calendar",
                                key=f"ics_{line}_{construction['summary']}_{i}"
                            )

                with button_cols[1]:
                    google_calendar_url = construction.get("google_calendar")
                    if google_calendar_url:
                        st.link_button("Ajouter à Google Calendar", google_calendar_url)

            if count_finished==len(construction_details):
                placeholder.text("Pas de travaux futurs identifiés.")

cal_event = create_st_calendar(calendar_events,resources)
# if cal_event and cal_event["callback"] =="eventClick":
#     components.html(scroll(cal_event["eventClick"]["event"]["extendedProps"]["line"]))