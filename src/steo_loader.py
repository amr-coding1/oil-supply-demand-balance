"""
EIA Short-Term Energy Outlook (STEO) Excel workbook parser.
Downloads and parses STEO_m.xlsx which contains the complete
global oil supply/demand balance with 18-month forecasts.

Workbook structure (as of March 2026):
- Multiple sheets: 3atab (world balance), 3btab (non-OPEC detail),
  3ctab (world production), 3dtab (crude production), 3etab (consumption),
  4atab (US detail)
- Row 2: year headers (sparse, every 12 columns starting at col 2)
- Row 3: month names (Jan-Dec repeating)
- Row 4+: section headers and data rows
- Col 0: series ID (lowercase), Col 1: label, Cols 2+: monthly data
"""

import requests
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta


STEO_URL = "https://www.eia.gov/outlooks/steo/xls/STEO_m.xlsx"

MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# Series we need, organized by sheet.
# Keys are lowercase as they appear in the workbook.
# We extract from 3atab (world summary) and 3etab (consumption detail).
SERIES_MAP = {
    # sheet -> {series_id -> output_column_name}
    "3atab": {
        "papr_world":          "total_world_supply",     # row 5 or 9
        "copr_opec":           "opec_crude",             # row 11
        "opec_nc":             "opec_ngls",              # row 12
        "papr_nonopec":        "non_opec_supply",        # row 13
        "patc_world":          "global_demand",          # row 18
        "patc_oecd":           "oecd_demand",            # row 19
        "patc_non_oecd":       "non_oecd_demand",        # row 26
        "patc_us":             "us_demand",              # row 23
        "patc_ch":             "china_demand",           # row 27
    },
    "3btab": {
        "papr_us":             "us_total_liquids",       # US total liquid fuels
    },
    "3dtab": {
        "coprpus":             "us_crude_production",    # US crude production
    },
}


