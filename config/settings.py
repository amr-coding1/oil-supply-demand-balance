import os
from dotenv import load_dotenv
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

load_dotenv(PROJECT_ROOT / ".env")

# EIA API
EIA_API_KEY = os.getenv("EIA_API_KEY", "")
EIA_BASE_URL = "https://api.eia.gov/v2"
STEO_EXCEL_URL = "https://www.eia.gov/outlooks/steo/xls/STEO_m.xlsx"

# Data paths
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
TEMPLATES_DIR = DATA_DIR / "templates"
OUTPUT_DIR = PROJECT_ROOT / "output"

# Model parameters
START_DATE = "2023-01"
END_DATE = "2026-12"
# LAST_ACTUAL_MONTH and REPORT_MONTH are now auto-detected from the STEO
# workbook's Dates sheet. See STEOLoader.extract_metadata().
STEO_CACHE_MAX_AGE_DAYS = 7  # Re-download STEO workbook after this many days
