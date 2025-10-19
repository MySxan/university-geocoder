# Global University Geocoder

[中文](README.md) | **English**

This project is a variant of [cn-university-geocoder](https://github.com/Naptie/cn-university-geocoder),
extended for global universities with Google Places API (New) support.  
A Python tool for batch querying and collecting geographic information of global universities. It supports Chinese universities (based on Tencent Maps API) and global universities (based on Google Places API), integrating multiple university ranking data, and exporting structured results for further use.

## Features

### Chinese University Processing (main.py)

- Reads university lists from Excel and merges with detailed JSON data
- Queries Tencent Maps API for campus geocoding (with QPS handling and retries)
- Cleans and deduplicates campus names
- Outputs results to JSON and CSV reports (including error and missing data reports)

### Global University Processing (main_global.py)

- Reads global university lists and ranking information from CSV (QS, THE, USNews/LAC)
- Queries Google Places API (New) for global university geocoding and detailed information
- Autocomplete (get placeId) → Place Details (get detailed info)
- Merges ranking information instead of discarding when multiple universities map to the same location
- Supports resuming after interruption to avoid duplicate queries
- Local caching to avoid duplicate API calls to save quota
- Outputs results to JSON and CSV reports (including query failures and missing website data reports)
- Complete process logging for traceability

## Requirements

- Python 3.8+
- See `requirements.txt` for dependencies

## Setup

1. **Clone this repository:**

   ```bash
   git clone <repo-url>
   cd university-geocoder
   ```

2. **Create and activate a virtual environment (recommended):**

   - On Windows:

     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```

   - On macOS/Linux:

     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Prepare a `.env` file in the project root with your API credentials:**

   ```env
   # For Chinese university processing (main.py)
   TENCENT_MAP_KEY="your_tencent_key"
   TENCENT_MAP_SK="your_tencent_secret_key"

   # For global university processing (main_global.py)
   GOOGLE_MAPS_KEY="your_google_maps_key"
   ```

## Usage

### Chinese University Data Processing

Run the main script to process Chinese universities:

```bash
python main.py
```

- The script will log output to a timestamped log file (e.g., `run_log_YYYYMMDD_HHMMSS.log`)
- Results will be saved as:
  - `universities.json`: Universities with campus geocodes
  - `universities_with_no_campuses.csv`: Universities with no campus found
  - `rejected_pois.csv`: POIs rejected by the name rules
  - `universities_without_details.csv`: Universities missing details in the supplementary JSON

### Global University Data Processing

Run the global university processing script:

```bash
python main_global.py
```

- The script will log output to a timestamped log file (e.g., `dedupe_log_YYYYMMDD_HHMMSS.log`)
- Results will be saved as:
  - `universities_global.json`: Global university data with geographic information and rankings
  - `rejected_pois_global.csv`: Universities where Google Places API query failed
  - `universities_with_no_website.csv`: Universities found but missing website information
  - `google_places_cache.json`: API response cache (for checkpoint resumption)
  - `processing_checkpoint.json`: Processing progress checkpoint

## File Structure

### Main Scripts

- `main.py` — Chinese university data processing (based on Tencent Maps API)
- `main_global.py` — Global university data processing (based on Google Places API)

### Input Data

- `univ_moe.xls` — Chinese Ministry of Education university list (for main.py)
- `univ_supp.json` — Supplementary university details (for main.py)
- `merged_rankings.csv` — Global university ranking data (for main_global.py)
  - Contains fields: Name, Country, QS_Rank, THE_Rank, USNews_Rank, Latitude, Longitude, etc.

### Output Data

#### main.py Output

- `universities.json` — Final university data (with campus geocodes)
- `universities_with_no_campuses.csv` — Universities with no campus found
- `rejected_pois.csv` — POIs rejected by name rules

#### main_global.py Output

- `universities_global.json` — Final global university data (with rankings and geographic information)
- `rejected_pois_global.csv` — Universities where API query failed
- `universities_with_no_website.csv` — Universities missing website information

### Working Files

- `requirements.txt` — Python dependencies
- `.env` — Environment variable configuration (to be created by user)
- `google_places_cache.json` — Google Places API response cache
- `processing_checkpoint.json` — Processing progress checkpoint
- `dedupe_log_*.log` — Detailed processing logs

## Notes

- **Chinese university processing (main.py)**: Designed for Chinese university data with Tencent Maps API
- **Global university processing (main_global.py)**: Supports global universities using Google Places API (New)
- Ensure input data files exist and are in correct format
- Sufficient API quota for best results
- First run may be slower (requires API calls); subsequent runs will be faster using local cache
- After interruption, next run will automatically resume from checkpoint, avoiding duplicate queries

## License

[Mozilla Public License 2.0](LICENSE)
