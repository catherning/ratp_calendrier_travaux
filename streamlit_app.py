import streamlit as st
import json
import os
from datetime import datetime


# Load data from data.json
data_file_path = os.path.join("data", "data.json")

LINE_LOGOS = {
    "1":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Paris_transit_icons_-_M%C3%A9tro_1.svg/20px-Paris_transit_icons_-_M%C3%A9tro_1.svg.png",
    "2":"https://upload.wikimedia.org/wikipedia/commons/thumb/d/da/Paris_transit_icons_-_M%C3%A9tro_2.svg/20px-Paris_transit_icons_-_M%C3%A9tro_2.svg.png",
    "3":"https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/Paris_transit_icons_-_M%C3%A9tro_3.svg/20px-Paris_transit_icons_-_M%C3%A9tro_3.svg.png",
    "4":"https://upload.wikimedia.org/wikipedia/commons/thumb/7/76/Paris_transit_icons_-_M%C3%A9tro_4.svg/20px-Paris_transit_icons_-_M%C3%A9tro_4.svg.png",
    "5":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/54/Paris_transit_icons_-_M%C3%A9tro_5.svg/20px-Paris_transit_icons_-_M%C3%A9tro_5.svg.png",
    "6":"https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Paris_transit_icons_-_M%C3%A9tro_6.svg/20px-Paris_transit_icons_-_M%C3%A9tro_6.svg.png",
    "7":"https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Paris_transit_icons_-_M%C3%A9tro_7.svg/20px-Paris_transit_icons_-_M%C3%A9tro_7.svg.png",
    "8":"https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Paris_transit_icons_-_M%C3%A9tro_8.svg/20px-Paris_transit_icons_-_M%C3%A9tro_8.svg.png",
    "9":"https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Paris_transit_icons_-_M%C3%A9tro_9.svg/20px-Paris_transit_icons_-_M%C3%A9tro_9.svg.png",
    "10":"https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/Paris_transit_icons_-_M%C3%A9tro_10.svg/20px-Paris_transit_icons_-_M%C3%A9tro_10.svg.png",
    "11":"https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Paris_transit_icons_-_M%C3%A9tro_11.svg/20px-Paris_transit_icons_-_M%C3%A9tro_11.svg.png",
    "12":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Paris_transit_icons_-_M%C3%A9tro_12.svg/20px-Paris_transit_icons_-_M%C3%A9tro_12.svg.png",
    "13":"https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Paris_transit_icons_-_M%C3%A9tro_13.svg/20px-Paris_transit_icons_-_M%C3%A9tro_13.svg.png",
    "14":"https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Paris_transit_icons_-_M%C3%A9tro_14.svg/20px-Paris_transit_icons_-_M%C3%A9tro_14.svg.png",
    "15":"https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Paris_transit_icons_-_M%C3%A9tro_15.svg/20px-Paris_transit_icons_-_M%C3%A9tro_15.svg.png",
    "A":"https://upload.wikimedia.org/wikipedia/commons/4/4a/Paris_transit_icons_-_RER_A.svg",
    "B":"https://upload.wikimedia.org/wikipedia/commons/f/fd/Paris_transit_icons_-_RER_B.svg"
# https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Paris_transit_icons_-_M%C3%A9tro_16.svg/20px-Paris_transit_icons_-_M%C3%A9tro_16.svg.png
}
NUM_COLS = 1

with open(data_file_path, "r") as f:
    data = json.load(f)

st.title("Calendrier des travaux RATP")

# Display construction details by line
for line, line_details in data.items():
    construction_details = line_details["construction_list"]
    num_columns = len(construction_details)

    if construction_details:
        placeholder = st.container()
        col1, col2 = placeholder.columns([1, 20])
        with col1:
            st.image(LINE_LOGOS[line],width=30)
        with col2:
            st.header(f"Ligne {line}")
        
        travaux_unique_name = set()
        count_finished = 0
        
        with st.expander("Détails des travaux", expanded=False):
            for i, construction in enumerate(construction_details):
                date_fin = datetime.strptime(construction['date_fin'], '%Y%m%dT%H%M%S')
                if date_fin<datetime.now():
                    count_finished+=1
                    continue

                name = construction["summary"].split(" - ")[1]
                if name not in travaux_unique_name: 
                    st.subheader(name)
                    st.write(f"Stations: {construction.get('stations', 'N/A')}")
                    travaux_unique_name.add(name)
                    
                st.write(construction["date_text"])
                # st.write(f"Du {datetime.strptime(construction['date_debut'], '%Y%m%dT%H%M%S').strftime('%d/%m/%Y %H:%M')} au {date_fin.strftime('%d/%m/%Y %H:%M')}")
                # https://github.com/im-perativa/streamlit-calendar?tab=readme-ov-file ?
                # Download ICS file and Google Calendar link in same row
                button_cols = st.columns(2)  # Create two columns for the buttons
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
                # placeholder.empty()