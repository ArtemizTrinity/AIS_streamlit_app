import streamlit as st
import requests
import zipfile
import os
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
import math
import tempfile

# Constants
ZIP_URL = "https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2020/AIS_2020_06_27.zip"
EXTRACT_PATH = tempfile.mkdtemp()

st.set_page_config(page_title="AIS Vessel Explorer", layout="wide")
st.title("NOAA AIS Vessel Explorer - June 27, 2020")

# Step 1: Download and extract the ZIP file
@st.cache_data
def download_and_extract_zip():
    zip_path = os.path.join(EXTRACT_PATH, "AIS_2020_06_27.zip")
    csv_file = None

    if not os.path.exists(zip_path):
        try:
            st.info("Downloading AIS ZIP file...")
            response = requests.get(ZIP_URL, timeout=60)
            response.raise_for_status()
            with open(zip_path, "wb") as f:
                f.write(response.content)
            st.success("Download complete.")
        except requests.exceptions.RequestException as e:
            st.error(f"Download failed: {e}")
            st.stop()

    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            for name in z.namelist():
                if name.endswith('.csv'):
                    csv_file = name
                    z.extract(name, EXTRACT_PATH)
                    break
        if csv_file is None:
            st.error("No CSV file found in ZIP archive.")
            st.stop()
    except zipfile.BadZipFile as e:
        st.error(f"Invalid ZIP file: {e}")
        st.stop()

    return os.path.join(EXTRACT_PATH, csv_file)

# Step 2: Load the CSV file
@st.cache_data
def load_data(csv_path):
    try:
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Failed to load CSV file: {e}")
        st.stop()

csv_path = download_and_extract_zip()
df = load_data(csv_path)

# Step 3: Filter vessels longer than 200 meters
df['Length'] = pd.to_numeric(df['Length'], errors='coerce')
long_vessels = df[df['Length'] > 200]
vessel_names = sorted(long_vessels['VesselName'].dropna().unique())

selected_vessel = st.sidebar.selectbox("Select a vessel (>200m length)", vessel_names)

# Step 4: Isolate selected vessel data
vessel_df = df[df['VesselName'] == selected_vessel].copy()
vessel_df = vessel_df.sort_values("BaseDateTime")

# Step 5: Transformations
vessel_df['BaseDateTime'] = pd.to_datetime(vessel_df['BaseDateTime'], errors='coerce')
vessel_df['FormattedTime'] = vessel_df['BaseDateTime'].dt.strftime('%m/%d/%Y %H:%M:%S')
vessel_df['VesselName'] = vessel_df['VesselName'].str.lower()
vessel_df['Speed_mps'] = vessel_df['SOG'] * 0.514444
vessel_df['TimeDelta_s'] = vessel_df['BaseDateTime'].diff().dt.total_seconds().fillna(0)
vessel_df['Acceleration_mps2'] = vessel_df['Speed_mps'].diff() / vessel_df['TimeDelta_s'].replace(0, 1)

# Step 6: Save vessel data
safe_vessel_name = selected_vessel.lower().replace(" ", "_")
output_file = os.path.join(EXTRACT_PATH, f"{safe_vessel_name}_data.csv")
vessel_df.to_csv(output_file, index=False)
st.success()

# Step 7: Display map
st.subheader("Vessel Track Map")
if not vessel_df.empty:
    m = folium.Map(location=[vessel_df['LAT'].mean(), vessel_df['LON'].mean()], zoom_start=6)
    for _, row in vessel_df.iterrows():
        folium.CircleMarker(
            location=(row['LAT'], row['LON']),
            radius=3,
            popup=row['FormattedTime'],
            fill=True
        ).add_to(m)
    st_data = st_folium(m, width=700, height=500)
else:
    st.warning("No location data available for this vessel.")

# Step 9: Vessel Metadata
st.subheader("Vessel Metadata")
metadata_fields = ['MMSI', 'IMO', 'CallSign', 'VesselType', 'Length', 'Width', 'Draft', 'Cargo']
st.write(vessel_df[metadata_fields].iloc[0])

# Step 10: Vessel Profile (Open-source stub)
def get_vessel_profile(imo):
    if pd.isna(imo):
        return "No IMO number available to fetch profile."
    return f"""
    This vessel (IMO: {imo}) is likely a commercial vessel exceeding 200 meters.
    You can search this IMO on open databases such as:
    - https://www.marinetraffic.com/
    - https://www.equasis.org/
    """

st.subheader("Open-Source Vessel Profile")
st.markdown(get_vessel_profile(vessel_df['IMO'].iloc[0]))

# Step 11: Display DataFrame
st.subheader("Full Data Table")
st.dataframe(vessel_df.reset_index(drop=True))
