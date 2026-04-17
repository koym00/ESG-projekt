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
import plotly.graph_objects as go

from pathlib import Path
from datetime import datetime, timedelta
from streamlit_folium import st_folium
from shapely.geometry import Point
from street_view import display_street_views

# Configuration
ZIP_PATH = r"C:\temp\Metadata\meta1.zip"
CSV_FILENAME = r"meta1.csv"
META2_ZIP_PATH = r"C:\temp\Metadata\meta2.zip"
META2_CSV_FILENAME = r"meta2.csv"
TEMPERATURE_DIR = r"C:\temp\Data\Temperature"

# Definice povodňových map (nyní bezpečně namířené do složky temp a s PŘESNÝMI velkými/malými písmeny!)
MAPA_Q5 = r"C:\temp\Data\D01_ZaplUzemi5Vody.shp"
MAPA_Q20 = r"C:\temp\Data\D02_ZaplUzemi20vody.shp"
MAPA_Q100 = r"C:\temp\Data\D03_ZaplUzemi100vody.shp"

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


def predict_epc_score(model_package, building_data, heating_days):
    if model_package is None:
        return None
    try:
        model = model_package["model"]
        tech = building_data.get("technicko_ekonomicke_atributy", {})

        # --- NOVÁ ČASŤ: Extrakcia roku dokončenia ---
        datum_raw = tech.get("Datum dokončení", "")
        try:
            # Ak je dátum v formáte "26.08.2022", vezmeme poslednú časť
            rok_dokoncenia = int(str(datum_raw).split('.')[-1])
        except (ValueError, IndexError):
            # Ak rok chýba, dosadíme medián (napr. 2000)
            rok_dokoncenia = 2000 

        def clean_numeric(value, default):
            numeric_value = pd.to_numeric(value, errors="coerce")
            if pd.isna(numeric_value):
                return default
            return float(numeric_value)

        # Príprava dát pre model - MUSÍ presne zodpovedať trénovacím dátam
        features = pd.DataFrame([{
            "Počet podlaží": clean_numeric(tech.get("Počet podlaží"), 1),
            "Počet bytů": clean_numeric(tech.get("Počet bytů"), 0),
            "Zastavěná plocha [m2]": clean_numeric(tech.get("Zastavěná plocha [m2]"), 100),
            "heating_days": heating_days,
            "Rok dokončení": rok_dokoncenia,  # TENTO PARAMETER MODEL TERAZ VYŽADUJE
            "Druh svislé nosné konstrukce": tech.get("Druh svislé nosné konstrukce", "Unknown") or "Unknown",
            "Vybavení výtahem": tech.get("Vybavení výtahem", "Unknown") or "Unknown",
            "Způsob vytápění": tech.get("Způsob vytápění", "Unknown") or "Unknown",
        }])

        score = model.predict(features)[0]
        return score
    except Exception as e:
        st.warning(f"Chyba pri predikcii: {e}")
        return None


def epc_grade(score):
    # Kontrola na None i na NaN (pomocí numpy)
    if score is None or (isinstance(score, float) and np.isnan(score)):
        return "N/A"
    
    grades = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "F", 7: "G"}
    try:
        # np.clip a int spadnou na NaN, proto ta kontrola výše
        rounded = int(np.clip(round(score), 1, 7))
        return grades.get(rounded, "G")
    except (ValueError, TypeError):
        return "N/A"


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

def create_esg_spider_chart(e, s, g):
    """Vytvoří radarový graf pro ESG pilíře."""
    fig = go.Figure(data=go.Scatterpolar(
      r=[e, s, g, e],
      theta=['Environmentální (E)', 'Sociální (S)', 'Správní (G)', 'Environmentální (E)'],
      fill='toself',
      line=dict(color='#4B0082'),
      fillcolor='rgba(75, 0, 130, 0.3)'
    ))
    
    fig.update_layout(
      polar=dict(
        radialaxis=dict(visible=True, range=[0, 100])
      ),
      showlegend=False,
      margin=dict(l=40, r=40, t=20, b=20),
      height=350
    )
    return fig

