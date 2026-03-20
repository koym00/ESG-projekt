# CHMI Metadata CSV Downloader and Individual Zipper

A Python automation script that scrapes, downloads, and individually zips CSV files from the Czech Hydrometeorological Institute (CHMI) meteorology database.

## Features

✓ **Link Scraping**: Fetches the CHMI index page and extracts all CSV file links using BeautifulSoup  
✓ **Smart Filtering**: Automatically identifies and filters only `.csv` files  
✓ **Individual Zipping**: Each CSV file is downloaded and immediately compressed into its own ZIP archive  
✓ **No Loose Files**: Original CSV files are automatically deleted after zipping - only ZIP files remain  
✓ **Reliable Downloads**: Downloads files with proper User-Agent headers and timeout handling  
✓ **Progress Tracking**: Displays progress messages for each download with ZIP file sizes  
✓ **Error Handling**: Comprehensive try-except blocks for network issues and file I/O errors  

## Requirements

- Python 3.7+
- `requests` library
- `beautifulsoup4` library

## Installation

1. **Install required packages**:
   ```bash
   pip install requests beautifulsoup4
   ```

2. **Place the script** in your desired location:
   ```
   c:\ESG projekt\chmi_downloader.py
   ```

## Usage

Simply run the script:

```bash
python chmi_downloader.py
```

## What the Script Does

### 1. **Directory Setup**
   - Creates `temp` directory if it doesn't exist

### 2. **Web Scraping**
   - Fetches: `https://opendata.chmi.cz/meteorology/climate/historical_csv/metadata/`
   - Parses HTML to find all CSV download links

### 3. **Individual Download & Zipping**
   - Downloads each CSV file temporarily
   - Immediately compresses it into a separate ZIP file (e.g., `meta1.csv` → `meta1.zip`)
   - Deletes the original CSV file
   - Shows progress with ZIP file sizes

### 4. **Result**
   - Each CSV file becomes its own ZIP archive
   - No loose CSV files remain in the directory

## Configuration Options

Edit the script to customize:

```python
# Change target directory
TEMP_DIR = r"temp"

# Customize User-Agent header
HEADERS = {
    'User-Agent': 'Your custom user agent here'
}
```

## Error Handling

The script handles these scenarios gracefully:

| Error Type | Handling |
|-----------|----------|
| **Connection Timeout** | Skips file, continues with next |
| **Connection Error** | Skips file, continues with next |
| **File I/O Errors** | Logs error, continues with next |
| **ZIP Creation Issues** | Reports error and exits cleanly |
| **Directory Creation** | Attempts to create with mkdir -p equivalent |

## Output Example

```
============================================================
CHMI METADATA CSV DOWNLOADER AND INDIVIDUAL ZIPPER
============================================================

✓ Directory ensured: temp
→ Fetching index page: https://opendata.chmi.cz/meteorology/climate/historical_csv/metadata/
  Found: meta1.csv
  Found: meta2.csv
  Found: meta3.csv
  Found: meta4.csv
✓ Total CSV files found: 4

============================================================
DOWNLOADING AND INDIVIDUALLY ZIPPING 4 CSV FILES
============================================================

[1/4] ⬇ Downloading: meta1.csv... ✓ → meta1.zip (530.12 KB)
[2/4] ⬇ Downloading: meta2.csv... ✓ → meta2.zip (7454.65 KB)
[3/4] ⬇ Downloading: meta3.csv... ✓ → meta3.zip (1.14 KB)
[4/4] ⬇ Downloading: meta4.csv... ✓ → meta4.zip (0.23 KB)

✓ Downloaded and zipped 4/4 files successfully

============================================================
✓ WORKFLOW COMPLETED SUCCESSFULLY
============================================================

All files individually zipped in: temp
```

## File Structure After Running

```
temp/
├── meta1.zip     (contains meta1.csv)
├── meta2.zip     (contains meta2.csv)
├── meta3.zip     (contains meta3.csv)
└── meta4.zip     (contains meta4.csv)
```

**No loose CSV files remain!**
DOWNLOADING 3 CSV FILES
============================================================

[1/3] ⬇ Downloading: file1.csv... ✓ (1234.56 KB)
[2/3] ⬇ Downloading: file2.csv... ✓ (2345.67 KB)
[3/3] ⬇ Downloading: file3.csv... ✓ (3456.78 KB)

✓ Downloaded 3/3 files successfully

============================================================
CREATING ZIP ARCHIVE
============================================================

→ Zipping 3 CSV files...
  ✓ Added: file1.csv
  ✓ Added: file2.csv
  ✓ Added: file3.csv

✓ Archive created successfully: chmi_metadata_archive.zip (6.50 MB)

→ Keeping original CSV files (CLEANUP_AFTER_ZIP = False)
  Tip: Set CLEANUP_AFTER_ZIP = True to delete originals after zipping.

============================================================
✓ WORKFLOW COMPLETED SUCCESSFULLY
============================================================

Archive location: temp/chmi_metadata_archive.zip
```

## Cleanup Options Explained

### Option 1: Keep Original CSVs (Default - CLEANUP_AFTER_ZIP = False)
- ✓ Easier to verify files before cleanup
- ✓ Can re-use original files for other purposes
- ⚠ Uses more disk space

### Option 2: Delete Original CSVs (CLEANUP_AFTER_ZIP = True)
- ✓ Saves disk space
- ✓ Cleaner directory
- ⚠ Remove originals immediately after zipping

## Troubleshooting

**Script doesn't download any files?**
- Check your internet connection
- Verify the CHMI website is accessible
- The website URL may have changed

**Permission denied errors?**
- Run as Administrator
- Ensure temp is accessible

**ZIP files not created?**
- Verify downloads were successful (check temp)
- Ensure sufficient disk space for the ZIP files

**Module not found errors?**
- Install required packages: `pip install requests beautifulsoup4`

## Notes

- The script uses a realistic User-Agent header to avoid being blocked by the server
- Network requests have timeouts (10s for index, 30s for file downloads)
- ZIP file sizes are displayed in KB for easy reading
- Each CSV is compressed individually with DEFLATE compression
- Original CSV files are automatically cleaned up after zipping

## License

This script is provided as-is for educational and data collection purposes.
