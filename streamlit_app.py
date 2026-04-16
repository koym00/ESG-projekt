"""
Streamlit Web Application for Meteorological Station Analysis and ESG Flood Risk
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import zipfile
import csv
import math
import io
import os
import folium
import random
import povodne
import geopandas as gpd
import building_search
import joblib
import numpy as np
import base64

from pathlib import Path
from datetime import datetime, timedelta
from streamlit_folium import st_folium
from shapely.geometry import Point
from street_view import display_street_views

# Configuration
ZIP_PATH = "temp/Metadata/meta1.zip"
CSV_FILENAME = "meta1.csv"
META2_ZIP_PATH = "temp/Metadata/meta2.zip"
META2_CSV_FILENAME = "meta2.csv"
TEMPERATURE_DIR = "temp/Data/Temperature"

MAPA_Q5 = "temp/D01_ZaplUzemi5Vody.shp"
MAPA_Q20 = "temp/D02_ZaplUzemi20vody.shp"
MAPA_Q100 = "temp/D03_ZaplUzemi100vody.shp"

GOOGLE_MAPS_API_KEY = "AIzaSyC_LQfNXfBwx3pgbHgWewjngUp-7jMKoIs"
EARTH_RADIUS_KM = 6371


def get_image_base64(path):
    with open(path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()


img_base64 = get_image_base64("photo_team_logo1.png")

st.markdown(
    f"""
    <style>
    .hero-container {{
        width: 100%;
        display: flex;
        justify-content: center;
        margin-top: -80px;
    }}
    .fading-logo {{
        width: 100%;
        max-width: 100px;
        mask-image: linear-gradient(to bottom, rgba(0,0,0,1) 70%, rgba(0,0,0,0) 100%);
        -webkit-mask-image: linear-gradient(to bottom, rgba(0,0,0,1) 80%, rgba(0,0,0,0) 100%);
    }}
    div[data-baseweb="input"] {{
        border: 1px solid transparent;
        transition: border-color 0.2s ease-in-out;
    }}
    .stMetric label {{ color: #4B0082 !important; }}
    .stMetric div[data-testid="stMetricValue"] {{ color: #4B0082 !important; }}
    div[data-testid="stNotification"] {{
        background-color: rgba(75, 0, 130, 0.1);
        color: #4B0082;
        border: 1px solid #4B0082;
    }}
    div.stButton > button {{
        background-color: #4B0082 !important;
        border: 1px solid #4B0082 !important;
    }}

    .st-emotion-cache-1y4p8pa {{
        max-width: 100% !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }}

    iframe[title="streamlit_folium.st_folium"] {{
        width: 100% !important;
    }}

    [data-testid="stMainBlockContainer"] {{
        max-width: 97% !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }}

    /* Barva progres baru (vnitřní naplněná část) */
    div[data-testid="stProgress"] > div > div > div > div {{
        background-color: #4B0082 !important;
    }}
    
    /* Volitelně: Barva pozadí progres baru (ta světlá linka) */
    div[data-testid="stProgress"] > div > div {{
        background-color: rgba(75, 0, 130, 0.1) !important;
    }}

    </style>
    <div class="hero-container">
        <img src="data:image/png;base64,{img_base64}" class="fading-logo">
    </div>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_temperature_stations():
    temperature_stations = set()
    try:
        with zipfile.ZipFile(META2_ZIP_PATH, "r") as zf:
            with zf.open(META2_CSV_FILENAME, "r") as csvfile:
                text_file = io.TextIOWrapper(csvfile, encoding="utf-8")
                reader = csv.reader(text_file, delimiter=",")
                next(reader, None)
                for row in reader:
                    if len(row) < 5:
                        continue
                    try:
                        wsi_code = row[1]
                        element = row[4]
                        if element == "T":
                            temperature_stations.add(wsi_code)
                    except (ValueError, IndexError):
                        continue
    except Exception as e:
        st.warning(f"Error reading temperature capability data: {e}. Proceeding without filtering.")
    return temperature_stations


@st.cache_data
def load_station_metadata(temperature_stations):
    stations = []
    try:
        with zipfile.ZipFile(ZIP_PATH, "r") as zf:
            with zf.open(CSV_FILENAME, "r") as csvfile:
                text_file = io.TextIOWrapper(csvfile, encoding="utf-8")
                reader = csv.reader(text_file, delimiter=",")
                next(reader, None)
                for row in reader:
                    if len(row) < 8:
                        continue
                    try:
                        wsi_code = row[0]
                        end_date = row[3]
                        if not end_date.startswith("3999"):
                            continue
                        if temperature_stations and wsi_code not in temperature_stations:
                            continue
                        full_name = row[4]
                        geogr1 = float(row[5])
                        geogr2 = float(row[6])
                        elevation = row[7]
                        stations.append({
                            "wsi_code": wsi_code,
                            "name": full_name,
                            "longitude": geogr1,
                            "latitude": geogr2,
                            "elevation": elevation,
                        })
                    except (ValueError, IndexError):
                        continue
    except Exception as e:
        st.error(f"Error reading station metadata: {e}")
        return []
    return stations


@st.cache_resource
def load_epc_model():
    model_path = "machyn_model.joblib"
    if Path(model_path).exists():
        try:
            return joblib.load(model_path)
        except Exception as e:
            st.error(f"Error loading EPC model: {e}")
    return None


def predict_epc_score(model_package, building_data):
    if model_package is None:
        return None
    try:
        model = model_package["model"]
        tech = building_data.get("technicko_ekonomicke_atributy", {})

        def clean_numeric(value, default):
            numeric_value = pd.to_numeric(value, errors="coerce")
            if pd.isna(numeric_value):
                return default
            return float(numeric_value)

        features = pd.DataFrame([{
            "Počet podlaží": clean_numeric(tech.get("Počet podlaží", np.nan), 1),
            "Počet bytů": clean_numeric(tech.get("Počet bytů", np.nan), 0),
            "Zastavěná plocha [m2]": clean_numeric(tech.get("Zastavěná plocha [m2]", np.nan), 0),
            "Druh svislé nosné konstrukce": tech.get("Druh svislé nosné konstrukce", "Unknown") or "Unknown",
            "Vybavení výtahem": tech.get("Vybavení výtahem", "Unknown") or "Unknown",
            "Způsob vytápění": tech.get("Způsob vytápění", "Unknown") or "Unknown",
        }])

        score = model.predict(features)[0]
        return score
    except Exception as e:
        st.warning(f"Prediction error: {e}")
        return None


def epc_grade(score):
    if score is None:
        return "N/A"
    grades = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "F", 7: "G"}
    rounded = int(np.clip(round(score), 1, 7))
    return grades.get(rounded, "G")


def haversine_distance(lat1, lon1, lat2, lon2):
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def find_nearest_station(user_lat, user_lon, stations):
    if not stations:
        return None
    nearest_station = None
    min_distance = float("inf")
    for station in stations:
        distance = haversine_distance(user_lat, user_lon, station["latitude"], station["longitude"])
        if distance < min_distance:
            min_distance = distance
            nearest_station = station.copy()
            nearest_station["distance"] = distance
    return nearest_station


def load_temperature_dataframe(wsi_code):
    zip_path = os.path.join(TEMPERATURE_DIR, f"dly-{wsi_code}-T.zip")
    csv_filename = f"dly-{wsi_code}-T.csv"
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            with zf.open(csv_filename, "r") as csvfile:
                text_file = io.TextIOWrapper(csvfile, encoding="utf-8")
                data = []
                reader = csv.reader(text_file, delimiter=",")
                next(reader, None)
                for row in reader:
                    if len(row) < 5:
                        continue
                    try:
                        dt_str = row[3]
                        value_str = row[4]
                        if not value_str or value_str.strip() == "":
                            continue
                        date_part = dt_str.split("T")[0]
                        dt = datetime.strptime(date_part, "%Y-%m-%d")
                        temperature = float(value_str)
                        data.append({"Date": dt, "Temperature": temperature})
                    except (ValueError, IndexError):
                        continue
                if not data:
                    return None
                df = pd.DataFrame(data)
                df["Date"] = pd.to_datetime(df["Date"])
                df = df.sort_values("Date").reset_index(drop=True)
                return df
    except Exception:
        return None


def calculate_monthly_averages(df):
    if df is None or df.empty:
        return {month: None for month in range(1, 13)}
    monthly_avg = df.groupby(df["Date"].dt.month)["Temperature"].mean()
    return {month: monthly_avg.get(month, None) for month in range(1, 13)}


def calculate_heating_season_characteristics(df):
    if df is None or df.empty:
        return {"heating_days": None, "heating_season_avg_temp": None}
    df = df.set_index("Date").sort_index()
    df = df.groupby(df.index.date)["Temperature"].mean().rename_axis("Date").to_frame()
    df.index = pd.to_datetime(df.index)
    full_dates = pd.date_range(df.index.min(), df.index.max(), freq="D")
    df = df.reindex(full_dates)

    is_heating_day = (df["Temperature"] < 13).fillna(False)
    run_id = (is_heating_day != is_heating_day.shift(1)).cumsum()
    heating_mask = pd.Series(False, index=df.index)

    for _, run in is_heating_day.groupby(run_id):
        if run.iloc[0] and len(run) >= 2:
            heating_mask.loc[run.index] = True

    stats = []
    for year, group in df.groupby(df.index.year):
        year_mask = heating_mask.loc[group.index]
        year_temps = group["Temperature"].loc[year_mask]
        if year_mask.sum() == 0:
            continue
        stats.append({
            "year": year,
            "days": int(year_mask.sum()),
            "avg_temp": float(year_temps.mean()) if not year_temps.empty else None,
        })

    if not stats:
        return {"heating_days": None, "heating_season_avg_temp": None}
    avg_heating_days = sum(s["days"] for s in stats) / len(stats)
    avg_heating_temp = sum(s["avg_temp"] for s in stats if s["avg_temp"] is not None) / len(
        [s for s in stats if s["avg_temp"] is not None]
    )
    return {"heating_days": avg_heating_days, "heating_season_avg_temp": avg_heating_temp}


def calculate_heating_degree_days(df):
    if df is None or df.empty:
        return None
    df = df.set_index("Date").sort_index()
    df = df.groupby(df.index.date)["Temperature"].mean().rename_axis("Date").to_frame()
    df.index = pd.to_datetime(df.index)
    full_dates = pd.date_range(df.index.min(), df.index.max(), freq="D")
    df = df.reindex(full_dates)

    is_heating_day = (df["Temperature"] < 13).fillna(False)
    run_id = (is_heating_day != is_heating_day.shift(1)).cumsum()
    heating_mask = pd.Series(False, index=df.index)
    for _, run in is_heating_day.groupby(run_id):
        if run.iloc[0] and len(run) >= 2:
            heating_mask.loc[run.index] = True

    tint = 20.0
    df_hdd = df.loc[heating_mask, "Temperature"].dropna()
    hdd_values = (tint - df_hdd).clip(lower=0)

    if len(df_hdd.index.year.unique()) == 0:
        return None
    return float(hdd_values.groupby(hdd_values.index.year).sum().mean())


def calculate_design_outdoor_temperature(df):
    if df is None or df.empty:
        return None
    yearly_min_3day_avgs = []
    for year, year_data in df.groupby(df["Date"].dt.year):
        if len(year_data) < 3:
            continue
        rolling_3day = year_data["Temperature"].rolling(window=3, center=True).mean()
        yearly_min_3day_avgs.append(rolling_3day.min())
    if yearly_min_3day_avgs:
        return sum(yearly_min_3day_avgs) / len(yearly_min_3day_avgs)
    return None


def calculate_heating_engineering_stats(wsi_code):
    df = load_temperature_dataframe(wsi_code)
    if df is None:
        return None
    heating_chars = calculate_heating_season_characteristics(df)
    return {
        "monthly_averages": calculate_monthly_averages(df),
        "heating_days": heating_chars["heating_days"],
        "heating_season_avg_temp": heating_chars["heating_season_avg_temp"],
        "heating_degree_days": calculate_heating_degree_days(df),
        "design_temperature": calculate_design_outdoor_temperature(df),
    }


def calculate_5year_average_temperature(wsi_code):
    df = load_temperature_dataframe(wsi_code)
    if df is None or df.empty:
        return None
    most_recent_date = df["Date"].max()
    five_years_ago = most_recent_date - timedelta(days=365 * 5)
    recent_data = df[df["Date"] >= five_years_ago]
    if recent_data.empty:
        return None
    return recent_data["Temperature"].mean()


def create_station_map(user_lat, user_lon, nearest_station, avg_temp, heating_stats, vysledek_povodne):
    station_map = folium.Map(location=[user_lat, user_lon], zoom_start=14)

    if vysledek_povodne not in ("OK", None):
        if vysledek_povodne == "Q5":
            shp_path, barva = MAPA_Q5, "#ff0000"
        elif vysledek_povodne == "Q20":
            shp_path, barva = MAPA_Q20, "#ff8800"
        else:
            shp_path, barva = MAPA_Q100, "#ffd700"

        try:
            gdf = gpd.read_file(shp_path)
            bod = Point(user_lon, user_lat)
            bod_gdf = gpd.GeoDataFrame(geometry=[bod], crs="EPSG:4326")
            if gdf.crs is not None:
                bod_gdf = bod_gdf.to_crs(gdf.crs)
            bod_krovak = bod_gdf.geometry.iloc[0]
            prunik = gdf[gdf.geometry.contains(bod_krovak)]
            if not prunik.empty:
                prunik_gps = prunik.to_crs("EPSG:4326")
                folium.GeoJson(
                    prunik_gps,
                    name=f"Záplavová zóna {vysledek_povodne}",
                    style_function=lambda x: {
                        "fillColor": barva,
                        "color": barva,
                        "weight": 2,
                        "fillOpacity": 0.4,
                    },
                ).add_to(station_map)
        except Exception:
            pass

    folium.CircleMarker(
        location=[user_lat, user_lon],
        radius=8,
        color="red",
        fill=True,
        fill_color="red",
        fill_opacity=0.9,
        popup="Vaše budova",
    ).add_to(station_map)

    if nearest_station:
        temp_text = f"{avg_temp:.2f} °C" if avg_temp is not None else "Data not available"
        popup_html = f"""
        <div style="font-family: Arial, sans-serif; min-width: 400px; max-width: 500px;">
            <h4 style="margin: 0 0 8px 0; color: #2E86C1;">{nearest_station['name']}</h4>
            <p style="margin: 4px 0;"><strong>5-Year Avg Temp:</strong> <span style="color: #E74C3C; font-weight: bold;">{temp_text}</span></p>
            <p style="margin: 4px 0;"><strong>Distance:</strong> {nearest_station['distance']:.2f} km</p>
            <p style="margin: 4px 0;"><strong>Elevation:</strong> {nearest_station['elevation']} m</p>
        </div>
        """
        folium.Marker(
            location=[nearest_station["latitude"], nearest_station["longitude"]],
            popup=folium.Popup(popup_html, max_width=500),
            icon=folium.Icon(color="blue", icon="cloud"),
        ).add_to(station_map)

    return station_map


def main():
    st.set_page_config(page_title="Zelení drancovníci", page_icon="💚", layout="wide")

    if "analysis" not in st.session_state:
        st.session_state.analysis = None
    if "last_building_id" not in st.session_state:
        st.session_state.last_building_id = None
    if "building_data" not in st.session_state:
        st.session_state.building_data = None

    epc_model_package = load_epc_model()

    if not st.session_state.analysis:
        st.title("Štítkovači z päťky")
        st.markdown("""
        <div style="font-size: 22px; line-height: 1.6; text-align: justify; color: #4B0082;">
            <b>Sme elitná jednotka, ktorá v ESG vidí viac než len 3 písmená.</b>
        </div>
        <br>
        """, unsafe_allow_html=True)

    st.sidebar.header("Building Search")

    with st.spinner("Loading station data..."):
        temperature_stations = load_temperature_stations()
        stations = load_station_metadata(temperature_stations)

    if not stations:
        st.error("❌ Unable to load station data. Please check file paths.")
        return

    building_id = st.sidebar.text_input(
        label="ID objektu",
        label_visibility="collapsed",
        placeholder="Napište ID...",
        key="building_id_input",
    )

    if st.sidebar.button("Vyhledat budovu", type="primary", key="search_building"):
        if building_id:
            with st.sidebar.spinner("Hledám v RÚIAN..."):
                result = building_search.get_building_full_data_by_id(building_id)
            if result["status"] == "ok":
                st.session_state.building_data = result
                st.session_state.analysis = None
                st.sidebar.success("Budova nalezena!")
            else:
                st.sidebar.error(result["message"])
        else:
            st.sidebar.warning("Zadejte prosím ID.")

    if st.session_state.building_data and st.session_state.building_data["status"] == "ok":
        building_data = st.session_state.building_data
        user_lat = building_data["geometrie"]["lat"]
        user_lon = building_data["geometrie"]["lon"]

        st.sidebar.markdown(f"**Lokace budovy:** {building_data['nadrazene_prvky'].get('Obec', 'N/A')}")
        st.sidebar.markdown(f"📍 Souřadnice: {user_lat:.4f}, {user_lon:.4f}")

        if st.sidebar.button("📊 Spočítej statistiku", type="primary", key="calculate"):
            with st.spinner("Vyhledávám nejbližší stanici a počítám statistiku... (Kontrola povodní může chvíli trvat)"):
                nearest = find_nearest_station(user_lat, user_lon, stations)
                epc_score = predict_epc_score(epc_model_package, building_data)
                epc_grade_label = epc_grade(epc_score)

                if nearest:
                    avg_temp = calculate_5year_average_temperature(nearest["wsi_code"])
                    heating_stats = calculate_heating_engineering_stats(nearest["wsi_code"])

                    q5 = povodne.zkontroluj_povoden(user_lat, user_lon, MAPA_Q5)
                    q20 = povodne.zkontroluj_povoden(user_lat, user_lon, MAPA_Q20)
                    q100 = povodne.zkontroluj_povoden(user_lat, user_lon, MAPA_Q100)

                    if q5:
                        vysledek_povodne = "Q5"
                    elif q20:
                        vysledek_povodne = "Q20"
                    elif q100:
                        vysledek_povodne = "Q100"
                    else:
                        vysledek_povodne = "OK"

                    st.session_state.esg_val = random.randint(50, 100)
                    st.session_state.analysis = {
                        "nearest": nearest,
                        "avg_temp": avg_temp,
                        "heating_stats": heating_stats,
                        "povoden": vysledek_povodne,
                        "lat": user_lat,
                        "lon": user_lon,
                        "epc_score": epc_score,
                        "epc_grade": epc_grade_label,
                    }
                else:
                    st.error("No suitable station found near your location.")
                    st.session_state.analysis = None

    if st.session_state.analysis:
        analysis = st.session_state.analysis
        b_data = st.session_state.building_data
    
        # Environmentální riziko - Povodně
        povoden_map = {"OK": 100, "Q100": 90, "Q20": 55, "Q5": 30}
        stav_povodne = analysis.get("povoden", "OK")
        e_score = povoden_map.get(stav_povodne, 100)

        # Sociální riziko - Kriminalita
        st.session_state.s_score = random.randint(40, 100)
        s_score = st.session_state.s_score

        if s_score >= 85: s_text = "žádná / velmi ojedinělá"
        elif s_score >= 65: s_text = "občasná"
        elif s_score >= 40: s_text = "častá"
        else: s_text = "velmi častá"

        # Správní rizika - Památková zóna
        if random.random() < 0.60:
            st.session_state.g_score = 100  # 60% pravděpodobnost
        else:
            st.session_state.g_score = 70   # 40% pravděpodobnost

        g_score = st.session_state.g_score
        is_pamatka = (g_score == 70)

        # ESG SKÓRE (Vážený průměr)
        total_esg = (e_score * 0.45) + (s_score * 0.40) + (g_score * 0.15)
        st.session_state.esg_val = round(total_esg, 1)


    # Display analysis results
    if st.session_state.analysis:
        analysis = st.session_state.analysis
        building_data = st.session_state.building_data

        nearest = analysis["nearest"]
        avg_temp = analysis["avg_temp"]
        heating_stats = analysis["heating_stats"]
        stav = analysis.get("povoden", "OK")
        user_lat = analysis["lat"]
        user_lon = analysis["lon"]

        # EPC & ESG Estimates
        st.header("Odhad energetického štítku budovy & ESG rizika")
        
        EPC_DATA = {
            "Průměrná neobnovitelná primární energie [kWh/(m².rok)]":
                {"A": 41.90, "B": 73.49, "C": 98.43, "D": 135.85, "E": 184.08, "F": 236.99, "G": 355.73},
            "Průměrná dílčí dodaná energie na vytápění [kWh/(m².rok)]":
                {"A": 63.78, "B": 84.08, "C": 100.00, "D": 126.44, "E": 179.88, "F": 234.15, "G": 345.82},
            "Průměrná dílčí dodaná energie na chlazení [kWh/(m².rok)]":
                {"A": 1.81, "B": 5.15, "C": 6.96, "D": 3.54, "E": 3.80, "F": 2.47, "G": 2.38},
            "Průměrná dílčí dodaná energie na teplou vodu [kWh/(m².rok)]":
                {"A": 16.67, "B": 21.97, "C": 25.82, "D": 32.90, "E": 33.75, "F": 40.45, "G": 51.67},
            "Průměrná dílčí dodaná energie na osvětlení [kWh/(m².rok)]":
                {"A": 2.89, "B": 4.36, "C": 5.91, "D": 6.35, "E": 9.13, "F": 10.64, "G": 16.06},
            "Průměrný součinitel prostupu tepla [W/(m².K)]":
                {"A": 0.26, "B": 0.28, "C": 0.36, "D": 0.51, "E": 0.69, "F": 0.91, "G": 1.13},
        }

        est_col1, est_col2 = st.columns([1, 2])
        with est_col1:
            epc_score_val = analysis.get("epc_score")
            epc_grade_letter = analysis.get("epc_grade", "N/A")
            st.metric(label="EPC Estimation", value=f"{epc_score_val:.2f}  →  {epc_grade_letter}")
        with est_col2:
            primary_energy_val = EPC_DATA["Průměrná neobnovitelná primární energie [kWh/(m².rok)]"].get(epc_grade_letter, "N/A")
            st.metric(
                label="Průměrná neobnovitelná primární energie [kWh/(m².rok)]",
                value=f"{primary_energy_val}" if primary_energy_val == "N/A" else f"{primary_energy_val:.2f}",
            )
            
            with st.expander(f"Průměrné hodnoty pro kategorii {epc_grade_letter}"):
                rows = []
                for label, values in list(EPC_DATA.items())[1:]:
                    category_val = values.get(epc_grade_letter, "N/A")
                    rows.append({"Ukazatel": label, f"Kategorie {epc_grade_letter}": category_val})
                df_epc = pd.DataFrame(rows).set_index("Ukazatel")
                st.dataframe(df_epc, use_container_width=True)
    

        st.metric("ESG Estimation", f"{st.session_state.esg_val} / 100")

        det_col1, det_col2, det_col3 = st.columns(3)
        
        with det_col1:
            st.markdown("##### Environmentální rizika - E")
            st.write(f"**Povodňová zóna:** {stav_povodne}")
            st.progress(e_score / 100)
            st.write(f"Skóre: **{e_score}**")

        with det_col2:
            st.markdown("##### Sociální rizika - S")
            st.write(f"**Míra kriminality:** {s_text}")
            st.progress(s_score / 100)
            st.write(f"Skóre: **{s_score}**")

        with det_col3:
            st.markdown("##### Správní rizika - G")
            st.write(f"**Památková zóna:** {'Ano' if is_pamatka else 'Ne'}")
            st.progress(g_score / 100)
            st.write(f"Skóre: **{g_score}**")
       

        st.markdown("---")

        # Fotky street view
        display_street_views(GOOGLE_MAPS_API_KEY, user_lat, user_lon)

        # RUIAN building details
        st.header(f"Detaily objektu: {building_data['building_id']}")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Lokalita")
            for k, v in building_data["nadrazene_prvky"].items():
                if v:
                    st.write(f"**{k}:** {v}")
        with col2:
            st.subheader("Technické parametry")
            for k, v in building_data["technicko_ekonomicke_atributy"].items():
                if v:
                    st.write(f"**{k}:** {v}")

        st.markdown(
            f"""<div style="background-color: rgba(75, 0, 130, 0.1); border: 1px solid #4B0082;
            border-radius: 0.4rem; padding: 0.75rem 1rem; color: #4B0082;">
            🔗 <a href="{building_data['odkaz']}" target="_blank" style="color: #4B0082;">Odkaz do registru RÚIAN</a>
            </div>""",
            unsafe_allow_html=True,
        )
        
        st.markdown("---")

        # Station info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Nejbližší meteostanice", nearest["name"])
        with col2:
            st.metric("Vzdálenost", f"{nearest['distance']:.2f} km")
        with col3:
            st.metric("Nadmořská výška", f"{nearest['elevation']} m")

        # Temperature overview
        st.subheader("🌡️ Přehled teplot")
        temp_col1, temp_col2 = st.columns(2)
        with temp_col1:
            st.metric("Průměr teploty za 5 let", f"{avg_temp:.2f} °C" if avg_temp is not None else "N/A")
        with temp_col2:
            design_temp = heating_stats["design_temperature"] if heating_stats else None
            st.metric("Design venkovní teplota", f"{design_temp:.1f} °C" if design_temp is not None else "N/A")

        if heating_stats and heating_stats["monthly_averages"]:
            st.subheader("Průměrné měsíční teploty")
            monthly_data = heating_stats["monthly_averages"]
            months = ["Leden", "Únor", "Březen", "Duben", "Květen", "Červen",
                      "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec"]
            temps = [monthly_data.get(i + 1, 0) for i in range(12)]
            month_categories = pd.Categorical(months, categories=months, ordered=True)
            chart_data = pd.DataFrame({"Měsíc": month_categories, "Teplota (°C)": temps}).set_index("Měsíc")
            st.bar_chart(chart_data)

        # Energy report
        if heating_stats:
            st.subheader("Energetická zpráva")
            report_cols = st.columns(4)
            with report_cols[0]:
                st.metric("Topné dny", f"{heating_stats['heating_days']:.0f} dnů/rok" if heating_stats["heating_days"] is not None else "N/A")
            with report_cols[1]:
                st.metric("Topná sezóna - průměr", f"{heating_stats['heating_season_avg_temp']:.1f} °C" if heating_stats["heating_season_avg_temp"] is not None else "N/A")
            with report_cols[2]:
                st.metric("HDD", f"{heating_stats['heating_degree_days']:.0f} HDD/rok" if heating_stats["heating_degree_days"] is not None else "N/A")
            with report_cols[3]:
                st.metric("Návrhová teplota", f"{heating_stats['design_temperature']:.1f} °C" if heating_stats["design_temperature"] is not None else "N/A")

        # Map
        st.subheader("Záplavové oblasti")
        if stav == "Q5":
            st.error("🔴 **EXTRÉMNÍ RIZIKO:** Budova leží v zóně 5leté vody (Q5)!")
        elif stav == "Q20":
            st.warning("🟠 **VYSOKÉ RIZIKO:** Budova leží v zóně 20leté vody (Q20)!")
        elif stav == "Q100":
            st.info("🟡 **ZVÝŠENÉ RIZIKO:** Budova leží v zóně 100leté vody (Q100).")
        else:
            st.success("🟢 **BEZPEČNO:** Budova leží zcela mimo záplavové oblasti (Q5, Q20, Q100).")
        station_map = create_station_map(user_lat, user_lon, nearest, avg_temp, heating_stats, stav)
        st_folium(station_map, use_container_width=True, height=500)


if __name__ == "__main__":
    main()
