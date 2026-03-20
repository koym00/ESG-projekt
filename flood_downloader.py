"""
Automatický stahovač povodňových map (VÚV TGM) pro ESG Aplikaci
"""

import os
import requests
import zipfile
from pathlib import Path

# ==========================================
# ZDE DOPLŇ ODKAZY Z WEBU
# Běž na web VÚV, klikni pravým tlačítkem na tu černou ikonku 'ZIP' u dané mapy,
# dej 'Kopírovat odkaz' (Copy link address) a vlož ho sem místo textu v uvozovkách:
# ==========================================
MAPY_K_STAZENI = {
    "Q5": "https://heis.vuv.cz/data/webmap/datovesady/isvs/ZaplavUzemi/E_ISVS$ZAPL_UZ5.zip",
    "Q20": "https://heis.vuv.cz/data/webmap/datovesady/isvs/ZaplavUzemi/E_ISVS$ZAPL_UZ20.zip",
    "Q100": "https://heis.vuv.cz/data/webmap/datovesady/isvs/ZaplavUzemi/E_ISVS$ZAPL_UZ100.zippython"
}

TEMP_DIR = "temp"

# Tváříme se jako běžný prohlížeč, aby nás server VÚV nezablokoval
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def download_and_extract(name, url):
    if url.startswith("ZDE_VLOZ"):
        print(f"⚠️ Přeskočeno {name} - Musíš do kódu doplnit skutečný odkaz z webu!")
        return False
        
    print(f"⬇ Stahuji mapu {name} (tohle může chvíli trvat, má to stovky MB)...")
    try:
        # 1. Stáhneme ZIP soubor a uložíme ho dočasně na disk (šetříme RAM paměť)
        temp_zip_path = os.path.join(TEMP_DIR, f"temp_{name}.zip")
        response = requests.get(url, headers=HEADERS, stream=True)
        response.raise_for_status()
        
        with open(temp_zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
        print(f"📦 Rozbaluji {name} do složky {TEMP_DIR}...")
        
        # 2. Rozbalíme ZIP přímo do složky temp
        with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
            zip_ref.extractall(TEMP_DIR)
            
        # 3. Uklidíme po sobě (smažeme ten stažený ZIP, už máme rozbalené mapy)
        os.remove(temp_zip_path)
            
        print(f"✅ Mapa {name} úspěšně stažena a rozbalena!\n")
        return True
        
    except Exception as e:
        print(f"❌ Chyba při stahování {name}: {e}\n")
        return False

def main():
    # Ujistíme se, že existuje složka temp
    Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*60)
    print("🌊 AUTOMATICKÝ STAHOVAČ POVODŇOVÝCH MAP (ESG) 🌊")
    print("="*60 + "\n")
    
    for name, url in MAPY_K_STAZENI.items():
        download_and_extract(name, url)
        
    print("="*60)
    print("🎉 HOTOVO! Všechny mapy jsou bezpečně ve složce temp.")
    print("Můžeš spustit Streamlit aplikaci.")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()