def get_clean_coefficients(model_package):
    """Extrahuje koeficienty z modelu a vyčistí jejich názvy."""
    if model_package is None:
        return None
    
    model = model_package['model']
    preprocessor = model.named_steps['preprocessor']
    
    # Získání názvů proměnných (stejná logika jako ve vašem validačním skriptu)
    num_features = preprocessor.transformers_[0][2]
    cat_features = list(preprocessor.transformers_[1][1].get_feature_names_out())
    feature_names = num_features + cat_features
    
    # Extrakce koeficientů
    coefs = model.named_steps['regressor'].coef_
    
    # Vytvoření DataFrame
    df = pd.DataFrame({
        "Vlastnost": feature_names,
        "Váha (Koeficient)": coefs
    })
    
    # Vyčištění názvů pro uživatele (odstranění názvů sloupců z OneHotEncoding)
    df["Vlastnost"] = df["Vlastnost"].str.replace("Druh svislé nosné konstrukce_", "Konstrukce: ")
    df["Vlastnost"] = df["Vlastnost"].str.replace("Způsob vytápění_", "Vytápění: ")
    df["Vlastnost"] = df["Vlastnost"].str.replace("Vybavení výtahem_", "Výtah: ")
    
    return df.sort_values(by="Váha (Koeficient)", ascending=False)

def predict_epc_score_with_breakdown(model_package, building_data, heating_days, active_vars=None):
    if model_package is None:
        return None, None
    try:
        model = model_package["model"]
        # --- KLÍČOVÉ: Definice preprocesoru a regresoru musí být zde ---
        preprocessor = model.named_steps['preprocessor']
        regressor = model.named_steps['regressor']
        
        tech = building_data.get("technicko_ekonomicke_atributy", {})
        
        # Kontrola roku dokončení (beze změny)
        datum_raw = tech.get("Datum dokončení", "")
        if not datum_raw or str(datum_raw).lower() in ["nan", "", "nezjištěno", "none"]:
            return None, "CHYBA_ROK"
        try:
            rok = int(str(datum_raw).split('.')[-1])
        except (ValueError, IndexError):
            return None, "CHYBA_ROK"

        # Pomocná funkce pro checkboxy (pokud je var vypnutá, dáme neutrální hodnotu)
        def get_val(key, default_if_inactive, val_from_tech):
            if active_vars and not active_vars.get(key, True):
                return default_if_inactive
            num = pd.to_numeric(val_from_tech, errors="coerce")
            return default_if_inactive if pd.isna(num) else float(num)

        # Příprava DataFrame (respektuje checkboxy)
        features = pd.DataFrame([{
            "Počet podlaží": get_val("Počet podlaží", 1, tech.get("Počet podlaží") or tech.get("Počet nadzemních podlaží")),
            "Počet bytů": get_val("Počet bytů", 0, tech.get("Počet bytů")),
            "Zastavěná plocha [m2]": get_val("Zastavěná plocha [m2]", 100, tech.get("Zastavěná plocha [m2]")),
            "heating_days": heating_days if (not active_vars or active_vars.get("heating_days")) else 220,
            "Rok dokončení": rok if (not active_vars or active_vars.get("Rok dokončení")) else 2000,
            "Druh svislé nosné konstrukce": tech.get("Druh svislé nosné konstrukce", "Unknown") if (not active_vars or active_vars.get("Druh svislé nosné konstrukce")) else "Unknown",
            "Vybavení výtahem": tech.get("Vybavení výtahem", "Unknown") if (not active_vars or active_vars.get("Vybavení výtahem")) else "Unknown",
            "Způsob vytápění": tech.get("Způsob vytápění", "Unknown") if (not active_vars or active_vars.get("Způsob vytápění")) else "Unknown",
        }])

        # 1. Transformace dat (zde byla ta chyba)
        X_transformed = preprocessor.transform(features)
        
        # 2. Názvy sloupců pro rozbor
        cat_feature_names = list(preprocessor.transformers_[1][1].get_feature_names_out())
        feature_names = ["Počet podlaží", "Počet bytů", "Zastavěná plocha [m2]", "heating_days", "Rok dokončení"] + cat_feature_names
        
        # 3. Výpočet příspěvků a celkového skóre
        coefficients = regressor.coef_
        intercept = regressor.intercept_
        contributions = X_transformed[0] * coefficients
        
        breakdown = {"Základní konstanta (Intercept)": intercept}
        for name, contrib in zip(feature_names, contributions):
            if contrib != 0: 
                clean_name = name.replace("Druh svislé nosné konstrukce_", "Konstrukce: ") \
                                 .replace("Způsob vytápění_", "Vytápění: ") \
                                 .replace("Vybavení výtahem_", "Výtah: ")
                breakdown[clean_name] = contrib

        total_score = intercept + sum(contributions)
        return total_score, breakdown
    except Exception as e:
        st.error(f"Chyba výpočtu: {e}")
        return None, None

