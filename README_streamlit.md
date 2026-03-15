# Meteorological Station Analyzer - Streamlit Web App

A Streamlit web application for finding the nearest meteorological station that measures temperature and calculating comprehensive heating engineering statistics.

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application**:
   ```bash
   # Option 1: Using the batch file (Windows)
   run_streamlit.bat

   # Option 2: Direct command
   streamlit run streamlit_app.py
   ```

3. **Open your browser** to `http://localhost:8501`

## Features

- **Nearest Station Finder**: Automatically locates the closest temperature-measuring meteorological station
- **5-Year Temperature Analysis**: Calculates average temperatures over the most recent 5-year period
- **Heating Engineering Statistics**:
  - Monthly average temperatures
  - Heating season characteristics (heating days, average heating temperature)
  - Heating degree days (HDD) calculation
  - Design outdoor temperature for building design
- **Location Preview**: Google Street View integration showing the input location
- **Interactive Map**: Folium-powered map showing user location and station with detailed popups
- **Performance Optimized**: Uses Streamlit caching for fast data loading

## Data Requirements

The application requires CHMI meteorological data to be downloaded and organized as follows:

1. **Metadata**: Download station metadata and save as:
   - `C:\temp\Metadata\meta1.zip` (containing meta1.csv)
   - `C:\temp\Metadata\meta2.zip` (containing meta2.csv)

2. **Temperature Data**: Download temperature data and save as:
   - `C:\temp\Data\Temperature\dly-{WSI_CODE}-T.zip` (containing dly-{WSI_CODE}-T.csv)

## Google Street View Configuration

The app includes a Street View preview of your input location. To enable the embedded Street View:

1. Get a Google Maps API key from the [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the "Maps Embed API" for your project
3. In `streamlit_app.py`, set:
   ```python
   GOOGLE_MAPS_API_KEY = "YOUR_API_KEY_HERE"
   ```

If no API key is provided, the app will show a fallback with a link to open Street View in Google Maps.

## Usage

1. Run the Streamlit application:
```bash
streamlit run streamlit_app.py
```

2. Open your web browser to the displayed URL (typically http://localhost:8501)

3. Enter your coordinates (latitude and longitude) in the sidebar

4. Click "Calculate Statistics" to find the nearest station and view comprehensive heating engineering analysis

## Technical Details

### Heating Engineering Calculations

- **Heating Days**: Days with average temperature < 13°C in consecutive runs of 2+ days
- **Heating Degree Days (HDD)**: Sum of (20°C - daily temperature) for heating days only
- **Design Outdoor Temperature**: Average of the coldest 3-day rolling averages for each year
- **Monthly Averages**: 5-year average temperatures for each month

### Data Processing

- Filters stations to only include active temperature-measuring stations
- Handles multiple daily temperature readings by averaging to single daily values
- Uses Haversine formula for accurate geographic distance calculations
- Implements Czech heating standards for building design calculations

## Dependencies

- `streamlit`: Web application framework
- `streamlit-folium`: Folium map integration for Streamlit
- `pandas`: Data manipulation and analysis
- `folium`: Interactive maps
- `requests`: HTTP requests for data downloading
- `beautifulsoup4`: HTML parsing for web scraping

## Data Source

Data provided by the Czech Hydrometeorological Institute (CHMI).

## License

This project is for educational and research purposes. Please respect CHMI data usage policies.