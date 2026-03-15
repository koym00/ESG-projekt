#!/usr/bin/env python3
"""
Quick test script for the Streamlit app functions
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

# Import functions from the main app
from streamlit_app import load_temperature_stations, load_station_metadata, haversine_distance

def test_basic_functions():
    """Test basic functions to ensure they work."""
    print("Testing basic functions...")

    # Test Haversine distance
    distance = haversine_distance(50.0, 14.0, 51.0, 15.0)
    print(f"Haversine distance test: {distance:.2f} km")

    # Test loading temperature stations
    try:
        temp_stations = load_temperature_stations()
        print(f"Loaded {len(temp_stations)} temperature station WSI codes")
    except Exception as e:
        print(f"Error loading temperature stations: {e}")
        return False

    # Test loading station metadata
    try:
        stations = load_station_metadata(temp_stations)
        print(f"Loaded {len(stations)} station metadata records")
        if stations:
            print(f"Sample station: {stations[0]['name']} at ({stations[0]['latitude']}, {stations[0]['longitude']})")
    except Exception as e:
        print(f"Error loading station metadata: {e}")
        return False

    print("✅ All basic functions working!")
    return True

if __name__ == "__main__":
    success = test_basic_functions()
    sys.exit(0 if success else 1)