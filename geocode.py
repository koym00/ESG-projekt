import requests
from pyproj import Transformer

GEOCODE_URL = "https://ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/MapServer/exts/GeocodeSOE/tables/1/reverseGeocode"

def reverse_geocode(lat: float, lon: float):
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:5514", always_xy=True)
    x, y = transformer.transform(lon, lat)

    params = {
        "location": f"{x},{y}",
        "distance": 10,
        "outSR": 4326,
        "f": "json"
    }

    response = requests.get(GEOCODE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()