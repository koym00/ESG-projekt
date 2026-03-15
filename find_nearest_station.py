"""
Find Nearest Meteorological Station & Calculate Heating Engineering Statistics

This script finds the nearest meteorological station that measures temperature based on 
user-provided geographic coordinates, calculates the 5-year average temperature, and
computes comprehensive heating engineering statistics. Results are displayed in the
terminal and on an interactive map.

Requirements:
- Input: User provides Latitude (GEOGR2) and Longitude (GEOGR1)
- Metadata: C:\\temp\\Metadata\\meta1.zip (station locations) and meta2.zip (capabilities)
- Temperature: C:\\temp\\Data\\Temperature\\dly-{WSI}-T.zip containing temperature data
- Filtering: Only active stations (END_DATE starts with "3999") that measure temperature (EG_EL_ABBREVIATION = "T")
- Calculations: Monthly averages, heating season characteristics, heating degree days, design outdoor temperature
- Output: Nearest temperature-measuring station details with distance, 5-year temperature average, heating engineering statistics, and interactive map
"""

import zipfile
import csv
import math
import sys
import io
import os
from datetime import datetime, timedelta
import folium
import webbrowser
import pandas as pd

# Configuration
ZIP_PATH = r"C:\temp\Metadata\meta1.zip"
CSV_FILENAME = "meta1.csv"
META2_ZIP_PATH = r"C:\temp\Metadata\meta2.zip"
META2_CSV_FILENAME = "meta2.csv"
TEMPERATURE_DIR = r"C:\temp\Data\Temperature"

# Earth's radius in kilometers
EARTH_RADIUS_KM = 6371


def load_temperature_stations():
    """
    Load WSI codes of stations that measure temperature from meta2.csv.
    
    Returns:
        Set of WSI codes that measure temperature (EG_EL_ABBREVIATION = "T")
    """
    temperature_stations = set()
    
    try:
        with zipfile.ZipFile(META2_ZIP_PATH, 'r') as zf:
            with zf.open(META2_CSV_FILENAME, 'r') as csvfile:
                text_file = io.TextIOWrapper(csvfile, encoding='utf-8')
                reader = csv.reader(text_file, delimiter=',')
                next(reader, None)  # Skip header row
                
                for row in reader:
                    if len(row) < 5:  # Ensure we have enough columns
                        continue
                        
                    try:
                        wsi_code = row[1]  # Column B (index 1): WSI
                        element = row[4]  # Column E (index 4): EG_EL_ABBREVIATION
                        
                        # Add to set if it measures temperature
                        if element == "T":
                            temperature_stations.add(wsi_code)
                            
                    except (ValueError, IndexError) as e:
                        continue
                        
    except FileNotFoundError:
        print(f"Warning: Temperature capability data not found at {META2_ZIP_PATH}")
        print("Proceeding without temperature measurement filtering...")
    except zipfile.BadZipFile:
        print(f"Warning: Invalid meta2 ZIP file at {META2_ZIP_PATH}")
        print("Proceeding without temperature measurement filtering...")
    except Exception as e:
        print(f"Warning: Error reading temperature capability data: {e}")
        print("Proceeding without temperature measurement filtering...")
    
    return temperature_stations


def load_temperature_dataframe(wsi_code):
    """
    Load temperature data for a station into a pandas DataFrame.
    
    Args:
        wsi_code: The WSI code of the station
        
    Returns:
        pandas DataFrame with Date and Temperature columns, or None if error
    """
    zip_path = find_temperature_zip_path(wsi_code)
    csv_filename = f"dly-{wsi_code}-T.csv"
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            with zf.open(csv_filename, 'r') as csvfile:
                text_file = io.TextIOWrapper(csvfile, encoding='utf-8')
                
                # Read CSV data
                data = []
                reader = csv.reader(text_file, delimiter=',')
                next(reader, None)  # Skip header row
                
                for row in reader:
                    if len(row) < 5:  # Ensure we have enough columns
                        continue
                        
                    try:
                        dt_str = row[3]  # Column D (index 3): DT (Date/Time)
                        value_str = row[4]  # Column E (index 4): VALUE
                        
                        # Skip empty values
                        if not value_str or value_str.strip() == '':
                            continue
                            
                        # Parse date (ISO 8601 format like 2025-12-09T20:00Z)
                        date_part = dt_str.split('T')[0]
                        dt = datetime.strptime(date_part, '%Y-%m-%d')
                        temperature = float(value_str)
                        
                        data.append({'Date': dt, 'Temperature': temperature})
                        
                    except (ValueError, IndexError) as e:
                        continue
                
                if not data:
                    return None
                
                # Create DataFrame
                df = pd.DataFrame(data)
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.sort_values('Date').reset_index(drop=True)
                
                return df
    
    except FileNotFoundError:
        return None
    except Exception as e:
        return None


