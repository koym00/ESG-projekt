import streamlit as st
import streamlit.components.v1 as components
import requests
import math
import base64

STREET_VIEW_HEIGHT = 400

def calculate_bearing(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def get_street_view_data(api_key, lat, lon):
    metadata_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    meta_resp = requests.get(metadata_url, params={"location": f"{lat},{lon}", "key": api_key})
    meta_data = meta_resp.json()
    if meta_data.get("status") == "OK":
        car_lat = meta_data['location']['lat']
        car_lng = meta_data['location']['lng']
        heading = calculate_bearing(car_lat, car_lng, lat, lon)
        return heading, True
    return 0, False

def display_street_views(api_key, lat, lon):
    heading, success = get_street_view_data(api_key, lat, lon)

    if not success:
        st.error("Street View pro tuto lokalitu není k dispozici.")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Street View - Interaktivní pohled")
        embed_url = (
            f"https://www.google.com/maps/embed/v1/streetview"
            f"?key={api_key}&location={lat},{lon}&heading={heading}&pitch=10&fov=90"
        )
        components.iframe(embed_url, height=STREET_VIEW_HEIGHT, scrolling=False)

    with col2:
        st.subheader("Street View - Statický snímek")
        params = {
            "size": "800x600",
            "location": f"{lat},{lon}",
            "key": api_key,
            "heading": heading,
            "pitch": 10,
            "fov": 150,
        }
        response = requests.get(
            "https://maps.googleapis.com/maps/api/streetview", params=params
        )
        if response.status_code == 200:
            b64 = base64.b64encode(response.content).decode()
            st.markdown(
                f"""
                <img src="data:image/jpeg;base64,{b64}"
                     style="width:100%; height:{STREET_VIEW_HEIGHT}px;
                            object-fit:cover; border-radius:4px;">
                """,
                unsafe_allow_html=True,
            )
        else:
            st.write("Statický obrázek se nepodařilo načíst.")
