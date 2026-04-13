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
from datetime import datetime, timedelta
import folium
from streamlit_folium import st_folium
import povodne
import geopandas as gpd
from shapely.geometry import Point
import building_search

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

# Google Street View Configuration
GOOGLE_MAPS_API_KEY = "AIzaSyAmA49RD3nfCsYs1wHKlI-1P-eQp1U2UPE"  # Replace with your API key or leave as None for fallback
EARTH_RADIUS_KM = 6371

@st.cache_data
def load_temperature_stations():
    temperature_stations = set()
    try:
        with zipfile.ZipFile(META2_ZIP_PATH, 'r') as zf:
            with zf.open(META2_CSV_FILENAME, 'r') as csvfile:
                text_file = io.TextIOWrapper(csvfile, encoding='utf-8')
                reader = csv.reader(text_file, delimiter=',')
                next(reader, None)
                for row in reader:
                    if len(row) < 5: continue
                    try:
                        wsi_code = row[1]
                        element = row[4]
                        if element == "T": temperature_stations.add(wsi_code)
                    except (ValueError, IndexError): continue
    except Exception as e:
        st.warning(f"Error reading temperature capability data: {e}. Proceeding without filtering.")
    return temperature_stations

@st.cache_data
def load_station_metadata(temperature_stations):
    stations = []
    try:
        with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
            with zf.open(CSV_FILENAME, 'r') as csvfile:
                text_file = io.TextIOWrapper(csvfile, encoding='utf-8')
                reader = csv.reader(text_file, delimiter=',')
                next(reader, None)
                for row in reader:
                    if len(row) < 8: continue
                    try:
                        wsi_code = row[0]
                        end_date = row[3]
                        if not end_date.startswith("3999"): continue
                        if temperature_stations and wsi_code not in temperature_stations: continue
                        
                        full_name = row[4]
                        geogr1 = float(row[5])
                        geogr2 = float(row[6])
                        elevation = row[7]
                        
                        stations.append({
                            'wsi_code': wsi_code, 'name': full_name,
                            'longitude': geogr1, 'latitude': geogr2, 'elevation': elevation
                        })
                    except (ValueError, IndexError): continue
    except Exception as e:
        st.error(f"Error reading station metadata: {e}")
        return []
    return stations

def haversine_distance(lat1, lon1, lat2, lon2):
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c

def find_nearest_station(user_lat, user_lon, stations):
    if not stations: return None
    nearest_station = None
    min_distance = float('inf')
    for station in stations:
        distance = haversine_distance(user_lat, user_lon, station['latitude'], station['longitude'])
        if distance < min_distance:
            min_distance = distance
            nearest_station = station.copy()
            nearest_station['distance'] = distance
    return nearest_station

def load_temperature_dataframe(wsi_code):
    zip_path = os.path.join(TEMPERATURE_DIR, f"dly-{wsi_code}-T.zip")
    csv_filename = f"dly-{wsi_code}-T.csv"
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            with zf.open(csv_filename, 'r') as csvfile:
                text_file = io.TextIOWrapper(csvfile, encoding='utf-8')
                data = []
                reader = csv.reader(text_file, delimiter=',')
                next(reader, None)
                for row in reader:
                    if len(row) < 5: continue
                    try:
                        dt_str = row[3]
                        value_str = row[4]
                        if not value_str or value_str.strip() == '': continue
                        date_part = dt_str.split('T')[0]
                        dt = datetime.strptime(date_part, '%Y-%m-%d')
                        temperature = float(value_str)
                        data.append({'Date': dt, 'Temperature': temperature})
                    except (ValueError, IndexError): continue
                if not data: return None
                df = pd.DataFrame(data)
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.sort_values('Date').reset_index(drop=True)
                return df
    except Exception: return None

def calculate_monthly_averages(df):
    if df is None or df.empty: return {month: None for month in range(1, 13)}
    monthly_avg = df.groupby(df['Date'].dt.month)['Temperature'].mean()
    return {month: monthly_avg.get(month, None) for month in range(1, 13)}

