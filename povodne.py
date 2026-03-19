import geopandas as gpd
from shapely.geometry import Point

def zkontroluj_povoden(lat, lon, cesta_k_mape):
    """
    Tato funkce vezme GPS souřadnice a mapu povodní a zjistí,
    jestli dům leží v záplavové oblasti.
    """
    print("Načítám povodňovou mapu (to může chvilku trvat)...")
    
    # 1. Načteme staženou mapu z DIBAVODu (ten .shp soubor)
    mapa_povodni = gpd.read_file(cesta_k_mape)
    
    # 2. Z tvé GPS (lat, lon) vytvoříme virtuální tečku (Bod).
    # Pozor: V mapách se vždy zadává nejdřív zeměpisná délka (lon=X) a pak šířka (lat=Y)
    bod = Point(lon, lat)
    
    # 3. Vytvoříme z tečky mini-mapu, aby se dala porovnat s velkou mapou
    # GPS souřadnice (lat, lon) používají systém "WGS84", jehož kód je EPSG:4326
    bod_gdf = gpd.GeoDataFrame([1], geometry=[bod], crs="EPSG:4326")
    
    # Státní mapy (DIBAVOD) často používají jiný systém (tzv. S-JTSK). 
    # Tento řádek automaticky převede naši tečku do stejného systému, jaký má státní mapa.
    bod_gdf = bod_gdf.to_crs(mapa_povodni.crs)
    
    # 4. Protnutí (Magie!): Zjistíme, jestli se naše tečka dotýká nějaké "kaluže" v mapě
    prunik = gpd.sjoin(bod_gdf, mapa_povodni, how="inner", predicate="intersects")
    
    # 5. Vyhodnocení
    if not prunik.empty:
        return True # Je to pod vodou!
    else:
        return False # Je to v suchu.

# ==========================================
# TADY SI TO OTESTUJEME:
# ==========================================
if __name__ == "__main__":
    # TADY doplň přesný název tvého souboru, který končí na .shp
    # Například: "data_povodne/Q100_zapl_uzemi.shp"
    cesta = "D03_ZaplUzemi100Vody.shp" 
    
    # Testovací GPS (zkus třeba souřadnice nějakého domu u řeky a nějakého na kopci)
    test_lat = 50.29402368840738 # Zeměpisná šířka
    test_lon = 14.488737950416374 # Zeměpisná délka
    
    print(f"Ověřuji souřadnice: {test_lat}, {test_lon}...")
    
    je_v_riziku = zkontroluj_povoden(test_lat, test_lon, cesta)
    
    if je_v_riziku:
        print("🔴 POZOR: Budova leží ve 100leté záplavové oblasti! Vysoké ESG riziko.")
    else:
        print("🟢 BEZPEČNO: Budova je mimo 100letou záplavovou oblast.")