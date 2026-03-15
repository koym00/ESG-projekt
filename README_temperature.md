# CHMI Temperature CSV Downloader and Individual Zipper

A Python automation script that scrapes, downloads, and individually zips temperature CSV files from the Czech Hydrometeorological Institute (CHMI) temperature database.

## Features

✓ **Link Scraping**: Fetches the CHMI temperature data index page and extracts all CSV file links  
✓ **Smart Filtering**: Automatically identifies and filters only temperature CSV files ending with `T.csv`  
✓ **Individual Zipping**: Each temperature CSV file is downloaded and immediately compressed into its own ZIP archive  
✓ **No Loose Files**: Original CSV files are automatically deleted after zipping - only ZIP files remain  
✓ **Reliable Downloads**: Downloads files with proper User-Agent headers and timeout handling  
✓ **Progress Tracking**: Displays progress messages for each download with ZIP file sizes  
✓ **Error Handling**: Comprehensive try-except blocks for network issues and file I/O errors  

## Requirements

- Python 3.7+
- `requests` library
- `beautifulsoup4` library

## Installation

1. **Install required packages** (if not already installed):
   ```bash
   pip install -r requirements.txt
   ```

2. **Place the script** in your desired location:
   ```
   c:\ESG projekt\chmi_temperature_downloader.py
   ```

## Usage

Simply run the script:

```bash
python chmi_temperature_downloader.py
```

## What the Script Does

### 1. **Directory Setup**
   - Creates `C:\temp\Data\Temperature` directory if it doesn't exist

### 2. **Web Scraping**
   - Fetches: `https://opendata.chmi.cz/meteorology/climate/historical_csv/data/monthly/temperature/`
   - Parses HTML to find all CSV download links ending with `T.csv`

### 3. **Individual Download & Zipping**
   - Downloads each temperature CSV file temporarily
   - Immediately compresses it into a separate ZIP file (e.g., `station123T.csv` → `station123T.zip`)
   - Deletes the original CSV file
   - Shows progress with ZIP file sizes

### 4. **Result**
   - Each temperature CSV file becomes its own ZIP archive
   - No loose CSV files remain in the directory

## Configuration Options

Edit the script to customize:

```python
# Change target directory
TEMP_DIR = r"C:\temp\Data\Temperature"

# Customize User-Agent header
HEADERS = {
    'User-Agent': 'Your custom user agent here'
}
```

## Output Example

```
============================================================
CHMI TEMPERATURE CSV DOWNLOADER AND INDIVIDUAL ZIPPER
============================================================

✓ Directory ensured: C:\temp\Data\Temperature
→ Fetching temperature index page: https://opendata.chmi.cz/meteorology/climate/historical_csv/data/monthly/temperature/
  Found: station001T.csv
  Found: station002T.csv
  Found: station003T.csv
✓ Total temperature CSV files found: 3

============================================================
DOWNLOADING AND INDIVIDUALLY ZIPPING 3 TEMPERATURE CSV FILES
============================================================

[1/3] ⬇ Downloading: station001T.csv... ✓ → station001T.zip (1250.45 KB)
[2/3] ⬇ Downloading: station002T.csv... ✓ → station002T.zip (980.12 KB)
[3/3] ⬇ Downloading: station003T.csv... ✓ → station003T.zip (1456.78 KB)

✓ Downloaded and zipped 3/3 temperature files successfully

============================================================
✓ TEMPERATURE DATA WORKFLOW COMPLETED SUCCESSFULLY
============================================================

All temperature files individually zipped in: C:\temp\Data\Temperature
```

## File Structure After Running

```
C:\temp\Data\Temperature\
├── station001T.zip     (contains station001T.csv)
├── station002T.zip     (contains station002T.csv)
├── station003T.zip     (contains station003T.csv)
└── ...
```

**No loose CSV files remain!**

## Error Handling

The script handles these scenarios gracefully:

| Error Type | Handling |
|-----------|----------|
| **Connection Timeout** | Skips file, continues with next |
| **Connection Error** | Skips file, continues with next |
| **File I/O Errors** | Logs error, continues with next |
| **ZIP Creation Issues** | Logs error, continues with next |
| **Directory Creation** | Attempts to create with mkdir -p equivalent |

## Troubleshooting

**Script doesn't download any files?**
- Check your internet connection
- Verify the CHMI website is accessible
- The website URL may have changed

**Permission denied errors?**
- Run as Administrator
- Ensure C:\temp\Data\Temperature is accessible

**ZIP files not created?**
- Verify downloads were successful (check C:\temp\Data\Temperature)
- Ensure sufficient disk space for the ZIP files

**Module not found errors?**
- Install required packages: `pip install requests beautifulsoup4`

## Notes

- The script uses a realistic User-Agent header to avoid being blocked by the server
- Network requests have timeouts (10s for index, 30s for file downloads)
- ZIP file sizes are displayed in KB for easy reading
- Each CSV is compressed individually with DEFLATE compression
- Original CSV files are automatically cleaned up after zipping
- Only files ending with `T.csv` are downloaded (temperature data)

## License

This script is provided as-is for educational and data collection purposes.