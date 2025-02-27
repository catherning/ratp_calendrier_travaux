import streamlit as st
import json
import os
from datetime import datetime


# Load data from data.json
data_file_path = os.path.join("data", "data.json")

LINE_LOGOS = [
    "https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Paris_transit_icons_-_M%C3%A9tro_1.svg/20px-Paris_transit_icons_-_M%C3%A9tro_1.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/d/da/Paris_transit_icons_-_M%C3%A9tro_2.svg/20px-Paris_transit_icons_-_M%C3%A9tro_2.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/Paris_transit_icons_-_M%C3%A9tro_3.svg/20px-Paris_transit_icons_-_M%C3%A9tro_3.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/7/76/Paris_transit_icons_-_M%C3%A9tro_4.svg/20px-Paris_transit_icons_-_M%C3%A9tro_4.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/54/Paris_transit_icons_-_M%C3%A9tro_5.svg/20px-Paris_transit_icons_-_M%C3%A9tro_5.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Paris_transit_icons_-_M%C3%A9tro_6.svg/20px-Paris_transit_icons_-_M%C3%A9tro_6.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Paris_transit_icons_-_M%C3%A9tro_7.svg/20px-Paris_transit_icons_-_M%C3%A9tro_7.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Paris_transit_icons_-_M%C3%A9tro_8.svg/20px-Paris_transit_icons_-_M%C3%A9tro_8.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Paris_transit_icons_-_M%C3%A9tro_9.svg/20px-Paris_transit_icons_-_M%C3%A9tro_9.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/Paris_transit_icons_-_M%C3%A9tro_10.svg/20px-Paris_transit_icons_-_M%C3%A9tro_10.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Paris_transit_icons_-_M%C3%A9tro_11.svg/20px-Paris_transit_icons_-_M%C3%A9tro_11.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Paris_transit_icons_-_M%C3%A9tro_12.svg/20px-Paris_transit_icons_-_M%C3%A9tro_12.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Paris_transit_icons_-_M%C3%A9tro_13.svg/20px-Paris_transit_icons_-_M%C3%A9tro_13.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Paris_transit_icons_-_M%C3%A9tro_14.svg/20px-Paris_transit_icons_-_M%C3%A9tro_14.svg.png",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Paris_transit_icons_-_M%C3%A9tro_15.svg/20px-Paris_transit_icons_-_M%C3%A9tro_15.svg.png",
# https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Paris_transit_icons_-_M%C3%A9tro_16.svg/20px-Paris_transit_icons_-_M%C3%A9tro_16.svg.png
]
NUM_COLS = 1

with open(data_file_path, "r") as f:
    data = json.load(f)

st.title("Calendrier des travaux RATP")

# Display construction details by line
for line, line_details in data.items():
    construction_details = line_details["construction_list"]
    num_columns = len(construction_details)

    if construction_details:
        # st.header(f"Ligne {line}")
        st.image(LINE_LOGOS[int(line)-1],width=30)
        cols = st.columns(min(NUM_COLS, num_columns)) 
        
        for i, construction in enumerate(construction_details):
            col_index = i % NUM_COLS
            with cols[col_index]:
                st.subheader(construction["summary"].split(" - ")[1])
                st.write(f"Du {datetime.strptime(construction['date_debut'], '%Y%m%dT%H%M%S').strftime('%d/%m/%Y %H:%M')} au {datetime.strptime(construction['date_fin'], '%Y%m%dT%H%M%S').strftime('%d/%m/%Y %H:%M')}")
                st.write(f"Stations: {construction.get('stations', 'N/A')}")

                # Download ICS file and Google Calendar link in same row
                button_cols = st.columns(2)  # Create two columns for the buttons
                with button_cols[0]:
                    ics_filename = f"event_ligne_{construction['summary']}.ics"
                    ics_file_path = os.path.join("data", ics_filename)
                    if os.path.exists(ics_file_path):
                        with open(ics_file_path, "rb") as ics_file:
                            st.download_button(
                                label="Download ICS File",
                                data=ics_file,
                                file_name=ics_filename,
                                mime="text/calendar",
                                key=f"ics_{line}_{construction['summary']}_{i}"  # Unique key
                            )

                with button_cols[1]:
                    google_calendar_url = construction.get("google_calendar")
                    if google_calendar_url:
                        st.link_button("Add to Google Calendar", google_calendar_url)