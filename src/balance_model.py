"""
Core Oil Supply/Demand Balance Model.
Assembles supply and demand from multiple sources, calculates the balance,
and provides inventory cross-checking and term structure validation.
"""

import pandas as pd
import numpy as np


class OilBalanceModel:
    def __init__(self):
        self.supply = None
        self.demand = None
        self.balance = None
        self.last_actual_month = None

    def build_supply_table(self, steo_data: pd.DataFrame, opec_data=None, iea_data=None):
        """
        Assemble supply table. Priority cascade:
        1. IEA OMR (if available) — most authoritative for non-OPEC
        2. OPEC MOMR (if available) — best for OPEC country detail
        3. EIA STEO — always available, serves as baseline

        All values in mb/d.
        """
        supply = pd.DataFrame(index=steo_data.index)

        # STEO baseline
        if "opec_crude" in steo_data.columns:
            supply["opec_crude"] = steo_data["opec_crude"]
        if "opec_ngls" in steo_data.columns:
            supply["opec_ngls"] = steo_data["opec_ngls"]
        if "non_opec_supply" in steo_data.columns:
            supply["non_opec_supply"] = steo_data["non_opec_supply"]
        if "total_world_supply" in steo_data.columns:
            supply["total_world_supply"] = steo_data["total_world_supply"]
        if "us_crude_production" in steo_data.columns:
            supply["us_crude_production"] = steo_data["us_crude_production"]

        # Override with OPEC MOMR data if available
        if opec_data is not None and not opec_data.empty:
            if "total_opec_crude" in opec_data.columns:
                common_idx = supply.index.intersection(opec_data.index)
                valid = opec_data.loc[common_idx, "total_opec_crude"].dropna()
                if not valid.empty:
                    supply.loc[valid.index, "opec_crude"] = valid

        # Override with IEA data if available
        if iea_data is not None and not iea_data.empty:
            common_idx = supply.index.intersection(iea_data.index)
            for steo_col, iea_col in [
                ("non_opec_supply", "non_opec_supply_mbd"),
                ("total_world_supply", "global_supply_mbd"),
            ]:
                if iea_col in iea_data.columns:
                    valid = iea_data.loc[common_idx, iea_col].dropna()
                    if not valid.empty:
                        supply.loc[valid.index, steo_col] = valid

        # Compute total if components are available but total is missing
        if "total_world_supply" not in supply.columns or supply["total_world_supply"].isna().all():
            components = ["opec_crude", "opec_ngls", "non_opec_supply"]
            if all(c in supply.columns for c in components):
                supply["total_world_supply"] = (
                    supply["opec_crude"] + supply["opec_ngls"] + supply["non_opec_supply"]
                )

        # YoY growth
        supply["supply_yoy_change"] = supply["total_world_supply"].diff(12)

        self.supply = supply
        return supply

    def build_demand_table(self, steo_data: pd.DataFrame, iea_data=None):
        """
        Assemble demand table from STEO baseline with IEA overrides.
        All values in mb/d.
        """
        demand = pd.DataFrame(index=steo_data.index)

        # STEO baseline
        if "global_demand" in steo_data.columns:
            demand["global_demand"] = steo_data["global_demand"]
        if "oecd_demand" in steo_data.columns:
            demand["oecd_demand"] = steo_data["oecd_demand"]
        if "non_oecd_demand" in steo_data.columns:
            demand["non_oecd_demand"] = steo_data["non_oecd_demand"]
        if "us_demand" in steo_data.columns:
            demand["us_demand"] = steo_data["us_demand"]
        if "china_demand" in steo_data.columns:
            demand["china_demand"] = steo_data["china_demand"]

        # Override with IEA data if available
        if iea_data is not None and not iea_data.empty:
            common_idx = demand.index.intersection(iea_data.index)
            for steo_col, iea_col in [
                ("global_demand", "global_demand_mbd"),
                ("oecd_demand", "total_oecd_mbd"),
                ("non_oecd_demand", "total_non_oecd_mbd"),
                ("china_demand", "china_mbd"),
            ]:
                if iea_col in iea_data.columns:
                    valid = iea_data.loc[common_idx, iea_col].dropna()
                    if not valid.empty:
                        demand.loc[valid.index, steo_col] = valid

        # YoY growth
        demand["demand_yoy_change"] = demand["global_demand"].diff(12)
        demand["demand_yoy_pct"] = (
            demand["global_demand"].pct_change(12) * 100
        )

        self.demand = demand
        return demand

    def calculate_balance(self) -> pd.DataFrame:
        """
        The centerpiece calculation:
        Balance = Total Supply - Total Demand = Implied Stock Change (mb/d)
        """
        if self.supply is None or self.demand is None:
            raise ValueError("Must build supply and demand tables first.")

        balance = pd.DataFrame(index=self.supply.index)

        # Core components
        balance["total_supply"] = self.supply["total_world_supply"]
        balance["total_demand"] = self.demand["global_demand"]

        # The balance (positive = build/surplus, negative = draw/deficit)
        balance["implied_stock_change"] = (
            balance["total_supply"] - balance["total_demand"]
        )

        # Convert mb/d to absolute million barrels per month
        days_in_month = balance.index.to_series().dt.days_in_month
        balance["implied_stock_change_mb"] = (
            balance["implied_stock_change"] * days_in_month
        )
        balance["cumulative_stock_change_mb"] = (
            balance["implied_stock_change_mb"].cumsum()
        )

        # Call on OPEC = Demand - Non-OPEC Supply - OPEC NGLs
        if "non_opec_supply" in self.supply.columns and "opec_ngls" in self.supply.columns:
            balance["call_on_opec"] = (
                balance["total_demand"]
                - self.supply["non_opec_supply"]
                - self.supply["opec_ngls"]
            )

        # Supply/demand growth
        if "supply_yoy_change" in self.supply.columns:
            balance["supply_yoy_change"] = self.supply["supply_yoy_change"]
        if "demand_yoy_change" in self.demand.columns:
            balance["demand_yoy_change"] = self.demand["demand_yoy_change"]
        if "demand_yoy_pct" in self.demand.columns:
            balance["demand_yoy_pct"] = self.demand["demand_yoy_pct"]

        # Market state classification
        balance["market_state"] = np.where(
            balance["implied_stock_change"] > 0.1, "Surplus",
            np.where(balance["implied_stock_change"] < -0.1, "Deficit", "Balanced")
        )

        self.balance = balance
        return balance

    def add_actual_inventory_comparison(self, us_stocks: pd.Series):
        """
        Compare implied stock change with actual US crude inventory movements.
        US represents ~25% of OECD visible storage.
        """
        if self.balance is None:
            raise ValueError("Must calculate balance first.")

        # Align index — STEO uses 1st-of-month, EIA stocks use end-of-month.
        # Normalize both to month period for matching.
        stocks_monthly = us_stocks.copy()
        stocks_monthly.index = stocks_monthly.index.to_period("M").to_timestamp()

        common_idx = self.balance.index.intersection(stocks_monthly.index)
        self.balance["us_crude_stocks_mmbbl"] = np.nan
        self.balance.loc[common_idx, "us_crude_stocks_mmbbl"] = stocks_monthly.loc[common_idx].values

        # Monthly stock change
        self.balance["us_stock_change_mmbbl"] = (
            self.balance["us_crude_stocks_mmbbl"].diff()
        )

        # Directional agreement: does implied and actual move the same way?
        implied_dir = np.sign(self.balance["implied_stock_change"])
        actual_dir = np.sign(self.balance["us_stock_change_mmbbl"])
        self.balance["directional_agreement"] = implied_dir == actual_dir

        return self.balance

    def flag_actuals_vs_forecasts(self, last_actual_month: str):
        """Mark rows as actuals or STEO forecasts."""
        self.last_actual_month = pd.to_datetime(last_actual_month)
        if self.balance is not None:
            self.balance["data_type"] = np.where(
                self.balance.index <= self.last_actual_month,
                "Actual", "Forecast"
            )
        if self.supply is not None:
            self.supply["data_type"] = np.where(
                self.supply.index <= self.last_actual_month,
                "Actual", "Forecast"
            )
        if self.demand is not None:
            self.demand["data_type"] = np.where(
                self.demand.index <= self.last_actual_month,
                "Actual", "Forecast"
            )

    def get_master_table(self) -> pd.DataFrame:
        """
        Produce the full master balance table for display.
        Combines key supply, demand, and balance columns.
        """
        cols = {}

        # Supply side
        if self.supply is not None:
            for col in ["opec_crude", "opec_ngls", "non_opec_supply",
                        "total_world_supply", "us_crude_production"]:
                if col in self.supply.columns:
                    cols[col] = self.supply[col]

        # Demand side
        if self.demand is not None:
            for col in ["oecd_demand", "non_oecd_demand", "global_demand",
                        "us_demand", "china_demand"]:
                if col in self.demand.columns:
                    cols[col] = self.demand[col]

        # Balance
        if self.balance is not None:
            for col in ["implied_stock_change", "implied_stock_change_mb",
                        "cumulative_stock_change_mb", "call_on_opec",
                        "us_crude_stocks_mmbbl", "us_stock_change_mmbbl",
                        "market_state", "data_type"]:
                if col in self.balance.columns:
                    cols[col] = self.balance[col]

        master = pd.DataFrame(cols)
        master.index.name = "month"

        # Rename for display
        display_names = {
            "opec_crude": "OPEC Crude",
            "opec_ngls": "OPEC NGLs",
            "non_opec_supply": "Non-OPEC Supply",
            "total_world_supply": "Total Supply",
            "us_crude_production": "US Crude Prod.",
            "oecd_demand": "OECD Demand",
            "non_oecd_demand": "Non-OECD Demand",
            "global_demand": "Total Demand",
            "us_demand": "US Demand",
            "china_demand": "China Demand",
            "implied_stock_change": "Balance (mb/d)",
            "implied_stock_change_mb": "Implied Stock Chg (mb)",
            "cumulative_stock_change_mb": "Cum. Stock Chg (mb)",
            "call_on_opec": "Call on OPEC",
            "us_crude_stocks_mmbbl": "US Crude Stocks (mmb)",
            "us_stock_change_mmbbl": "US Stock Chg (mmb)",
            "market_state": "Market State",
            "data_type": "Data Type",
        }
        master = master.rename(columns=display_names)

        return master

    def get_quarterly_summary(self) -> pd.DataFrame:
        """Aggregate balance to quarterly averages."""
        if self.balance is None:
            raise ValueError("Must calculate balance first.")

        quarterly = self.balance[
            ["total_supply", "total_demand", "implied_stock_change"]
        ].resample("QE").mean()
        quarterly.index = quarterly.index.to_period("Q")
        return quarterly

    def get_latest_month_data(self) -> dict:
        """Extract the latest month's data as a dict (for commentary generation)."""
        if self.balance is None or self.supply is None or self.demand is None:
            raise ValueError("Model not yet built.")

        # Use the last actual month if flagged, otherwise fall back to last available
        if self.last_actual_month is not None:
            latest_month = self.last_actual_month
        else:
            valid = self.supply["total_world_supply"].dropna()
            if valid.empty:
                raise ValueError("No supply data available.")
            latest_month = valid.index[-1]

        data = {
            "report_month": latest_month.strftime("%B %Y"),
            "total_supply": self.supply.loc[latest_month, "total_world_supply"],
            "total_demand": self.demand.loc[latest_month, "global_demand"],
            "stock_change": self.balance.loc[latest_month, "implied_stock_change"],
        }

        # OPEC crude
        if "opec_crude" in self.supply.columns:
            data["opec_crude"] = self.supply.loc[latest_month, "opec_crude"]
        if "non_opec_supply" in self.supply.columns:
            data["non_opec"] = self.supply.loc[latest_month, "non_opec_supply"]

        # MoM supply change (relative to the month before latest_month)
        idx = self.supply.index.get_loc(latest_month)
        if idx > 0:
            prev = self.supply["total_world_supply"].iloc[idx - 1]
            data["supply_mom_change"] = data["total_supply"] - prev

        # YoY demand
        if "demand_yoy_change" in self.demand.columns:
            data["demand_yoy_change"] = self.demand.loc[latest_month, "demand_yoy_change"]
        if "demand_yoy_pct" in self.demand.columns:
            data["demand_yoy_pct"] = self.demand.loc[latest_month, "demand_yoy_pct"]

        # US inventory
        if "us_stock_change_mmbbl" in self.balance.columns:
            val = self.balance.loc[latest_month, "us_stock_change_mmbbl"]
            data["us_stock_change"] = val if pd.notna(val) else None
        else:
            data["us_stock_change"] = None

        return data
