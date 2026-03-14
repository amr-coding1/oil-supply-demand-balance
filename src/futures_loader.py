"""
Brent futures curve data loader.
Uses yfinance for free front-month Brent data, CSV template for full curve.
"""

import pandas as pd
from pathlib import Path

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False


class FuturesLoader:
    def load_csv(self, filepath: str) -> pd.DataFrame:
        """Load Brent futures curve data from CSV template."""
        df = pd.read_csv(filepath, parse_dates=["date"])
        df = df.set_index("date").sort_index()
        for col in df.columns:
            if col != "curve_shape":
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def fetch_brent_front_month(self, start: str = "2023-01-01") -> pd.DataFrame:
        """Fetch Brent front-month prices from Yahoo Finance."""
        if not HAS_YFINANCE:
            print("yfinance not installed. Use CSV template for futures data.")
            return pd.DataFrame()

        bz = yf.Ticker("BZ=F")
        hist = bz.history(start=start, interval="1mo")
        if hist.empty:
            return pd.DataFrame()

        monthly = hist[["Close"]].rename(columns={"Close": "m1_brent"})
        monthly.index.name = "month"
        monthly.index = monthly.index.to_period("M").to_timestamp()
        return monthly

    def has_data(self, filepath: str) -> bool:
        """Check if CSV template has data."""
        try:
            df = pd.read_csv(filepath)
            return not df.dropna(how="all", subset=[c for c in df.columns if c not in ("date", "curve_shape")]).empty
        except (FileNotFoundError, pd.errors.EmptyDataError):
            return False
