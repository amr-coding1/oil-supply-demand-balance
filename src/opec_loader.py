"""
OPEC Monthly Oil Market Report (MOMR) data loader.
Handles both manual CSV templates and MOMR Excel appendix files.
"""

import pandas as pd
from pathlib import Path


class OPECLoader:
    def load_production_csv(self, filepath: str) -> pd.DataFrame:
        """Load OPEC crude production by country from CSV template."""
        df = pd.read_csv(filepath, parse_dates=["month"])
        df = df.set_index("month").sort_index()
        # Convert all numeric columns
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def load_ngls_csv(self, filepath: str) -> pd.DataFrame:
        """Load OPEC NGLs + condensate from CSV template."""
        df = pd.read_csv(filepath, parse_dates=["month"])
        df = df.set_index("month").sort_index()
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def load_from_momr_excel(self, filepath: str) -> dict:
        """
        Parse OPEC MOMR Excel appendix tables.
        Returns dict with 'production' and 'ngls' DataFrames.
        """
        if not Path(filepath).exists():
            raise FileNotFoundError(f"MOMR Excel file not found: {filepath}")

        xl = pd.ExcelFile(filepath, engine="openpyxl")
        result = {}

        # Try to find production table (Table 5.13 or similar)
        for sheet in xl.sheet_names:
            if "5.13" in sheet or "secondary" in sheet.lower():
                df = pd.read_excel(filepath, sheet_name=sheet, engine="openpyxl")
                result["production"] = self._clean_production_table(df)
                break

        # Try to find NGLs table
        for sheet in xl.sheet_names:
            if "4.9" in sheet or "ngl" in sheet.lower():
                df = pd.read_excel(filepath, sheet_name=sheet, engine="openpyxl")
                result["ngls"] = df
                break

        return result

    def _clean_production_table(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean raw MOMR production table into a usable format."""
        # MOMR tables vary in format; this handles common patterns
        # Typically: countries as rows, months as columns
        df = df.dropna(how="all")
        return df

    def has_data(self, filepath: str) -> bool:
        """Check if a CSV template has actual data (not just headers)."""
        try:
            df = pd.read_csv(filepath)
            return not df.dropna(how="all", subset=[c for c in df.columns if c != "month"]).empty
        except (FileNotFoundError, pd.errors.EmptyDataError):
            return False
