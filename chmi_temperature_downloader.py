"""
CHMI Temperature CSV Downloader and Individual Zipper

This script automates the following workflow:
1. Scrapes links from the CHMI daily temperature data index page
2. Filters for CSV files ending with 'T.csv'
3. Downloads them to temp/Data\Temperature with progress messages
4. Individually compresses each CSV into its own ZIP archive
5. Handles errors gracefully with try-except blocks
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import zipfile
from pathlib import Path
from typing import List

# Configuration
INDEX_URL = "https://opendata.chmi.cz/meteorology/climate/historical_csv/data/daily/temperature/"
TEMP_DIR = "C:\temp\Data\Temperature"

# User-Agent header to avoid being blocked
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


def ensure_temp_directory():
    """Ensure the temperature data directory exists."""
    try:
        Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)
        print(f"✓ Directory ensured: {TEMP_DIR}")
        return True
    except Exception as e:
        print(f"✗ Error creating directory {TEMP_DIR}: {e}")
        return False


def scrape_temperature_csv_links() -> List[str]:
    """
    Scrape the temperature index page and extract all CSV download links ending with 'T.csv'.

    Returns:
        List of absolute URLs for temperature CSV files
    """
    csv_links = []

    try:
        print(f"→ Fetching temperature index page: {INDEX_URL}")
        response = requests.get(INDEX_URL, headers=HEADERS, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all links (a tags)
        links = soup.find_all('a', href=True)

        for link in links:
            href = link['href']
            # Check if the link ends with T.csv (temperature files)
            if href.endswith('T.csv'):
                # Convert relative URLs to absolute URLs
                absolute_url = urljoin(INDEX_URL, href)
                csv_links.append(absolute_url)
                print(f"  Found: {os.path.basename(href)}")

        print(f"✓ Total temperature CSV files found: {len(csv_links)}\n")
        return csv_links

    except requests.exceptions.Timeout:
        print("✗ Error: Request timed out. The server took too long to respond.")
        return []
    except requests.exceptions.ConnectionError:
        print("✗ Error: Connection failed. Please check your internet connection.")
        return []
    except requests.exceptions.RequestException as e:
        print(f"✗ Error fetching temperature index page: {e}")
        return []
    except Exception as e:
        print(f"✗ Unexpected error while parsing temperature index page: {e}")
        return []


def download_temperature_csv_file(url: str) -> bool:
    """
    Download a single temperature CSV file to the temp directory and immediately zip it.

    Args:
        url: The absolute URL of the temperature CSV file

    Returns:
        True if successful, False otherwise
    """
    filename = os.path.basename(url)
    filepath = os.path.join(TEMP_DIR, filename)
    zip_filename = filename.replace('.csv', '.zip')
    zip_filepath = os.path.join(TEMP_DIR, zip_filename)

    try:
        print(f"⬇ Downloading: {filename}...", end=' ', flush=True)
        response = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        response.raise_for_status()

        # Download to temporary file
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Immediately create ZIP file for this CSV
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(filepath, arcname=filename)

        # Remove the original CSV file
        os.remove(filepath)

        zip_size_kb = os.path.getsize(zip_filepath) / 1024
        print(f"✓ → {zip_filename} ({zip_size_kb:.2f} KB)")
        return True

    except requests.exceptions.Timeout:
        print(f"✗ Timeout")
        return False
    except requests.exceptions.ConnectionError:
        print(f"✗ Connection error")
        return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
        return False
    except IOError as e:
        print(f"✗ File I/O error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def download_all_temperature_csvs(csv_links: List[str]) -> int:
    """
    Download all temperature CSV files from the provided list and individually ZIP each one.

    Args:
        csv_links: List of temperature CSV file URLs

    Returns:
        Number of successfully downloaded and zipped files
    """
    if not csv_links:
        print("No temperature CSV files to download.")
        return 0

    print(f"\n{'='*60}")
    print(f"DOWNLOADING AND INDIVIDUALLY ZIPPING {len(csv_links)} TEMPERATURE CSV FILES")
    print(f"{'='*60}\n")

    successful_downloads = 0

    for i, url in enumerate(csv_links, 1):
        print(f"[{i}/{len(csv_links)}] ", end='')
        if download_temperature_csv_file(url):
            successful_downloads += 1

    print(f"\n✓ Downloaded and zipped {successful_downloads}/{len(csv_links)} temperature files successfully\n")
    return successful_downloads


def main():
    """Main orchestration function."""
    print("\n" + "="*60)
    print("CHMI TEMPERATURE CSV DOWNLOADER AND INDIVIDUAL ZIPPER")
    print("="*60 + "\n")

    # Step 1: Ensure temperature data directory exists
    if not ensure_temp_directory():
        print("✗ Failed to set up temperature data directory. Exiting.")
        sys.exit(1)

    # Step 2: Scrape temperature CSV links from the index page
    csv_links = scrape_temperature_csv_links()

    if not csv_links:
        print("✗ No temperature CSV files found to download. Exiting.")
        sys.exit(1)

    # Step 3: Download all temperature CSV files and individually ZIP them
    downloaded_count = download_all_temperature_csvs(csv_links)

    if downloaded_count == 0:
        print("✗ No temperature files were downloaded. Exiting.")
        sys.exit(1)

    print("="*60)
    print("✓ TEMPERATURE DATA WORKFLOW COMPLETED SUCCESSFULLY")
    print("="*60)
    print(f"\nAll temperature files individually zipped in: {TEMP_DIR}\n")


if __name__ == "__main__":
    main()