def calculate_heating_season_characteristics(df):
    if df is None or df.empty: return {'heating_days': None, 'heating_season_avg_temp': None}
    df = df.set_index('Date').sort_index()
    df = df.groupby(df.index.date)['Temperature'].mean().rename_axis('Date').to_frame()
    df.index = pd.to_datetime(df.index)
    full_dates = pd.date_range(df.index.min(), df.index.max(), freq='D')
    df = df.reindex(full_dates)
    
    is_heating_day = (df['Temperature'] < 13).fillna(False)
    run_id = (is_heating_day != is_heating_day.shift(1)).cumsum()
    heating_mask = pd.Series(False, index=df.index)
    
    for _, run in is_heating_day.groupby(run_id):
        if run.iloc[0] and len(run) >= 2:
            heating_mask.loc[run.index] = True
            
    stats = []
    for year, group in df.groupby(df.index.year):
        year_mask = heating_mask.loc[group.index]
        year_temps = group['Temperature'].loc[year_mask]
        if year_mask.sum() == 0: continue
        stats.append({'year': year, 'days': int(year_mask.sum()), 'avg_temp': float(year_temps.mean()) if not year_temps.empty else None})
        
    if not stats: return {'heating_days': None, 'heating_season_avg_temp': None}
    avg_heating_days = sum(s['days'] for s in stats) / len(stats)
    avg_heating_temp = sum(s['avg_temp'] for s in stats if s['avg_temp'] is not None) / len([s for s in stats if s['avg_temp'] is not None])
    return {'heating_days': avg_heating_days, 'heating_season_avg_temp': avg_heating_temp}

def calculate_heating_degree_days(df):
    if df is None or df.empty: return None
    df = df.set_index('Date').sort_index()
    df = df.groupby(df.index.date)['Temperature'].mean().rename_axis('Date').to_frame()
    df.index = pd.to_datetime(df.index)
    full_dates = pd.date_range(df.index.min(), df.index.max(), freq='D')
    df = df.reindex(full_dates)
    
    is_heating_day = (df['Temperature'] < 13).fillna(False)
    run_id = (is_heating_day != is_heating_day.shift(1)).cumsum()
    heating_mask = pd.Series(False, index=df.index)
    for _, run in is_heating_day.groupby(run_id):
        if run.iloc[0] and len(run) >= 2: heating_mask.loc[run.index] = True
            
    tint = 20.0
    df_hdd = df.loc[heating_mask, 'Temperature'].dropna()
    hdd_values = (tint - df_hdd).clip(lower=0)
    
    if len(df_hdd.index.year.unique()) == 0: return None
    return float(hdd_values.groupby(hdd_values.index.year).sum().mean())

def calculate_design_outdoor_temperature(df):
    if df is None or df.empty: return None
    yearly_min_3day_avgs = []
    for year, year_data in df.groupby(df['Date'].dt.year):
        if len(year_data) < 3: continue
        rolling_3day = year_data['Temperature'].rolling(window=3, center=True).mean()
        yearly_min_3day_avgs.append(rolling_3day.min())
    if yearly_min_3day_avgs: return sum(yearly_min_3day_avgs) / len(yearly_min_3day_avgs)
    return None

def calculate_heating_engineering_stats(wsi_code):
    df = load_temperature_dataframe(wsi_code)
    if df is None: return None
    return {
        'monthly_averages': calculate_monthly_averages(df),
        'heating_days': calculate_heating_season_characteristics(df)['heating_days'],
        'heating_season_avg_temp': calculate_heating_season_characteristics(df)['heating_season_avg_temp'],
        'heating_degree_days': calculate_heating_degree_days(df),
        'design_temperature': calculate_design_outdoor_temperature(df)
    }

def calculate_5year_average_temperature(wsi_code):
    df = load_temperature_dataframe(wsi_code)
    if df is None or df.empty: return None
    most_recent_date = df['Date'].max()
    five_years_ago = most_recent_date - timedelta(days=365*5)
    recent_data = df[df['Date'] >= five_years_ago]
    if recent_data.empty: return None
    return recent_data['Temperature'].mean()