class STEOLoader:
    def __init__(self, cache_dir: str = None, max_cache_age_days: int = 7):
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.max_cache_age_days = max_cache_age_days
        self.metadata = None  # populated after parse() or extract_metadata()

    def download(self, save_path: str = None, force: bool = False) -> str:
        """Download the STEO Excel workbook. Skips if cached file is fresh."""
        if save_path is None and self.cache_dir:
            save_path = str(self.cache_dir / "STEO_m.xlsx")
        elif save_path is None:
            save_path = "STEO_m.xlsx"

        # Skip download if cache is fresh (unless forced)
        path = Path(save_path)
        if not force and path.exists():
            age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
            if age < timedelta(days=self.max_cache_age_days):
                print(f"Using cached STEO workbook ({age.days}d old, max {self.max_cache_age_days}d)")
                return save_path

        resp = requests.get(STEO_URL)
        resp.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(resp.content)
        print(f"Downloaded fresh STEO workbook to {save_path}")
        return save_path

    def extract_metadata(self, filepath: str) -> dict:
        """
        Read the 'Dates' sheet to get publication metadata.
        Returns dict with last_historical_month, forecast_month, modeling_date.
        """
        raw = pd.read_excel(filepath, sheet_name="Dates", header=None, engine="openpyxl")

        meta = {}

        # D1: Forecast month name (e.g. "March 2026")
        meta["forecast_month"] = str(raw.iloc[0, 3]) if pd.notna(raw.iloc[0, 3]) else None

        # D2: Modeling completion date
        val = raw.iloc[1, 3]
        if pd.notna(val):
            meta["modeling_date"] = pd.to_datetime(val)
        else:
            meta["modeling_date"] = None

        # D7: Last Historical Month as YYYYMM integer (e.g. 202602)
        val = raw.iloc[6, 3]
        if pd.notna(val):
            yyyymm = int(val)
            year = yyyymm // 100
            month = yyyymm % 100
            meta["last_historical_month"] = pd.Timestamp(year=year, month=month, day=1)
            meta["last_historical_month_str"] = f"{year}-{month:02d}"
        else:
            meta["last_historical_month"] = None
            meta["last_historical_month_str"] = None

        self.metadata = meta
        return meta

    def _build_date_index(self, raw: pd.DataFrame) -> list:
        """
        Build a date index from row 2 (years, sparse) and row 3 (month names).
        Years appear at columns 2, 14, 26, ... (every 12 columns).
        Month names (Jan-Dec) repeat in row 3 starting at col 2.
        """
        ncols = raw.shape[1]
        dates = []

        # Extract years from row 2, forward-fill
        current_year = None
        for col_idx in range(2, ncols):
            year_val = raw.iloc[2, col_idx]
            if pd.notna(year_val):
                try:
                    current_year = int(year_val)
                except (ValueError, TypeError):
                    pass

            month_name = raw.iloc[3, col_idx]
            if current_year and pd.notna(month_name) and str(month_name).strip() in MONTH_MAP:
                month_num = MONTH_MAP[str(month_name).strip()]
                dates.append((col_idx, pd.Timestamp(year=current_year, month=month_num, day=1)))
            else:
                dates.append((col_idx, None))

        return dates

    def _extract_series_from_sheet(
        self, filepath: str, sheet_name: str, series_ids: dict
    ) -> pd.DataFrame:
        """
        Extract specific series from a STEO sheet.
        Returns DataFrame with dates as index and series as columns.
        """
        raw = pd.read_excel(filepath, sheet_name=sheet_name, header=None, engine="openpyxl")

        # Build date index
        date_pairs = self._build_date_index(raw)
        valid_dates = [(col, dt) for col, dt in date_pairs if dt is not None]

        if not valid_dates:
            return pd.DataFrame()

        data_cols = [col for col, _ in valid_dates]
        date_index = pd.DatetimeIndex([dt for _, dt in valid_dates])

        # Find matching series — handle duplicates by taking the FIRST occurrence
        # that appears in a "data" section (after row 4)
        result = {}
        target_ids = {sid.lower(): col_name for sid, col_name in series_ids.items()}

        # Track which IDs we still need and in which context
        # Some IDs appear twice (e.g., papr_world appears in both Production and
        # a derived section). We want specific ones based on context.
        found_ids = set()

        for row_idx in range(4, len(raw)):
            cell_val = raw.iloc[row_idx, 0]
            if pd.notna(cell_val) and isinstance(cell_val, str):
                sid = cell_val.strip().lower()
                if sid in target_ids and sid not in found_ids:
                    col_name = target_ids[sid]
                    row_data = raw.iloc[row_idx, data_cols].values
                    result[col_name] = pd.to_numeric(
                        pd.Series(row_data, index=date_index), errors="coerce"
                    )
                    found_ids.add(sid)

        if not result:
            return pd.DataFrame()

        df = pd.DataFrame(result, index=date_index)
        df.index.name = "month"
        return df

    def parse(self, filepath: str, start: str = "2023-01", end: str = "2026-12") -> pd.DataFrame:
        """
        Parse the STEO workbook, extracting all required series from multiple sheets.
        Also extracts metadata (last_historical_month etc.) from the Dates sheet.
        """
        # Extract metadata first
        try:
            self.extract_metadata(filepath)
        except Exception as e:
            print(f"Warning: could not read STEO metadata: {e}")

        all_data = []

        for sheet_name, series_ids in SERIES_MAP.items():
            try:
                df = self._extract_series_from_sheet(filepath, sheet_name, series_ids)
                if not df.empty:
                    all_data.append(df)
            except Exception as e:
                print(f"Warning: could not parse sheet {sheet_name}: {e}")

        if not all_data:
            raise ValueError("No data extracted from any STEO sheet.")

        # Merge all sheets (they share the same date index)
        result = pd.concat(all_data, axis=1)
        result = result.sort_index()

        # Remove any duplicate columns (keep first)
        result = result.loc[:, ~result.columns.duplicated()]

        # Filter date range
        start_dt = pd.to_datetime(start)
        end_dt = pd.to_datetime(end)
        mask = (result.index >= start_dt) & (result.index <= end_dt)
        result = result.loc[mask]

        return result

    def download_and_parse(
        self, save_path: str = None, start: str = "2023-01", end: str = "2026-12"
    ) -> pd.DataFrame:
        """Download the STEO workbook and parse it in one step."""
        path = self.download(save_path)
        return self.parse(path, start=start, end=end)
