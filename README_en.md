# CN University Geocoder

[中文](README.md) | **English**

A Python tool to batch geocode Chinese universities using Tencent Maps API, merging Ministry of Education data and supplementary details, and exporting structured results for further use.

## Features

- Reads university lists from Excel and merges with detailed JSON data
- Queries Tencent Maps API for campus geocoding (with QPS handling and retries)
- Cleans and deduplicates campus names
- Outputs results to JSON and CSV reports (including error and missing data reports)
- Logs all operations for traceability

## Requirements

- Python 3.8+
- See `requirements.txt` for dependencies

## Setup

1. **Clone this repository:**

   ```bash
   git clone <repo-url>
   cd cn-university-geocoder
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

4. **Prepare a `.env` file in the project root with your Tencent Maps API credentials:**

   ```env
   TENCENT_MAP_KEY="your_key"
   TENCENT_MAP_SK="your_secret_key"
   ```

## Usage

Run the main script:

```bash
python main.py
```

- The script will log output to a timestamped log file (e.g., `run_log_YYYYMMDD_HHMMSS.log`).
- Results will be saved as:
  - `universities.json`: Universities with campus geocodes
  - `universities_with_no_campuses.csv`: Universities with no campus found
  - `rejected_pois.csv`: POIs rejected by the name rules
  - `universities_without_details.csv`: Universities missing details in the supplementary JSON

## File Structure

- `main.py` — Main script for data processing and geocoding
- `requirements.txt` — Python dependencies
- `univ_moe.xls` — Input Excel file
- `univ_supp.json` — Supplementary university details

## Notes

- The script is designed for Chinese university data and Tencent Maps API.
- For best results, ensure your input files are up to date and your API quota is sufficient.

## License

[Mozilla Public License 2.0](LICENSE)
