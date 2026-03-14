"""
IEA Oil Market Report (OMR) data loader.
Loads manually-entered data from CSV templates.
IEA OMR is paywalled, so this relies on user transcription.
"""

import pandas as pd


class IEALoader:
    def load_supply_csv(self, filepath: str) -> pd.DataFrame:
        """Load IEA supply data from CSV template."""
        df = pd.read_csv(filepath, parse_dates=["month"])
        df = df.set_index("month").sort_index()
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def load_demand_csv(self, filepath: str) -> pd.DataFrame:
        """Load IEA demand data from CSV template."""
        df = pd.read_csv(filepath, parse_dates=["month"])
        df = df.set_index("month").sort_index()
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def has_data(self, df: pd.DataFrame) -> bool:
        """Check if a loaded template has actual data."""
        numeric_cols = df.select_dtypes(include="number").columns
        return not df[numeric_cols].dropna(how="all").empty