def create_street_view_component(lat, lon):
    """Create multiple street view previews from different angles"""
    if GOOGLE_MAPS_API_KEY:
        angles = [0, 90, 180, 270]
        cols = st.columns(2)
        for idx, angle in enumerate(angles):
            with cols[idx % 2]:
                streetview_url = f"https://www.google.com/maps/embed/v1/streetview?key={GOOGLE_MAPS_API_KEY}&location={lat},{lon}&heading={angle}"
                components.iframe(streetview_url, width=400, height=300, scrolling=False)
                st.caption(f"Direction: {['North', 'East', 'South', 'West'][idx]}")
    else:
        # Fallback to multiple links
        st.subheader("🌐 Street View Preview")
        embed_url = f"https://www.google.com/maps?q=&layer=c&cbll={lat},{lon}&cbp=12,0,0,0,5"
        fallback_url = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}"
        st.markdown(
            f"""
            <div style="width: 100%; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; padding: 15px;">
                <div style="background: #1f2937; padding: 10px; color: white; font-weight: bold; border-radius: 5px;">🌐 Street View Preview</div>
                <div style="padding: 15px; background: #f8f9fa; text-align: center; margin-top: 10px;">
                    <p>Google Street View preview requires API key. Click below to view on Google Maps:</p>
                    <a href="{fallback_url}" target="_blank" style="background-color: #4285f4; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block; margin-top: 6px;">🗺️ Open Street View in Google Maps</a>
                </div>
            </div>
            """, unsafe_allow_html=True
        )

def create_station_map(user_lat, user_lon, nearest_station, avg_temp, heating_stats, vysledek_povodne):
    station_map = folium.Map(location=[user_lat, user_lon], zoom_start=14)

    if vysledek_povodne != "OK" and vysledek_povodne is not None:
        if vysledek_povodne == "Q5":
            shp_path = MAPA_Q5
            barva = "#ff0000"
        elif vysledek_povodne == "Q20":
            shp_path = MAPA_Q20
            barva = "#ff8800"
        else:
            shp_path = MAPA_Q100
            barva = "#ffd700"

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
                        'fillColor': barva,
                        'color': barva,
                        'weight': 2,
                        'fillOpacity': 0.4
                    }
                ).add_to(station_map)
        except Exception as e:
            pass

    folium.CircleMarker(
        location=[user_lat, user_lon],
        radius=8,
        color='red',
        fill=True,
        fill_color='red',
        fill_opacity=0.9,
        popup='Vaše budova'
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
            location=[nearest_station['latitude'], nearest_station['longitude']],
            popup=folium.Popup(popup_html, max_width=500),
            icon=folium.Icon(color='blue', icon='cloud')
        ).add_to(station_map)

    return station_map

