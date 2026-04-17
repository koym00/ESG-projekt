import pandas as pd
import streamlit_app as app # Využijeme existující funkce z vaší aplikace

# 1. Načtení trénovacích dat
df = pd.read_csv('data_stitky_EPC_with_ruian.csv', sep=';', encoding='utf-8')

# 2. Načtení metadat stanic
temp_stations = app.load_temperature_stations()
stations = app.load_station_metadata(temp_stations)

def get_heating_days(lat, lon):
    # Najde nejbližší stanici
    nearest = app.find_nearest_station(lat, lon, stations)
    if nearest:
        # Vypočítá statistiky z historických dat stanice
        stats = app.calculate_heating_engineering_stats(nearest["wsi_code"])
        if stats and stats['heating_days']:
            return stats['heating_days']
    return 220  # Výchozí hodnota (průměr ČR), pokud data chybí

print("Obohacuji data o počet topných dnů...")
df['heating_days'] = df.apply(lambda row: get_heating_days(row['lat_wgs84'], row['lon_wgs84']), axis=1)

# 3. Uložení obohaceného souboru
df.to_csv('data_stitky_EPC_enriched.csv', index=False, sep=';', encoding='utf-8')
print("Hotovo! Soubor data_stitky_EPC_enriched.csv byl vytvořen.")