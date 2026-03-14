"""
EIA API v2 client for fetching petroleum data and inventories.
API docs: https://www.eia.gov/opendata/documentation.php
"""

import requests
import pandas as pd
from pathlib import Path


class EIAClient:
    BASE_URL = "https://api.eia.gov/v2"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()

    def fetch_series(
        self,
        route: str,
        frequency: str = "monthly",
        facets: dict = None,
        data_col: str = "value",
        start: str = "2023-01",
        end: str = None,
        limit: int = 5000,
    ) -> pd.DataFrame:
        """Generic fetcher for any EIA API v2 route."""
        params = {
            "api_key": self.api_key,
            "frequency": frequency,
            "data[]": data_col,
            "start": start,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "length": limit,
        }
        if end:
            params["end"] = end
        if facets:
            for key, values in facets.items():
                for v in values:
                    params.setdefault(f"facets[{key}][]", [])
                    if isinstance(params[f"facets[{key}][]"], list):
                        params[f"facets[{key}][]"] = v
                    else:
                        params[f"facets[{key}][]"] = v

        url = f"{self.BASE_URL}/{route}/data"
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()["response"]["data"]
        return pd.DataFrame(data)

    def fetch_steo_series(
        self, series_id: str, start: str = "2023-01"
    ) -> pd.DataFrame:
        """Fetch a specific STEO series via the API."""
        params = {
            "api_key": self.api_key,
            "frequency": "monthly",
            "data[]": "value",
            "facets[seriesId][]": series_id,
            "start": start,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "length": 5000,
        }
        url = f"{self.BASE_URL}/steo/data"
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()["response"]["data"]
        df = pd.DataFrame(data)
        if not df.empty:
            df["period"] = pd.to_datetime(df["period"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.set_index("period").sort_index()
        return df

    def fetch_weekly_crude_stocks(self, start: str = "2023-01") -> pd.DataFrame:
        """US commercial crude oil stocks excluding SPR, weekly (national total)."""
        df = self.fetch_series(
            route="petroleum/stoc/wstk",
            frequency="weekly",
            facets={"product": ["EPC0"], "process": ["SAX"], "duoarea": ["NUS"]},
            start=start,
        )
        if not df.empty:
            df["period"] = pd.to_datetime(df["period"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.sort_values("period")
        return df

    def get_monthly_crude_stocks(self, start: str = "2023-01") -> pd.Series:
        """Fetch weekly crude stocks excl. SPR and resample to monthly average (million bbl)."""
        weekly = self.fetch_weekly_crude_stocks(start=start)
        if weekly.empty:
            return pd.Series(dtype=float, name="us_crude_stocks_mmbbl")
        # Convert from thousand barrels to million barrels
        weekly["value"] = weekly["value"] / 1000.0
        monthly = (
            weekly.set_index("period")["value"]
            .resample("ME")
            .mean()
        )
        monthly.name = "us_crude_stocks_mmbbl"
        monthly.index.name = "month"
        return monthly

    def download_steo_workbook(self, save_path: str) -> str:
        """Download the full STEO Excel workbook."""
        url = "https://www.eia.gov/outlooks/steo/xls/STEO_m.xlsx"
        resp = self.session.get(url)
        resp.raise_for_status()
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(resp.content)
        return save_path