def main():
    st.set_page_config(page_title="Zelení drancovníci", page_icon="💚", layout="wide")

    # Inicializace session state proměnných
    if 'analysis' not in st.session_state: st.session_state.analysis = None
    if 'building_data' not in st.session_state: st.session_state.building_data = None
    if 'analysis_requested' not in st.session_state: st.session_state.analysis_requested = False

    # --- 1. LOGIKA ZOBRAZENÍ ÚVODU NEBO RESET TLAČÍTKA ---
    if not st.session_state.analysis_requested:
        # Úvodní sekce se zobrazí jen pokud nebyl spuštěn výpočet
        st.title("Zelení drancovníci (bodov) aka Štítkovači z päťky")
        st.markdown("""
        <div style="font-size: 22px; line-height: 1.6; text-align: justify; color: #2E7D32;">
            <b>Sme elitná jednotka, ktorá v ESG vidí viac než len 3 písmená.</b><br>
            Naším revírom sú <b>dáta</b>, naším tempom je globálne otepľovanie a 
            naším nepriateľom každá budova, ktorá „kúri pánubohu do okien“.
        </div>
        <br>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background-color: #E8F5E9; border-left: 5px solid #2E7D32; padding: 15px; border-radius: 5px;">
            <span style="color: #2E7D32; font-weight: bold;">Naše motto:</span> 
            <i style="color: #1B5E20;">„Meriame všetko, čo tečie, páli alebo má súpisné číslo. Body drancujeme s nulovou uhlíkovou stopou!“</i>
        </div>
        <br>
        """, unsafe_allow_html=True)

        st.write("### Čo reálne stvárame?")
        col1, col2 = st.columns(2)
        with col1:
            st.write("🔍 **Registroví archeológovia**")
            st.markdown("V katastri nehnuteľností sa hrabeme radšej než krtko v záhrade.")
            st.write("🌊 **Povodňová hliadka**")
            st.markdown("Meriame hladinu vody skôr, než si stihnete obuť gumáky.")
        with col2:
            st.write("🏠 **Lovci štítkov**")
            st.markdown("Odhadujeme energetickú náročnosť budov s presnosťou, z ktorej majiteľom naskakuje mráz po chrbte.")
            st.write("🔥 **Teplotní detektívi**")
            st.markdown("Analyzujeme horúčavy tak detailne, že vieme, kedy v Prahe začnete sadiť banány.")
    else:
        # Po spuštění výpočtu úvod zmizí a objeví se tlačítko pro návrat
        if st.button("🔄 Vyhledat novou nemovitost", type="primary"):
            st.session_state.analysis = None
            st.session_state.analysis_requested = False
            st.session_state.building_data = None
            st.rerun()
        st.markdown("---")

    # --- 2. SIDEBAR - VYHLEDÁVÁNÍ (Sidebar) ---
    st.sidebar.header("🏘️ Building Search")
    with st.spinner("Loading station data..."):
        temperature_stations = load_temperature_stations()
        stations = load_station_metadata(temperature_stations)

    building_id = st.sidebar.number_input("🔢 ID nemovitosti (Building ID):", value=0, min_value=0, step=1, key="building_id_input")
    
    if st.sidebar.button("🔍 Vyhledat budovu", type="primary", key="search_building"):
        if building_id == 0:
            st.sidebar.error("❌ Prosím zadejte platné ID budovy")
        else:
            with st.spinner("Vyhledávám budovu v RÚIAN..."):
                building_info = building_search.get_building_full_data_by_id(int(building_id))
                if building_info['status'] == 'ok':
                    st.session_state.building_data = building_info
                    st.session_state.analysis = None
                    st.session_state.analysis_requested = False # Reset při novém hledání
                    st.sidebar.success(f"✅ Budova nalezena!")
                else:
                    st.sidebar.error(f"❌ {building_info['message']}")
                    st.session_state.building_data = None

    # Tlačítko pro výpočet se objeví až po nalezení budovy
    if st.session_state.building_data:
        st.sidebar.markdown(f"**Vybraná budova:** {st.session_state.building_data['nadrazene_prvky'].get('Obec', 'N/A')}")
        if st.sidebar.button("📊 Spočítej statistiku", type="secondary"):
            st.session_state.analysis_requested = True
            st.rerun()

    # --- 3. ZOBRAZENÍ VÝSLEDKŮ ---
    if st.session_state.analysis_requested:
        # Vytvoření záložek (RUIAN se načte hned)
        tab_ruian, tab_analyza = st.tabs([
            "🏢 RUIAN & StreetView", 
            "🌡️ Analýza rizika (Teplota & Povodně)"
        ])

        # KARTA 1: Data z RÚIAN (Okamžité zobrazení)
        with tab_ruian:
            b_data = st.session_state.building_data
            st.subheader("🏢 Data z RÚIAN")
            nad_cols = st.columns(3)
            for i, (k, v) in enumerate(b_data['nadrazene_prvky'].items()):
                with nad_cols[i % 3]: st.markdown(f"**{k}**: `{v if v else '---'}`")
            st.markdown("---")
            st.markdown("#### ⚙️ Technické a ekonomické atributy")
            tech = {k: v for k, v in b_data['technicko_ekonomicke_atributy'].items() if v}
            t_cols = st.columns(2)
            for i, (k, v) in enumerate(tech.items()):
                with t_cols[i % 2]: st.markdown(f"**{k}**: {v}")
            st.markdown("---")
            st.subheader("📍 Náhled polohy (Street View)")
            create_street_view_component(b_data['geometrie']['lat'], b_data['geometrie']['lon'])

        # KARTA 2: Analýza rizika (Pomalé načítání)
        with tab_analyza:
            if st.session_state.analysis is None:
                # Výpočet proběhne pouze jednou a uloží se do session_state
                with st.spinner("⏳ Provádím analýzu okolí a kontrolu povodní (může to trvat)..."):
                    lat, lon = b_data['geometrie']['lat'], b_data['geometrie']['lon']
                    nearest = find_nearest_station(lat, lon, stations)
                    if nearest:
                        avg_temp = calculate_5year_average_temperature(nearest['wsi_code'])
                        h_stats = calculate_heating_engineering_stats(nearest['wsi_code'])
                        # Kontrola povodní
                        q5 = povodne.zkontroluj_povoden(lat, lon, MAPA_Q5)
                        q20 = povodne.zkontroluj_povoden(lat, lon, MAPA_Q20)
                        q100 = povodne.zkontroluj_povoden(lat, lon, MAPA_Q100)
                        stav = "Q5" if q5 else "Q20" if q20 else "Q100" if q100 else "OK"
                        
                        st.session_state.analysis = {
                            'nearest': nearest, 'avg_temp': avg_temp,
                            'heating_stats': h_stats, 'povoden': stav,
                            'lat': lat, 'lon': lon
                        }
                        st.rerun()
            else:
                # Zobrazení hotových výsledků
                res = st.session_state.analysis
                h_stats = res['heating_stats']
                
                st.subheader("🌊 Environmentální ESG Riziko")
                if res['povoden'] == "OK": 
                    st.success("🟢 **BEZPEČNO:** Budova leží mimo záplavové oblasti.")
                else: 
                    st.error(f"🔴 **RIZIKO:** Zóna {res['povoden']}!")
                
                st.markdown("---")
                st.subheader("🌡️ Teplotní a energetická analýza")
                
                if h_stats:
                    st.markdown("#### ⚡ Energetické parametry")
                    e_col1, e_col2, e_col3, e_col4 = st.columns(4)
                    e_col1.metric("5letý průměr", f"{res['avg_temp']:.2f} °C")
                    e_col2.metric("Topné dny", f"{h_stats['heating_days']:.0f} d/r")
                    e_col3.metric("Sezónní průměr", f"{h_stats['heating_season_avg_temp']:.1f} °C")
                    e_col4.metric("HDD (Denostupně)", f"{h_stats['heating_degree_days']:.0f}")

                    st.subheader("📊 Průměrné měsíční teploty")
                    months_ordered = ['Leden', 'Únor', 'Březen', 'Duben', 'Květen', 'Červen', 'Červenec', 'Srpen', 'Září', 'Říjen', 'Listopad', 'Prosinec']
                    temps = [h_stats['monthly_averages'].get(i+1, 0) for i in range(12)]
                    chart_data = pd.DataFrame({
                        'Měsíc': pd.Categorical(months_ordered, categories=months_ordered, ordered=True),
                        'Teplota (°C)': temps
                    })
                    st.bar_chart(chart_data, x='Měsíc', y='Teplota (°C)')

                st.subheader("🗺️ Interaktivní mapa rizika")
                st_folium(create_station_map(res['lat'], res['lon'], res['nearest'], res['avg_temp'], h_stats, res['povoden']), width=800, height=500, key="mapa_rizika")

    st.markdown("---")
    st.markdown("*Zdroj dat: RÚIAN | ČHMÚ | VÚV TGM*")
    
if __name__ == "__main__":
    main()