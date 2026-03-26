import requests
import math
import base64

def calculate_bearing(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def get_optimized_street_view(api_key, target_lat, target_lng):
    metadata_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    meta_resp = requests.get(metadata_url, params={"location": f"{target_lat},{target_lng}", "key": api_key})
    meta_data = meta_resp.json()

    heading = 0
    if meta_data.get("status") == "OK":
        car_lat = meta_data['location']['lat']
        car_lng = meta_data['location']['lng']
        heading = calculate_bearing(car_lat, car_lng, target_lat, target_lng)

    sv_url = "https://maps.googleapis.com/maps/api/streetview"
    params = {
        "size": "600x400",
        "location": f"{target_lat},{target_lng}",
        "key": api_key,
        "heading": heading,
        "pitch": 20,
        "fov": 100
    }
    
    response = requests.get(sv_url, params=params)
    if response.status_code == 200:
        return base64.b64encode(response.content).decode('utf-8')
    return None