def calculate_monthly_averages(df):
    """
    Calculate average temperature for each month over the 5-year period.
    
    Args:
        df: pandas DataFrame with Date and Temperature columns
        
    Returns:
        Dictionary with month names as keys and average temperatures as values
    """
    if df is None or df.empty:
        return {month: None for month in range(1, 13)}
    
    # Group by month and calculate mean
    monthly_avg = df.groupby(df['Date'].dt.month)['Temperature'].mean()
    
    # Create dictionary for all months
    monthly_averages = {}
    for month in range(1, 13):
        monthly_averages[month] = monthly_avg.get(month, None)
    
    return monthly_averages


def calculate_heating_season_characteristics(df):
    """
    Calculate heating season characteristics based on Czech standards.
    
    Args:
        df: pandas DataFrame with Date and Temperature columns
        
    Returns:
        Dictionary with heating_days and heating_season_avg_temp
    """
    if df is None or df.empty:
        return {'heating_days': None, 'heating_season_avg_temp': None}
    
    # Ensure the Date column is the index and sorted
    df = df.set_index('Date').sort_index()
    
    # If there are multiple readings per day, average them to a single daily value
    df = df.groupby(df.index.date)['Temperature'].mean().rename_axis('Date')
    df = df.to_frame()
    df.index = pd.to_datetime(df.index)
    
    # Fill missing days with NaN to properly break consecutive runs
    full_dates = pd.date_range(df.index.min(), df.index.max(), freq='D')
    df = df.reindex(full_dates)
    
    # Heating day criterion (temp < 13°C)
    is_heating_day = df['Temperature'] < 13
    is_heating_day = is_heating_day.fillna(False)
    
    # Identify heating runs (consecutive heating days)
    run_id = (is_heating_day != is_heating_day.shift(1)).cumsum()
    heating_mask = pd.Series(False, index=df.index)
    
    for _, run in is_heating_day.groupby(run_id):
        if run.iloc[0] and len(run) >= 2:
            heating_mask.loc[run.index] = True
    
    # Annual statistics
    stats = []
    for year, group in df.groupby(df.index.year):
        year_mask = heating_mask.loc[group.index]
        year_temps = group['Temperature'].loc[year_mask]
        
        if year_mask.sum() == 0:
            continue
        
        stats.append({
            'year': year,
            'days': int(year_mask.sum()),
            'avg_temp': float(year_temps.mean()) if not year_temps.empty else None
        })
    
    if not stats:
        return {'heating_days': None, 'heating_season_avg_temp': None}
    
    avg_heating_days_per_year = sum(s['days'] for s in stats) / len(stats)
    avg_heating_temp = sum(s['avg_temp'] for s in stats if s['avg_temp'] is not None) / len([s for s in stats if s['avg_temp'] is not None])
    
    return {
        'heating_days': avg_heating_days_per_year,
        'heating_season_avg_temp': avg_heating_temp
    }


