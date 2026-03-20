import requests
from pyproj import Transformer
from datetime import datetime
from functools import lru_cache

BASE_URL = "https://ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/MapServer"
ADDRESS_LAYER = f"{BASE_URL}/1/query"
BUILDING_LAYER = f"{BASE_URL}/3/query"
BUILDING_LAYER_METADATA = f"{BASE_URL}/3"

transformer = Transformer.from_crs("EPSG:4326", "EPSG:5514", always_xy=True)

# která pole chceme dekódovat přes domain.codedValues z metadata vrstvy 3
CODED_FIELDS = [
    "typstavebnihoobjektukod",
    "zpusobvyuzitikod",
    "druhkonstrukcekod",
    "pripojenivodovodkod",
    "pripojenikanalizacekod",
    "pripojeniplynkod",
    "zpusobvytapenikod",
    "vybavenivytahemkod",
]


def wgs84_to_sjtsk(lon: float, lat: float):
    x, y = transformer.transform(lon, lat)
    return x, y


@lru_cache(maxsize=1)
def load_building_field_domains() -> dict:
    """
    Načte metadata vrstvy StavebniObjekt a vrátí mapování:
    {
        "druhkonstrukcekod": {1: "...", 2: "..."},
        "pripojenivodovodkod": {1: "...", 2: "..."},
        ...
    }
    """
    response = requests.get(BUILDING_LAYER_METADATA, params={"f": "pjson"}, timeout=30)
    response.raise_for_status()
    metadata = response.json()

    domains = {}

    for field in metadata.get("fields", []):
        field_name = field.get("name")
        domain = field.get("domain")

        if field_name in CODED_FIELDS and domain and domain.get("type") == "codedValue":
            coded_values = domain.get("codedValues", [])
            domains[field_name] = {
                item["code"]: item["name"]
                for item in coded_values
                if "code" in item and "name" in item
            }

    return domains


def decode_field(field_name: str, value):
    if value is None:
        return None

    domains = load_building_field_domains()
    field_domain = domains.get(field_name)

    if not field_domain:
        return value

    return field_domain.get(value, f"Neznámý kód: {value}")


def format_date(value):
    if value is None:
        return None
    try:
        return datetime.utcfromtimestamp(value / 1000).strftime("%Y-%m-%d")
    except (OSError, ValueError, TypeError):
        return "N/A"


def query_nearest_address(lat: float, lon: float, distance: int = 20):
    x, y = wgs84_to_sjtsk(lon, lat)

    params = {
        "f": "json",
        "geometry": f"{x},{y}",
        "geometryType": "esriGeometryPoint",
        "inSR": "5514",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": distance,
        "units": "esriSRUnit_Meter",
        "outFields": "kod,adresa,stavebniobjekt,psc,cislodomovni",
        "returnGeometry": "false",
        "where": "1=1",
        "orderByFields": "objectid"
    }

    response = requests.get(ADDRESS_LAYER, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    features = data.get("features", [])
    if not features:
        return None

    return features[0]["attributes"]


def query_building_by_code(building_code: int):
    params = {
        "f": "json",
        "where": f"kod = {building_code}",
        "outFields": ",".join([
            "kod",
            "dokonceni",
            "druhkonstrukcekod",
            "pripojenivodovodkod",
            "pripojenikanalizacekod",
            "pripojeniplynkod",
            "zpusobvytapenikod",
            "vybavenivytahemkod",
            "pocetpodlazi",
            "pocetbytu",
            "podlahovaplocha",
            "zastavenaplocha",
            "obestavenyprostor",
            "typstavebnihoobjektukod",
            "zpusobvyuzitikod",
            "cisladomovni"
        ]),
        "returnGeometry": "false"
    }

    response = requests.get(BUILDING_LAYER, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    features = data.get("features", [])
    if not features:
        return None

    return features[0]["attributes"]


def get_building_info_from_point(lat: float, lon: float):
    address = query_nearest_address(lat, lon)

    if not address:
        return {
            "status": "not_found",
            "message": "Nepodařilo se najít adresní místo poblíž zadaných souřadnic."
        }

    building_code = address.get("stavebniobjekt")
    if not building_code:
        return {
            "status": "not_found",
            "message": "Adresní místo bylo nalezeno, ale nemá vazbu na stavební objekt.",
            "address": address
        }

    building = query_building_by_code(building_code)
    if not building:
        return {
            "status": "not_found",
            "message": "Stavební objekt se nepodařilo načíst.",
            "address": address,
            "building_code": building_code
        }

    return {
        "status": "ok",
        "address": address.get("adresa"),
        "building_code": building.get("kod"),
        "raw_address_data": address,
        "building_data": {
            "datum_dokonceni": format_date(building.get("dokonceni")),
            "druhkonstrukcekod": decode_field("druhkonstrukcekod", building.get("druhkonstrukcekod")),
            "pripojenivodovodkod": decode_field("pripojenivodovodkod", building.get("pripojenivodovodkod")),
            "pripojenikanalizacekod": decode_field("pripojenikanalizacekod", building.get("pripojenikanalizacekod")),
            "pripojeniplynkod": decode_field("pripojeniplynkod", building.get("pripojeniplynkod")),
            "zpusobvytapenikod": decode_field("zpusobvytapenikod", building.get("zpusobvytapenikod")),
            "vybavenivytahemkod": decode_field("vybavenivytahemkod", building.get("vybavenivytahemkod")),
            "typstavebnihoobjektukod": decode_field("typstavebnihoobjektukod", building.get("typstavebnihoobjektukod")),
            "zpusobvyuzitikod": decode_field("zpusobvyuzitikod", building.get("zpusobvyuzitikod")),
            "pocet_podlazi": building.get("pocetpodlazi"),
            "pocet_bytu": building.get("pocetbytu"),
            "podlahova_plocha_m2": building.get("podlahovaplocha"),
            "zastavena_plocha_m2": building.get("zastavenaplocha"),
            "obestaveny_prostor_m3": building.get("obestavenyprostor"),
            "cisla_domovni": building.get("cisladomovni"),
        },
        "raw_building_data": building
    }