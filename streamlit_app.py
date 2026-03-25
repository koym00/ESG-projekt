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
import ruian_api

# Configuration
ZIP_PATH = "temp/Metadata/meta1.zip"
CSV_FILENAME = "meta1.csv"
META2_ZIP_PATH = "temp/Metadata/meta2.zip"
META2_CSV_FILENAME = "meta2.csv"
TEMPERATURE_DIR = "temp/Data/Temperature"

# Definice povodňových map (nyní bezpečně namířené do složky temp a s PŘESNÝMI velkými/malými písmeny!)
MAPA_Q5 = "temp/D01_ZaplUzemi5Vody.shp"
MAPA_Q20 = "temp/D02_ZaplUzemi20vody.shp"
MAPA_Q100 = "temp/D03_ZaplUzemi100vody.shp"

# Google Street View Configuration
GOOGLE_MAPS_API_KEY = "AIzaSyCiGoJ6R6ftPoO6WMdvPWuSkV7jWgecxJg"  # Replace with your API key or leave as None for fallback
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
    if GOOGLE_MAPS_API_KEY:
        streetview_url = f"https://www.google.com/maps/embed/v1/streetview?key={GOOGLE_MAPS_API_KEY}&location={lat},{lon}"
        components.iframe(streetview_url, width=800, height=300, scrolling=False)
    else:
        embed_url = f"https://www.google.com/maps?q=&layer=c&cbll={lat},{lon}&cbp=12,0,0,0,5"
        fallback_url = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}"
        st.markdown(
            f"""
            <div style="width: 800px; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
                <div style="background: #1f2937; padding: 10px; color: white; font-weight: bold;">🌐 Street View Preview</div>
                <iframe src="{embed_url}" width="800" height="300" style="border: none;" allowfullscreen loading="lazy"></iframe>
                <div style="padding: 10px; background: #f8f9fa; text-align: center;">
                    <a href="{fallback_url}" target="_blank" style="background-color: #4285f4; color: white; padding: 8px 16px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block; margin-top: 6px;">🗺️ Open in Google Maps</a>
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
    st.set_page_config(page_title="Meteorological Station Analyzer", page_icon="🌡️", layout="wide")
    st.title("🌡️ Meteorological Station Analyzer")
    st.markdown("Find the nearest temperature-measuring station and analyze heating engineering statistics.")

    st.sidebar.header("📍 Location Input")

    page = st.sidebar.radio("Vyberte stránku:", ["Teplota & Povodně", "RUIAN"])

    with st.spinner("Loading station data..."):
        temperature_stations = load_temperature_stations()
        stations = load_station_metadata(temperature_stations)

    if not stations:
        st.error("❌ Unable to load station data. Please check file paths.")
        return

    st.sidebar.success(f"✅ Loaded {len(stations)} temperature-measuring stations")

    if 'analysis' not in st.session_state: st.session_state.analysis = None
    if 'last_coords' not in st.session_state: st.session_state.last_coords = (None, None)

    user_lat = st.sidebar.number_input("Latitude (GEOGR2)", value=50.1254, format="%.6f", key="input_lat")
    user_lon = st.sidebar.number_input("Longitude (GEOGR1)", value=14.4539, format="%.6f", key="input_lon")

    if st.session_state.last_coords != (user_lat, user_lon):
        st.session_state.analysis = None
        st.session_state.last_coords = (user_lat, user_lon)

    if st.sidebar.button("🔍 Calculate Statistics", type="primary", key="calculate"):
        with st.spinner("Finding nearest station and calculating statistics... (Checking flood zones may take a few seconds)"):
            nearest = find_nearest_station(user_lat, user_lon, stations)

            if nearest:
                avg_temp = calculate_5year_average_temperature(nearest['wsi_code'])
                heating_stats = calculate_heating_engineering_stats(nearest['wsi_code'])
                
                q5 = povodne.zkontroluj_povoden(user_lat, user_lon, MAPA_Q5)
                q20 = povodne.zkontroluj_povoden(user_lat, user_lon, MAPA_Q20)
                q100 = povodne.zkontroluj_povoden(user_lat, user_lon, MAPA_Q100)

                if q5: vysledek_povodne = "Q5"
                elif q20: vysledek_povodne = "Q20"
                elif q100: vysledek_povodne = "Q100"
                else: vysledek_povodne = "OK"

                ruian_info = None
                try:
                    ruian_info = ruian_api.get_building_info_from_point(user_lat, user_lon)
                except Exception as e:
                    ruian_info = {'status': 'error', 'message': f"Chyba při načítání RUIAN: {e}"}

                st.session_state.analysis = {
                    'nearest': nearest, 'avg_temp': avg_temp,
                    'heating_stats': heating_stats, 'povoden': vysledek_povodne,
                    'ruian': ruian_info
                }
            else:
                st.session_state.analysis = {'error': "No suitable station found near your location."}

    if st.session_state.analysis:
        if 'error' in st.session_state.analysis:
            st.error(f"❌ {st.session_state.analysis['error']}")
        else:
            nearest = st.session_state.analysis['nearest']
            avg_temp = st.session_state.analysis['avg_temp']
            heating_stats = st.session_state.analysis['heating_stats']
            stav = st.session_state.analysis['povoden']
            ruian_info = st.session_state.analysis.get('ruian')

            # ==================== STRÁNKA 1: Teplota & Povodně ====================
            if page == "Teplota & Povodně":
                st.subheader("🌊 Environmentální ESG Riziko")
                if stav == "Q5": st.error("🔴 **EXTRÉMNÍ RIZIKO:** Budova leží v zóně 5leté vody (Q5)!")
                elif stav == "Q20": st.warning("🟠 **VYSOKÉ RIZIKO:** Budova leží v zóně 20leté vody (Q20)!")
                elif stav == "Q100": st.info("🟡 **ZVÝŠENÉ RIZIKO:** Budova leží v zóně 100leté vody (Q100).")
                else: st.success("🟢 **BEZPEČNO:** Budova leží zcela mimo záplavové oblasti (Q5, Q20, Q100).")
                st.markdown("---")

                col1, col2, col3 = st.columns(3)
                with col1: st.metric("📍 Nearest Station", nearest['name'])
                with col2: st.metric("📏 Distance", f"{nearest['distance']:.2f} km")
                with col3: st.metric("🏔️ Elevation", f"{nearest['elevation']} m")

                st.subheader("🌡️ Temperature Overview")
                temp_col1, temp_col2 = st.columns(2)
                with temp_col1:
                    st.metric("5-Year Average Temperature", f"{avg_temp:.2f} °C" if avg_temp is not None else "N/A")
                with temp_col2:
                    st.metric("Design Outdoor Temperature", f"{heating_stats['design_temperature']:.1f} °C" if heating_stats and heating_stats['design_temperature'] is not None else "N/A")

                if heating_stats and heating_stats['monthly_averages']:
                    st.subheader("📊 Monthly Average Temperatures")
                    monthly_data = heating_stats['monthly_averages']
                    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                    temps = [monthly_data.get(i+1, 0) for i in range(12)]
                    month_categories = pd.Categorical(months, categories=months, ordered=True)
                    chart_data = pd.DataFrame({'Month': month_categories, 'Temperature (°C)': temps}).set_index('Month')
                    st.bar_chart(chart_data)

                if heating_stats:
                    st.subheader("⚡ Energy Report")
                    report_cols = st.columns(4)
                    with report_cols[0]: st.metric("Heating Days", f"{heating_stats['heating_days']:.0f} days/year" if heating_stats['heating_days'] is not None else "N/A")
                    with report_cols[1]: st.metric("Heating Season Avg", f"{heating_stats['heating_season_avg_temp']:.1f} °C" if heating_stats['heating_season_avg_temp'] is not None else "N/A")
                    with report_cols[2]: st.metric("Heating Degree Days", f"{heating_stats['heating_degree_days']:.0f} HDD/year" if heating_stats['heating_degree_days'] is not None else "N/A")
                    with report_cols[3]: st.metric("Design Temperature", f"{heating_stats['design_temperature']:.1f} °C" if heating_stats['design_temperature'] is not None else "N/A")

                st.subheader("📍 Location Preview")
                create_street_view_component(user_lat, user_lon)

                st.subheader("🗺️ Interactive Map")
                station_map = create_station_map(user_lat, user_lon, nearest, avg_temp, heating_stats, stav)
                st_folium(station_map, width=800, height=500)

            # ==================== STRÁNKA 2: RUIAN ====================
            if page == "RUIAN":
                st.subheader("🏢 RUIAN data")
                if not ruian_info:
                    st.info("RUIAN data nejsou k dispozici.")
                elif ruian_info.get('status') == 'error':
                    st.error(f"❌ {ruian_info.get('message')}")
                elif ruian_info.get('status') == 'not_found':
                    st.warning(f"⚠️ {ruian_info.get('message')}")
                    if 'address' in ruian_info:
                        st.json(ruian_info['address'])
                else:
                    st.markdown(f"**Adresa:** {ruian_info.get('address', 'N/A')}  ")
                    st.markdown(f"**Kód budovy:** {ruian_info.get('building_code', 'N/A')}  ")
                    st.markdown("**Vlastnosti budovy:**")
                    st.json(ruian_info.get('building_data', {}))
                    st.markdown("**Surová data building:**")
                    st.json(ruian_info.get('raw_building_data', {}))
                    st.markdown("**Surová data adresy:**")
                    st.json(ruian_info.get('raw_address_data', {}))

    st.markdown("---")
    st.markdown("*Data source: Czech Hydrometeorological Institute (CHMI) | Flood data: VÚV TGM*")

if __name__ == "__main__":
    main()