def calculate_heating_degree_days(df):
    """
    Calculate heating degree days using the formula D = sum(Tint - Te,i)
    where Tint = 20°C and only for heating days.
    
    Args:
        df: pandas DataFrame with Date and Temperature columns
        
    Returns:
        Average annual heating degree days
    """
    if df is None or df.empty:
        return None
    
    # Ensure consistent date index
    df = df.set_index('Date').sort_index()
    
    # If multiple readings per day exist, average them to one value per day
    df = df.groupby(df.index.date)['Temperature'].mean().rename_axis('Date')
    df = df.to_frame()
    df.index = pd.to_datetime(df.index)
    
    full_dates = pd.date_range(df.index.min(), df.index.max(), freq='D')
    df = df.reindex(full_dates)
    
    # Identify heating days using same method as heating season characteristics
    is_heating_day = (df['Temperature'] < 13).fillna(False)
    run_id = (is_heating_day != is_heating_day.shift(1)).cumsum()
    heating_mask = pd.Series(False, index=df.index)
    for _, run in is_heating_day.groupby(run_id):
        if run.iloc[0] and len(run) >= 2:
            heating_mask.loc[run.index] = True
    
    # Calculate HDD only on heating days
    tint = 20.0
    df_hdd = df.loc[heating_mask, 'Temperature'].dropna()
    hdd_values = (tint - df_hdd).clip(lower=0)
    
    years = df_hdd.index.year.unique()
    if len(years) == 0:
        return None
    
    # Sum HDD per year then average
    yearly_hdd = hdd_values.groupby(hdd_values.index.year).sum()
    avg_hdd_per_year = yearly_hdd.mean()
    
    return float(avg_hdd_per_year)


def calculate_design_outdoor_temperature(df):
    """
    Calculate design outdoor temperature as the average of the coldest 3-day 
    window averages for each year, then average those yearly minimums.
    
    Args:
        df: pandas DataFrame with Date and Temperature columns
        
    Returns:
        Design outdoor temperature
    """
    if df is None or df.empty:
        return None
    
    yearly_min_3day_avgs = []
    
    # Group by year
    for year, year_data in df.groupby(df['Date'].dt.year):
        if len(year_data) < 3:
            continue
            
        # Calculate 3-day rolling averages
        rolling_3day = year_data['Temperature'].rolling(window=3, center=True).mean()
        
        # Find the minimum 3-day average for this year
        min_3day_avg = rolling_3day.min()
        yearly_min_3day_avgs.append(min_3day_avg)
    
    # Average the yearly minimums
    if yearly_min_3day_avgs:
        design_temp = sum(yearly_min_3day_avgs) / len(yearly_min_3day_avgs)
        return design_temp
    
    return None


