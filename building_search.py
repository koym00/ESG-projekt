"""
Module for searching buildings by ID and extracting their data from RUIAN.
Uses IDENTICAL extraction logic as register.py - DO NOT CHANGE extraction method.
"""

import requests
from bs4 import BeautifulSoup
import re
import pyproj


def get_building_full_data_by_id(building_id: int) -> dict:
    """
    Fetches building information from RUIAN using EXACT SAME extraction as register.py.
    Returns all data: coordinates, hierarchical info, technical attributes, and geometry.
    
    This function mirrors register.py's extraction logic exactly:
    - Identical HTML table scraping
    - Identical regex pattern for coordinate extraction  
    - Identical coordinate transformation with -abs() handling
    - Identical categorization of attributes
    
    Args:
        building_id: The building ID (stavební objekt ID)
        
    Returns:
        dict with full building data or error message
    """
    target_url = f"https://vdp.cuzk.gov.cz/vdp/ruian/stavebniobjekty/{building_id}"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(target_url, headers=headers, timeout=10)
        response.encoding = 'utf-8'

        if response.status_code != 200:
            return {
                "status": "error",
                "message": f"Objekt s ID {building_id} v RÚIAN nenalezen (status {response.status_code})"
            }

        soup = BeautifulSoup(response.text, 'html.parser')
        data = {}

        # IDENTICAL to register.py: Extract all attributes from tables
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['th', 'td'])
                for i in range(0, len(cells) - 1, 2):
                    k = cells[i].get_text(strip=True).replace(":", "")
                    v = cells[i+1].get_text(" ", strip=True)
                    if k:
                        data[k] = v

        # IDENTICAL to register.py: Extract coordinates and convert
        y_jtsk = x_jtsk = lat = lon = None
        coord_element = soup.find(string=re.compile(r'Y:.*X:'))
        
        if coord_element:
            match = re.search(r"Y:\s*([0-9.,\s]+)\s*X:\s*([0-9.,\s]+)", coord_element)
            if match:
                y_raw = match.group(1).replace(" ", "").replace(",", ".")
                x_raw = match.group(2).replace(" ", "").replace(",", ".")
                
                # IDENTICAL to register.py handling
                y_jtsk = -abs(float(y_raw))
                x_jtsk = -abs(float(x_raw))

                # IDENTICAL transformace
                transformer = pyproj.Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)
                lon, lat = transformer.transform(y_jtsk, x_jtsk)

        # IDENTICAL to register.py: Structure data into categories
        nadrazene_prvky = {
            "Stát": data.get("Stát"),
            "Region soudřnosti": data.get("Region soudřnosti"),
            "Kraj (VÚSC)": data.get("Kraj (VÚSC)"),
            "ORP": data.get("ORP"),
            "Obec": data.get("Obec"),
            "Městská část/obvod": data.get("Městská část/obvod"),
            "Část obce": data.get("Část obce"),
            "Katastrální území": data.get("Katastrální území"),
            "Parcela": data.get("Parcela")
        }
        
        technicko_ekonomicke_atributy = {
            "Datum dokončení": data.get("Datum dokončení"),
            "Druh svislé nosné konstrukce": data.get("Druh svislé nosné konstrukce"),
            "Počet bytů": data.get("Počet bytů"),
            "Počet podlaží": data.get("Počet podlaží"),
            "Připojení na vodovod": data.get("Připojení na vodovod"),
            "Zastavěná plocha [m2]": data.get("Zastavěná plocha [m2]"),
            "Podlahová plocha [m2]": data.get("Podlahová plocha [m2]"),
            "Obestavěný prostor [m3]": data.get("Obestavěný prostor [m3]"),
            "Způsob vytápění": data.get("Způsob vytápění"),
            "Připojení na rozvod plynu": data.get("Připojení na rozvod plynu"),
            "Vybavení výtahem": data.get("Vybavení výtahem"),
            "Připojení na kanalizační síť": data.get("Připojení na kanalizační síť"),
            "Počet vchodů": data.get("Počet vchodů")
        }

        geometrie = {
            "y_jtsk": y_jtsk,
            "x_jtsk": x_jtsk,
            "lat": lat,
            "lon": lon
        }

        return {
            "status": "ok",
            "building_id": building_id,
            "nadrazene_prvky": nadrazene_prvky,
            "technicko_ekonomicke_atributy": technicko_ekonomicke_atributy,
            "geometrie": geometrie,
            "odkaz": target_url,
            "raw_data": data
        }
        
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Chyba při komunikaci s RÚIAN: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Neznámá chyba: {str(e)}"
        }


def get_building_coordinates_by_id(building_id: int) -> dict:
    """
    Quick method - returns coordinates and GPS for ESG analysis.
    Uses the same extraction logic as get_building_full_data_by_id.
    """
    result = get_building_full_data_by_id(building_id)
    
    if result['status'] == 'ok':
        return {
            "status": "ok",
            "building_id": building_id,
            "lat": result['geometrie']['lat'],
            "lon": result['geometrie']['lon'],
            "y_jtsk": result['geometrie']['y_jtsk'],
            "x_jtsk": result['geometrie']['x_jtsk'],
            "address": result['nadrazene_prvky'].get("Obec", "Unknown"),
            "full_data": result
        }
    else:
        return result