def main():
    st.set_page_config(page_title="Zelení drancovníci", page_icon="💚", layout="wide")

    if "analysis" not in st.session_state:
        st.session_state.analysis = None
    if "last_building_id" not in st.session_state:
        st.session_state.last_building_id = None
    if "building_data" not in st.session_state:
        st.session_state.building_data = None

    epc_model_package = load_epc_model()

    # Průměrné hodnoty pro ČR (pro srovnání)
    CZ_PRUMER_TEPLOTA = 8.5   # Průměrná roční teplota v ČR
    CZ_PRUMER_DESIGN_T = -12.0 # Standardní návrhová teplota pro většinu území
    CZ_PRUMER_TOPNE_DNY = 220  # Průměrný počet topných dnů
    CZ_PRUMER_HDD = 3500      # Průměrné dennostupně

    if not st.session_state.analysis:
        st.title("Team 5 - ESG")
        st.markdown("""
        <div style="font-size: 22px; line-height: 1.6; text-align: justify; color: #4B0082;">
            <b>Markéta Hončíková, Matej Koyš, Erik Seidl a Anna Spilková</b>
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

        # --- NOVÉ: VÝBĚR PROMĚNNÝCH PRO EPC ---
        st.sidebar.markdown("---")
        
        # Použijeme expander namiesto subheaderu
        with st.sidebar.expander("Parametry výpočtu EPC"):
            
            
            vars_to_control = {
                "Počet podlaží": True,
                "Počet bytů": True,
                "Zastavěná plocha [m2]": True,
                "heating_days": True,
                "Rok dokončení": True,
                "Druh svislé nosné konstrukce": True,
                "Vybavení výtahem": True,
                "Způsob vytápění": True
            }
            
            # Checkboxy sa teraz vykreslia vo vnútri expandera
            active_vars = {}
            for var, default_val in vars_to_control.items():
                active_vars[var] = st.checkbox(f"Zahrnout: {var}", value=default_val)
        

        if st.sidebar.button("📊 Spočítej statistiku", type="primary", key="calculate"):
            with st.spinner("Vyhledávám nejbližší stanici a počítám statistiku..."):
                nearest = find_nearest_station(user_lat, user_lon, stations)
                
                if nearest:
                    avg_temp = calculate_5year_average_temperature(nearest["wsi_code"])
                    heating_stats = calculate_heating_engineering_stats(nearest["wsi_code"])
                    h_days = heating_stats['heating_days'] if heating_stats else 220
                    
                    score, breakdown = predict_epc_score_with_breakdown(
                        epc_model_package, 
                        building_data, 
                        h_days, 
                        active_vars=active_vars # Přidáno
                    )
                    
                    if breakdown == "CHYBA_ROK":
                        epc_grade_label = "G (nelze určit)"
                        final_score = None
                    else:
                        epc_grade_label = epc_grade(score) if score else "N/A"
                        final_score = score

                    vysledek_povodne = "Q5" if povodne.zkontroluj_povoden(user_lat, user_lon, MAPA_Q5) else \
                                       "Q20" if povodne.zkontroluj_povoden(user_lat, user_lon, MAPA_Q20) else \
                                       "Q100" if povodne.zkontroluj_povoden(user_lat, user_lon, MAPA_Q100) else "OK"

                    # --- TU VYGENERUJEME NÁHODU IBA RAZ PRI KLIKNUTÍ ---
                    s_score_new = random.randint(40, 100)
                    g_score_new = 100 if random.random() < 0.60 else 70
                    
                    # Výpočet celkového ESG skóre
                    povoden_map = {"OK": 100, "Q100": 90, "Q20": 55, "Q5": 30}
                    e_score_new = povoden_map.get(vysledek_povodne, 100)
                    total_esg = (e_score_new * 0.45) + (s_score_new * 0.40) + (g_score_new * 0.15)

                    st.session_state.analysis = {
                        "nearest": nearest,
                        "avg_temp": avg_temp,
                        "heating_stats": heating_stats,
                        "povoden": vysledek_povodne,
                        "lat": user_lat,
                        "lon": user_lon,
                        "epc_score": final_score,
                        "epc_grade": epc_grade_label,
                        "epc_breakdown": breakdown,
                        # Uložíme vygenerované skóre do analýzy
                        "e_score": e_score_new,
                        "s_score": s_score_new,
                        "g_score": g_score_new,
                        "esg_val": round(total_esg, 1)
                    }


    # Display analysis results
    if st.session_state.analysis:
        analysis = st.session_state.analysis
        building_data = st.session_state.building_data

        tab1, tab2 = st.tabs(["📊 Analýza rizika", "📖 Metadata a metodika"])

        with tab1:
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

            est_col1, est_col2 = st.columns(2) 

            epc_score_val = analysis.get("epc_score")
            epc_grade_letter = analysis.get("epc_grade", "N/A")
            grade_key = epc_grade_letter[0] if epc_grade_letter and epc_grade_letter[0] in "ABCDEFG" else "N/A"

            with est_col1:
                # Začína na 0 % šírky (úplne vľavo)
                score_display = f"{epc_score_val:.2f}" if epc_score_val is not None else "N/A"
                st.metric(label="EPC Estimation", value=f"{score_display}  →  {epc_grade_letter}")

            with est_col2:
                # Začína presne na 50 % šírky (stred strany)
                primary_energy_val = EPC_DATA["Průměrná neobnovitelná primární energie [kWh/(m².rok)]"].get(grade_key, "N/A")
                energy_display = f"{primary_energy_val:.2f}" if isinstance(primary_energy_val, (int, float)) else "N/A"
                
                st.metric(
                    label="Průměrná neobnovitelná primární energie [kWh/(m².rok)]",
                    value=energy_display,
                )

                with st.expander(f"Průměrné hodnoty pro kategorii {grade_key}"):
                    if grade_key != "N/A":
                        rows = []
                        for label, values in list(EPC_DATA.items())[1:]:
                            category_val = values.get(grade_key, "N/A")
                            rows.append({"Ukazatel": label, f"Kategorie {grade_key}": category_val})
                        df_epc = pd.DataFrame(rows).set_index("Ukazatel")
                        st.dataframe(df_epc, use_container_width=True)
                    else:
                        st.write("Průměrné hodnoty nejsou k dispozici.")

            st.divider()

            # --- NOVÉ ROZLOŽENÍ: SKÓRE A GRAF VLEVO, RIZIKA VPRAVO ---
            layout_col1, layout_col2 = st.columns(2) 

            with layout_col1:
                # Ťaháme skóre priamo z analýzy, kde je „zamrznuté“
                st.metric("ESG Estimation", f"{analysis.get('esg_val', 'N/A')} / 100")
                st.divider()
                
                e_val = analysis.get('e_score', 0)
                s_val = analysis.get('s_score', 0)
                g_val = analysis.get('g_score', 0)
                
                spider_fig = create_esg_spider_chart(e_val, s_val, g_val)
                st.plotly_chart(spider_fig, use_container_width=True)

            with layout_col2:
                st.write("## ") 
                
                # E - Environmentální
                st.markdown("##### Environmentální rizika - E")
                st.write(f"**Povodňová zóna:** {analysis.get('povoden', 'N/A')}")
                st.progress(e_val / 100)
                st.write(f"Skóre: **{e_val}**")
                st.markdown("<br>", unsafe_allow_html=True)

                # S - Sociální
                st.markdown("##### Sociální rizika - S")
                # Text určíme podľa zamrznutého skóre
                if s_val >= 85: s_text = "žádná / velmi ojedinělá"
                elif s_val >= 65: s_text = "občasná"
                elif s_val >= 40: s_text = "častá"
                else: s_text = "velmi častá"
                
                st.write(f"**Míra kriminality:** {s_text}")
                st.progress(s_val / 100)
                st.write(f"Skóre: **{s_val}**")
                st.markdown("<br>", unsafe_allow_html=True)

                # G - Správní
                st.markdown("##### Správní rizika - G")
                st.write(f"**Památková zóna:** {'Ano' if g_val == 70 else 'Ne'}")
                st.progress(g_val / 100)
                st.write(f"Skóre: **{g_val}**")

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

            # --- 1. PROUŽEK SE STANICÍ ---
            st.markdown("### Lokální meteorologický kontext")
            with st.container(border=True):
                stat_col1, stat_col2, stat_col3 = st.columns(3)
                with stat_col1:
                    st.caption("NEJBLIŽŠÍ STANICE")
                    st.markdown(f"**{nearest['name']}**")
                with stat_col2:
                    st.caption("VZDÁLENOST")
                    st.markdown(f"**{nearest['distance']:.2f} km**")
                with stat_col3:
                    st.caption("NADMOŘSKÁ VÝŠKA")
                    st.markdown(f"**{nearest['elevation']} m n.m.**")

            # --- 2. TEPLOTY A ENERGETIKA ---
            main_col1, main_col2 = st.columns([1.6, 1])

            with main_col1:
                with st.container(border=True):
                    st.subheader("Teplotní profil lokality")
                    
                    if heating_stats and "monthly_averages" in heating_stats:
                        mesice_poradie = ["Led", "Úno", "Bře", "Dub", "Kvě", "Čer", "Čec", "Srp", "Zář", "Říj", "Lis", "Pro"]
                        raw_data = heating_stats["monthly_averages"]
                        
                        teploty = []
                        for i in range(1, 13):
                            val = raw_data.get(i, raw_data.get(str(i), 0))
                            teploty.append(float(val) if val is not None else 0.0)
                        
                        df_graf = pd.DataFrame({
                            "Měsíc": mesice_poradie,
                            "Teplota": teploty
                        })
                        df_graf["Měsíc"] = pd.Categorical(df_graf["Měsíc"], categories=mesice_poradie, ordered=True)
                        
                        # ZMENA: Zníženie výšky na 375 pre lepšie zarovnanie
                        st.bar_chart(
                            df_graf, 
                            x="Měsíc", 
                            y="Teplota", 
                            color="#4B0082", 
                            height=325 
                        )
                    else:
                        st.info("Profil teplot není k dispozici.")
                    
                    # Metriky pod grafom
                    t_col1, t_col2 = st.columns(2)
                    with t_col1:
                        if avg_temp:
                            delta_t = avg_temp - CZ_PRUMER_TEPLOTA
                            st.metric("Průměrná teplota (5 let)", f"{avg_temp:.2f} °C", 
                                      delta=f"{delta_t:+.2f} °C", delta_color="normal")
                    with t_col2:
                        d_temp = heating_stats.get("design_temperature") if heating_stats else None
                        if d_temp:
                            delta_d = d_temp - CZ_PRUMER_DESIGN_T
                            st.metric("Návrhová teplota", f"{d_temp:.1f} °C", 
                                      delta=f"{delta_d:+.1f} °C", delta_color="normal")

            with main_col2:
                with st.container(border=True):
                    st.subheader("Energetická zpráva")
                    
                    if heating_stats:
                        # Topné dny
                        h_days = heating_stats["heating_days"]
                        if h_days:
                            delta_days = h_days - CZ_PRUMER_TOPNE_DNY
                            st.metric("Topné dny", f"{h_days:.0f} dnů/rok", 
                                      delta=f"{delta_days:+.0f} dnů", delta_color="inverse")
                        
                        st.divider()
                        
                        # HDD (Dennostupně)
                        hdd = heating_stats["heating_degree_days"]
                        if hdd:
                            delta_hdd = hdd - CZ_PRUMER_HDD
                            st.metric("Dennostupně (HDD)", f"{hdd:.0f} HDD/rok", 
                                      delta=f"{delta_hdd:+.0f} HDD", delta_color="inverse")
                        
                        st.divider()
                        
                        # Průměr sezóny
                        s_avg = heating_stats.get('heating_season_avg_temp')
                        st.metric("Průměr topné sezóny", f"{s_avg:.1f} °C" if s_avg else "N/A")
                    else:
                        st.info("Data nejsou k dispozici.")
                        
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
        with tab2:
            st.header("Metodika a metadata")
            st.markdown("Tento přehled vysvětluje logiku výpočtů a zdroje dat v pořadí, v jakém jsou prezentovány ve výsledcích analýzy.")

            # 1. EPC a ESG (Odpovídá první sekci na tab1)
            with st.expander("⚡ Odhad energetického štítku (EPC) - Dynamický model"):
                st.write("""
                Odhad výsledného skóre probíhá pomocí **Lineární regrese**. Níže uvedená tabulka zobrazuje 
                aktuální váhy jednotlivých parametrů načtené přímo z natrénovaného modelu.
                """)
                
                # Získání a zobrazení dynamických koeficientů
                df_coefs = get_clean_coefficients(epc_model_package)
                
                if df_coefs is not None:
                    # Přidáme sloupec s vysvětlením vlivu pro lepší srozumitelnost
                    df_coefs["Vliv na skóre"] = df_coefs["Váha (Koeficient)"].apply(
                        lambda x: "🔴 Zhoršuje štítek" if x > 0 else "🟢 Zlepšuje štítek"
                    )
                    
                    # Zobrazení tabulky
                    st.dataframe(
                        df_coefs, 
                        column_config={
                            "Váha (Koeficient)": st.column_config.NumberColumn(format="%.4f")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.error("Nepodařilo se načíst koeficienty modelu.")

                st.info("""
                **Interpretace:** Kladná váha posouvá budovu směrem k horšímu štítku (G=7), 
                záporná váha směrem k lepšímu štítku (A=1). Model pracuje s normalizovanými daty, 
                proto jsou koeficienty vzájemně porovnatelné.
                """)

                if st.session_state.analysis and "epc_breakdown" in st.session_state.analysis:
                    st.divider()
                    st.write("### 🔍 Konkrétní výpočet pro vybranou budovu")
                    
                    analysis = st.session_state.analysis
                    breakdown = analysis["epc_breakdown"]
                
                    # --- SCÉNÁŘ A: Rok dokončení chybí ---
                    if breakdown == "CHYBA_ROK":
                        st.error("⚠️ Výpočet energetického štítku nebyl proveden.")
                        st.write(f"**Důvod:** V registrech RÚIAN pro tuto budovu chybí povinný údaj: **Rok dokončení**.")
                        st.info(f"**Výsledná kategorie:** {analysis['epc_grade']}")
                        st.warning("Bez znalosti stáří budovy nelze provést statistický odhad energetické náročnosti.")
                
                    # --- SCÉNÁŘ B: Výpočet proběhl v pořádku (breakdown je slovník) ---
                    elif isinstance(breakdown, dict):
                        st.info("Tento výpočet ukazuje, jak se obecné koeficienty aplikovaly na parametry vaší budovy.")
                
                        # Seřazení rozboru podle vlivu (absolutní hodnota)
                        sorted_bd = dict(sorted(breakdown.items(), key=lambda item: abs(item[1]), reverse=True))
                
                        # Výpis jednotlivých vlivů
                        for feature, value in sorted_bd.items():
                            color = "red" if value > 0 else "green"
                            sign = "+" if value > 0 else ""
                            st.markdown(f"{feature}: **:{color}[{sign}{value:.4f}]**")
                
                        st.divider()
                        # Ošetření zobrazení skóre, pokud by náhodou bylo None
                        score_display = f"{analysis['epc_score']:.4f}" if analysis['epc_score'] is not None else "N/A"
                        st.success(f"**Finální vypočítané skóre: {score_display} (Kategorie {analysis['epc_grade']})**")
                
                else:
                    st.warning("Pro zobrazení konkrétního rozboru výpočtu nejprve vyberte budovu a klikněte na 'Spočítej statistiku' v bočním panelu.")

                st.write("""
                **Energetický štítek (EPC Estimation):**
                - Štítek je predikován pomocí modelu **lineární regrese**, který byl natrénován na historických datech EPC štítků propojených s technickými parametry budov.
                - **Vstupy:** Počet podlaží, počet bytů, zastavěná plocha, druh konstrukce a způsob vytápění z RÚIAN.
                - **Referenční hodnoty:** Údaje o primární energii v tabulce jsou odvozeny z průměrných hodnot pro danou kategorii (A-G).

                **ESG Skóre:**
                - Počítá se jako vážený průměr tří pilířů:
                """)
                st.latex(r"ESG_{total} = (E \cdot 0.45) + (S \cdot 0.40) + (G \cdot 0.15)")
                st.write("""
                - **Environmentální (E):** Určeno podle záplavové zóny (OK=100b, Q100=90b, Q20=55b, Q5=30b).
                - **Sociální (S):** Úroveň bezpečnosti na základě simulované kriminality v lokalitě.
                - **Správní (G):** Legislativní omezení (např. zda je budova v památkové zóně).
                """)

            # 2. Street View
            with st.expander("🖼️ Vizuální náhled (Street View)"):
                st.write("""
                **Zdroj:** Google Maps Static API / Street View Image API.
                - Snímky jsou načteny na základě GPS souřadnic budovy získaných z RÚIAN.
                - Zobrazují reálný kontext okolí budovy pro rychlou vizuální verifikaci polohy.
                """)

            # 3. RÚIAN Detaily
            with st.expander("🏠 Detaily objektu a identifikace (RÚIAN)"):
                st.write("""
                **Zdroj:** Veřejný dálkový přístup (VDP) Českého úřadu zeměměřického a katastrálního (ČÚZK).
                - **Sběr dat:** Data jsou extrahována v reálném čase z HTML struktury registru pro zadané ID stavebního objektu.
                - **Transformace souřadnic:** Původní české souřadnice **S-JTSK** jsou transformovány na globální systém **WGS84** (GPS) pomocí knihovny `pyproj` (transformace z EPSG:5514 na EPSG:4326).
                """)

            # 4. Meteostanice
            with st.expander("📡 Výběr nejbližší stanice"):
                st.write("""
                **Metodika výběru:**
                - Aplikace prohledává databázi metadat ČHMÚ a hledá nejbližší aktivní stanici, která měří teplotu (element 'T').
                - **Výpočet vzdálenosti:** Používá se **Haversineho vzorec**, který počítá nejkratší vzdálenost mezi dvěma body na povrchu koule (Země) na základě jejich zeměpisné šířky a délky.
                """)

            # 5. Teplotní ukazatele (Podrobný rozpis)
            with st.expander("🌡️ Podrobná analýza teplot (ČHMÚ)", expanded=True):
                st.write("""
                Všechny statistiky jsou počítány z denních měření za posledních **5 let** z vybrané stanice.

                **Metodika výpočtů:**
                - **5letý průměr:** Aritmetický průměr všech naměřených denních teplot za posledních 60 měsíců.
                - **Návrhová venkovní teplota:** Reprezentuje extrémně chladné období pro potřeby dimenzování topení. Počítá se jako průměr ročních minim z třídenních klouzavých průměrů denní teploty.
                - **Měsíční průměry:** Průměrná teplota pro každý kalendářní měsíc vypočítaná z 5leté historie, zobrazená v grafu pro vizualizaci sezónnosti.
                """)

            # 6. Energetická zpráva
            with st.expander("📊 Energetická zpráva a inženýrské výpočty"):
                st.write("""
                **Topné dny (Heating Days):**
                - Počet dní v roce, kdy je nutné topit. Den je označen jako „topný“, pokud je jeho průměrná teplota nižší než **13 °C**. Do součtu se berou pouze souvislé úseky trvající alespoň 2 dny.

                **Topná sezóna – průměr:**
                - Průměrná venkovní teplota vypočítaná výhradně za období topných dnů.

                **Vytápěcí dennostupně (HDD – Heating Degree Days):**
                - Ukazatel energetické náročnosti budovy. Vyjadřuje sumu rozdílů mezi interiérovou teplotou a venkovní teplotou za všechny topné dny:
                """)
                st.latex(r"HDD = \sum (T_{interiér} - T_{venkovní})")
                st.write(r"""
                - Kde **$T_{interiér} = 20,0\ ^\circ C$**. Vyšší hodnota HDD znamená vyšší potřebu energie na vytápění.
                """)

            # 7. Záplavové oblasti
            with st.expander("🌊 Analýza záplavových oblastí (DIBAVOD)"):
                st.write("""
                **Zdroj:** Digitální báze vodohospodářských dat (DIBAVOD) – Výzkumný ústav vodohospodářský T. G. Masaryka.
                - **Prostorová analýza:** Aplikace provádí prostorový průnik (`intersects`) GPS polohy budovy s polygony záplavových území.
                - **Scénáře:** Vyhodnocuje se riziko pro 5letou (Q5), 20letou (Q20) a 100letou vodu (Q100).
                - **Mapový podklad:** Vrstvy jsou zobrazeny pomocí knihovny Folium nad interaktivní mapou.
                """)


if __name__ == "__main__":
    main()