def calculate_heating_engineering_stats(wsi_code):
    """
    Calculate all heating engineering statistics for a station.
    
    Args:
        wsi_code: The WSI code of the station
        
    Returns:
        Dictionary with all heating engineering statistics
    """
    # Load temperature data
    df = load_temperature_dataframe(wsi_code)
    
    if df is None:
        return None
    
    # Calculate all statistics
    monthly_averages = calculate_monthly_averages(df)
    heating_characteristics = calculate_heating_season_characteristics(df)
    heating_degree_days = calculate_heating_degree_days(df)
    design_temperature = calculate_design_outdoor_temperature(df)
    
    return {
        'monthly_averages': monthly_averages,
        'heating_days': heating_characteristics['heating_days'],
        'heating_season_avg_temp': heating_characteristics['heating_season_avg_temp'],
        'heating_degree_days': heating_degree_days,
        'design_temperature': design_temperature
    }


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on Earth using the Haversine formula.

    Args:
        lat1, lon1: Latitude and longitude of first point (in degrees)
        lat2, lon2: Latitude and longitude of second point (in degrees)

    Returns:
        Distance in kilometers
    """
    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Differences
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    # Haversine formula
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def find_nearest_station(user_lat, user_lon, temperature_stations):
    """
    Find the nearest meteorological station to the given coordinates.

    Args:
        user_lat: User's latitude (GEOGR2)
        user_lon: User's longitude (GEOGR1)
        temperature_stations: Set of WSI codes that measure temperature

    Returns:
        Dictionary with nearest station details or None if error
    """
    nearest_station = None
    min_distance = float('inf')

    try:
        with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
            with zf.open(CSV_FILENAME, 'r') as csvfile:
                # Wrap binary stream in text mode for CSV reader
                text_file = io.TextIOWrapper(csvfile, encoding='utf-8')
                reader = csv.reader(text_file, delimiter=',')
                next(reader, None)  # Skip header row

                for row in reader:
                    if len(row) < 8:  # Ensure we have enough columns
                        continue

                    try:
                        # Extract data from CSV columns
                        wsi_code = row[0]  # Column A (index 0): WSI code
                        end_date = row[3]  # Column D (index 3): END_DATE
                        
                        # Filter: Only process active stations (END_DATE starts with "3999")
                        if not end_date.startswith("3999"):
                            continue
                            
                        # Filter: Only consider stations that measure temperature
                        if temperature_stations and wsi_code not in temperature_stations:
                            continue
                            
                        full_name = row[4]  # Column E (index 4): FULL_NAME
                        geogr1 = float(row[5])  # Column F (index 5): GEOGR1 (Longitude)
                        geogr2 = float(row[6])  # Column G (index 6): GEOGR2 (Latitude)
                        elevation = row[7]  # Column H (index 7): ELEVATION

                        # Calculate distance
                        distance = haversine_distance(user_lat, user_lon, geogr2, geogr1)

                        # Update nearest station if this is closer
                        if distance < min_distance:
                            min_distance = distance
                            nearest_station = {
                                'wsi_code': wsi_code,
                                'name': full_name,
                                'longitude': geogr1,
                                'latitude': geogr2,
                                'elevation': elevation,
                                'distance': distance
                            }

                    except (ValueError, IndexError) as e:
                        # Skip rows with invalid data
                        continue

    except FileNotFoundError:
        print(f"Error: ZIP file not found at {ZIP_PATH}")
        return None
    except zipfile.BadZipFile:
        print(f"Error: Invalid ZIP file at {ZIP_PATH}")
        return None
    except Exception as e:
        print(f"Error reading ZIP file: {e}")
        return None

    return nearest_station


def find_temperature_zip_path(wsi_code):
    """
    Construct the path to the temperature ZIP file based on WSI code.
    
    Args:
        wsi_code: The WSI code of the station
        
    Returns:
        Full path to the temperature ZIP file
    """
    filename = f"dly-{wsi_code}-T.zip"
    return os.path.join(TEMPERATURE_DIR, filename)


def calculate_5year_average_temperature(wsi_code):
    """
    Calculate the 5-year average temperature for a station.
    
    Args:
        wsi_code: The WSI code of the station
        
    Returns:
        5-year average temperature or None if data unavailable
    """
    zip_path = find_temperature_zip_path(wsi_code)
    csv_filename = f"dly-{wsi_code}-T.csv"
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            with zf.open(csv_filename, 'r') as csvfile:
                text_file = io.TextIOWrapper(csvfile, encoding='utf-8')
                reader = csv.reader(text_file, delimiter=',')
                next(reader, None)  # Skip header row
                
                temperatures = []
                most_recent_date = None
                
                for row in reader:
                    if len(row) < 5:  # Ensure we have enough columns
                        continue
                        
                    try:
                        dt_str = row[3]  # Column D (index 3): DT (Date/Time)
                        value_str = row[4]  # Column E (index 4): VALUE
                        
                        # Skip empty values
                        if not value_str or value_str.strip() == '':
                            continue
                            
                        # Parse date (ISO 8601 format like 2025-12-09T20:00Z)
                        # Extract date part before 'T'
                        date_part = dt_str.split('T')[0]
                        dt = datetime.strptime(date_part, '%Y-%m-%d')
                        
                        # Track most recent date
                        if most_recent_date is None or dt > most_recent_date:
                            most_recent_date = dt
                            
                        temperature = float(value_str)
                        temperatures.append((dt, temperature))
                        
                    except (ValueError, IndexError) as e:
                        continue
                
                if not temperatures or most_recent_date is None:
                    return None
                
                # Filter to last 5 years from most recent date
                five_years_ago = most_recent_date - timedelta(days=365*5)
                recent_temperatures = [temp for dt, temp in temperatures if dt >= five_years_ago]
                
                if not recent_temperatures:
                    return None
                
                # Calculate average
                return sum(recent_temperatures) / len(recent_temperatures)
    
    except FileNotFoundError:
        print(f"Temperature data not found for station {wsi_code} at {zip_path}")
        return None
    except zipfile.BadZipFile:
        print(f"Invalid temperature ZIP file for station {wsi_code}")
        return None
    except Exception as e:
        print(f"Error reading temperature data for station {wsi_code}: {e}")
        return None


def main():
    """Main function to run the nearest station finder with temperature analysis."""
    print("Find Nearest Meteorological Station & 5-Year Temperature Average")
    print("=" * 65)

    # Prompt user for coordinates
    try:
        user_lat = float(input("Enter your Latitude (GEOGR2): "))
        user_lon = float(input("Enter your Longitude (GEOGR1): "))
    except ValueError:
        print("Error: Invalid coordinate input. Please enter numeric values.")
        sys.exit(1)

    # Validate coordinate ranges (rough check)
    if not (-90 <= user_lat <= 90):
        print("Error: Latitude must be between -90 and 90 degrees.")
        sys.exit(1)
    if not (-180 <= user_lon <= 180):
        print("Error: Longitude must be between -180 and 180 degrees.")
        sys.exit(1)

    print(f"\nSearching for nearest station to coordinates: ({user_lat}, {user_lon})")
    print("-" * 65)

    # Load temperature-capable stations first
    print("Loading temperature measurement capabilities...")
    temperature_stations = load_temperature_stations()
    if temperature_stations:
        print(f"Found {len(temperature_stations)} stations that measure temperature.")
    else:
        print("No temperature capability data available - searching all active stations.")

    # Find nearest station
    nearest = find_nearest_station(user_lat, user_lon, temperature_stations)

    if nearest:
        print("Nearest Meteorological Station:")
        print(f"  Name: {nearest['name']}")
        print(f"  WSI Code: {nearest['wsi_code']}")
        print(f"  Coordinates: ({nearest['latitude']:.6f}, {nearest['longitude']:.6f})")
        print(f"  Elevation: {nearest['elevation']} meters")
        print(f"  Distance: {nearest['distance']:.2f} km")
        
        # Calculate 5-year average temperature
        print(f"\nCalculating 5-year average temperature...")
        avg_temp = calculate_5year_average_temperature(nearest['wsi_code'])
        
        if avg_temp is not None:
            print(f"  5-Year Average Temperature: {avg_temp:.2f} °C")
        else:
            print("  5-Year Average Temperature: Data not available")
            
        # Calculate heating engineering statistics
        print(f"\nCalculating heating engineering statistics...")
        heating_stats = calculate_heating_engineering_stats(nearest['wsi_code'])
        
        if heating_stats:
            print("  Heating Engineering Statistics (5-year averages):")
            print("  ──────────────────────────────────────────────────")
            
            # Monthly averages
            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            print("  Monthly Average Temperatures (°C):")
            for i, month in enumerate(month_names, 1):
                temp = heating_stats['monthly_averages'][i]
                temp_str = f"{temp:.1f}" if temp is not None else "N/A"
                print(f"    {month}: {temp_str}")
            
            # Heating season
            heating_days = heating_stats['heating_days']
            heating_temp = heating_stats['heating_season_avg_temp']
            hdd = heating_stats['heating_degree_days']
            design_temp = heating_stats['design_temperature']
            
            print(f"  Heating Season: {heating_days:.0f} days/year" if heating_days else "  Heating Season: N/A")
            print(f"  Heating Season Avg Temp: {heating_temp:.1f} °C" if heating_temp else "  Heating Season Avg Temp: N/A")
            print(f"  Heating Degree Days: {hdd:.0f} HDD/year" if hdd else "  Heating Degree Days: N/A")
            print(f"  Design Outdoor Temperature: {design_temp:.1f} °C" if design_temp else "  Design Outdoor Temperature: N/A")
        else:
            print("  Heating Engineering Statistics: Data not available")
            
        # Create and open interactive map
        create_station_map(user_lat, user_lon, nearest, avg_temp, heating_stats)
        
    else:
        print("Error: Could not find nearest station. Please check the data file.")


def create_station_map(user_lat, user_lon, nearest_station, avg_temp, heating_stats):
    """
    Create an interactive folium map showing user location and nearest station.
    
    Args:
        user_lat: User's latitude
        user_lon: User's longitude
        nearest_station: Dictionary with station details
        avg_temp: 5-year average temperature (float or None)
        heating_stats: Dictionary with heating engineering statistics
    """
    # Center map on Czech Republic
    czech_lat, czech_lon = 49.8, 15.5
    
    # Create map
    station_map = folium.Map(location=[czech_lat, czech_lon], zoom_start=7)
    
    # Add user location marker (red circle)
    folium.CircleMarker(
        location=[user_lat, user_lon],
        radius=8,
        color='red',
        fill=True,
        fill_color='red',
        fill_opacity=0.7,
        popup='Input Location'
    ).add_to(station_map)
    
    # Add station marker with popup
    if nearest_station:
        # Format temperature for popup
        temp_text = f"{avg_temp:.2f} °C" if avg_temp is not None else "Data not available"
        
        # Create popup HTML with heating engineering statistics
        popup_html = f"""
        <div style="font-family: Arial, sans-serif; min-width: 400px; max-width: 500px;">
            <h4 style="margin: 0 0 8px 0; color: #2E86C1;">{nearest_station['name']}</h4>
            <p style="margin: 4px 0;"><strong>5-Year Avg Temp:</strong> <span style="color: #E74C3C; font-weight: bold;">{temp_text}</span></p>
            <p style="margin: 4px 0;"><strong>Distance:</strong> {nearest_station['distance']:.2f} km</p>
            <p style="margin: 4px 0;"><strong>Elevation:</strong> {nearest_station['elevation']} m</p>
        """
        
        # Add heating engineering statistics if available
        if heating_stats:
            popup_html += """
            <hr style="margin: 10px 0; border: none; border-top: 1px solid #ddd;">
            <h5 style="margin: 8px 0 6px 0; color: #2E86C1;">Heating Engineering (5-year averages)</h5>
            """
            
            # Monthly averages table
            if heating_stats['monthly_averages']:
                popup_html += """
                <table style="width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 8px;">
                    <tr style="background-color: #f8f9fa;">
                        <th colspan="12" style="padding: 4px; text-align: center; border: 1px solid #ddd; font-weight: bold;">Monthly Average Temperatures (°C)</th>
                    </tr>
                    <tr>
                """
                month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                for i, month in enumerate(month_names, 1):
                    temp = heating_stats['monthly_averages'][i]
                    temp_str = f"{temp:.1f}" if temp is not None else "N/A"
                    popup_html += f'<td style="padding: 2px 4px; text-align: center; border: 1px solid #ddd;">{month}<br/><strong>{temp_str}</strong></td>'
                popup_html += "</tr></table>"
            
            # Heating season statistics
            heating_days = heating_stats['heating_days']
            heating_temp = heating_stats['heating_season_avg_temp']
            hdd = heating_stats['heating_degree_days']
            design_temp = heating_stats['design_temperature']
            
            popup_html += '<table style="width: 100%; border-collapse: collapse; font-size: 12px;">'
            
            if heating_days is not None:
                popup_html += f'<tr><td style="padding: 4px; border: 1px solid #ddd;"><strong>Heating Days:</strong></td><td style="padding: 4px; border: 1px solid #ddd;">{heating_days:.0f} days/year</td></tr>'
            
            if heating_temp is not None:
                popup_html += f'<tr><td style="padding: 4px; border: 1px solid #ddd;"><strong>Heating Season Avg:</strong></td><td style="padding: 4px; border: 1px solid #ddd;">{heating_temp:.1f} °C</td></tr>'
            
            if hdd is not None:
                popup_html += f'<tr><td style="padding: 4px; border: 1px solid #ddd;"><strong>Heating Degree Days:</strong></td><td style="padding: 4px; border: 1px solid #ddd;">{hdd:.0f} HDD/year</td></tr>'
            
            if design_temp is not None:
                popup_html += f'<tr style="background-color: #fff3cd;"><td style="padding: 4px; border: 1px solid #ddd;"><strong>Design Outdoor Temp:</strong></td><td style="padding: 4px; border: 1px solid #ddd; font-weight: bold; color: #8B0000;">{design_temp:.1f} °C</td></tr>'
            
            popup_html += "</table>"
        
        popup_html += "</div>"
        
        folium.Marker(
            location=[nearest_station['latitude'], nearest_station['longitude']],
            popup=folium.Popup(popup_html, max_width=500),
            icon=folium.Icon(color='blue', icon='cloud')
        ).add_to(station_map)
    
    # Save map
    station_map.save('station_map.html')
    print(f"\n✓ Interactive map saved as: station_map.html")
    
    # Open in browser
    try:
        webbrowser.open('station_map.html')
        print("✓ Map opened in default web browser")
    except Exception as e:
        print(f"⚠ Could not open map in browser: {e}")
        print("  You can manually open station_map.html in your web browser")


if __name__ == "__main__":
    main()