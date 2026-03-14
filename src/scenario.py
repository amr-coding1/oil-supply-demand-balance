"""
Scenario analysis engine for the oil balance model.

Lets you adjust OPEC production, non-OPEC supply, and demand assumptions
for forecast months, then compare the resulting balances side by side.
Actuals are never modified.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from copy import deepcopy

from src.styling import COLORS


class Scenario:
    """A single named scenario with adjustment parameters."""

    def __init__(
        self,
        name: str,
        opec_crude_adj: float = 0.0,
        non_opec_adj: float = 0.0,
        demand_adj: float = 0.0,
        opec_crude_override: float = None,
        description: str = "",
    ):
        self.name = name
        self.opec_crude_adj = opec_crude_adj
        self.non_opec_adj = non_opec_adj
        self.demand_adj = demand_adj
        self.opec_crude_override = opec_crude_override
        self.description = description

    def __repr__(self):
        parts = [f'"{self.name}"']
        if self.opec_crude_override is not None:
            parts.append(f"opec={self.opec_crude_override:.1f}")
        elif self.opec_crude_adj:
            parts.append(f"opec_adj={self.opec_crude_adj:+.1f}")
        if self.non_opec_adj:
            parts.append(f"non_opec_adj={self.non_opec_adj:+.1f}")
        if self.demand_adj:
            parts.append(f"demand_adj={self.demand_adj:+.1f}")
        return f"Scenario({', '.join(parts)})"


class ScenarioEngine:
    """
    Run multiple scenarios against the base supply/demand data and compare results.

    Expects a DataFrame with columns: opec_crude, opec_ngls, non_opec_supply,
    total_world_supply, global_demand. Pass the model's processed data (which
    includes any OPEC/IEA overrides), not the raw STEO parse.

    Usage:
        engine = ScenarioEngine(model_data, last_actual_month="2026-02")
        engine.add_scenario("OPEC Holds Cuts", opec_crude_adj=+4.0)
        engine.add_scenario("China Slowdown", demand_adj=-0.3)
        results = engine.run_all()
        engine.summary_table()
        engine.plot_comparison()
    """

    def __init__(self, model_data: pd.DataFrame, last_actual_month: str):
        self.steo_data = model_data.copy()
        self.last_actual = pd.to_datetime(last_actual_month)
        self.forecast_mask = self.steo_data.index > self.last_actual
        self.scenarios = {}
        self.results = {}

        # Base case is always the STEO as-is
        self.scenarios["Base Case (EIA STEO)"] = Scenario(
            name="Base Case (EIA STEO)",
            description="EIA STEO forecast, no adjustments.",
        )

    def add_scenario(
        self,
        name: str,
        opec_crude_adj: float = 0.0,
        non_opec_adj: float = 0.0,
        demand_adj: float = 0.0,
        opec_crude_override: float = None,
        description: str = "",
    ):
        """Register a scenario. Adjustments are in mb/d, applied to forecast months only."""
        self.scenarios[name] = Scenario(
            name=name,
            opec_crude_adj=opec_crude_adj,
            non_opec_adj=non_opec_adj,
            demand_adj=demand_adj,
            opec_crude_override=opec_crude_override,
            description=description,
        )

    def _apply_scenario(self, scenario: Scenario) -> pd.DataFrame:
        """Apply scenario adjustments to a copy of the base data. Only forecast months change."""
        data = self.steo_data.copy()
        mask = self.forecast_mask

        # OPEC crude
        if scenario.opec_crude_override is not None:
            data.loc[mask, "opec_crude"] = scenario.opec_crude_override
        elif scenario.opec_crude_adj != 0:
            data.loc[mask, "opec_crude"] += scenario.opec_crude_adj

        # Non-OPEC supply
        if scenario.non_opec_adj != 0:
            data.loc[mask, "non_opec_supply"] += scenario.non_opec_adj

        # Recalculate total supply from components
        data.loc[mask, "total_world_supply"] = (
            data.loc[mask, "opec_crude"]
            + data.loc[mask, "opec_ngls"]
            + data.loc[mask, "non_opec_supply"]
        )

        # Demand adjustment
        if scenario.demand_adj != 0:
            data.loc[mask, "global_demand"] += scenario.demand_adj

        return data

    def _calc_balance(self, data: pd.DataFrame) -> pd.DataFrame:
        """Lightweight balance calculation (no model overhead)."""
        bal = pd.DataFrame(index=data.index)
        bal["total_supply"] = data["total_world_supply"]
        bal["total_demand"] = data["global_demand"]
        bal["opec_crude"] = data["opec_crude"]
        bal["non_opec_supply"] = data["non_opec_supply"]
        bal["balance"] = bal["total_supply"] - bal["total_demand"]

        days = bal.index.to_series().dt.days_in_month
        bal["balance_mb"] = bal["balance"] * days
        bal["cumulative_mb"] = bal["balance_mb"].cumsum()

        # Call on OPEC
        bal["call_on_opec"] = (
            bal["total_demand"] - data["non_opec_supply"] - data["opec_ngls"]
        )

        bal["market_state"] = np.where(
            bal["balance"] > 0.1, "Surplus",
            np.where(bal["balance"] < -0.1, "Deficit", "Balanced"),
        )

        return bal

    def run_all(self) -> dict:
        """Run all registered scenarios and store results."""
        self.results = {}
        for name, scenario in self.scenarios.items():
            adjusted = self._apply_scenario(scenario)
            balance = self._calc_balance(adjusted)
            self.results[name] = {
                "scenario": scenario,
                "data": adjusted,
                "balance": balance,
            }
        return self.results

    def summary_table(self) -> pd.DataFrame:
        """
        Quarterly comparison table across all scenarios.
        Shows average balance (mb/d) for each quarter under each scenario.
        """
        if not self.results:
            self.run_all()

        quarterly = {}
        for name, res in self.results.items():
            bal = res["balance"]["balance"]
            q = bal.resample("QE").mean()
            q.index = q.index.to_period("Q").astype(str)
            quarterly[name] = q

        table = pd.DataFrame(quarterly).T
        table.columns.name = "Quarter"
        table.index.name = "Scenario"

        # Only show forecast quarters (and last actual quarter for context)
        last_actual_q = self.last_actual.to_period("Q").start_time
        forecast_qs = [c for c in table.columns
                       if pd.Period(c).start_time >= last_actual_q]
        if forecast_qs:
            table = table[forecast_qs]

        return table.round(2)

    def detail_table(self) -> pd.DataFrame:
        """
        Monthly comparison: balance under each scenario for forecast months.
        """
        if not self.results:
            self.run_all()

        monthly = {}
        for name, res in self.results.items():
            monthly[name] = res["balance"]["balance"]

        table = pd.DataFrame(monthly)
        table.index = table.index.strftime("%Y-%m")
        table.index.name = "Month"

        # Show from last actual month onward for context
        last_str = self.last_actual.strftime("%Y-%m")
        if last_str in table.index:
            table = table.loc[last_str:]

        return table.round(2)

    def plot_comparison(self, save_path: str = None) -> plt.Figure:
        """
        Overlay chart: balance path under each scenario.
        Base case is solid bold, alternatives are dashed.
        """
        if not self.results:
            self.run_all()

        fig, ax = plt.subplots(figsize=(14, 6))

        scenario_colors = [
            "#2c3e50",  # base: dark navy
            "#e74c3c",  # red
            "#3498db",  # blue
            "#27ae60",  # green
            "#f39c12",  # orange
            "#9b59b6",  # purple
        ]

        for i, (name, res) in enumerate(self.results.items()):
            bal = res["balance"]["balance"]
            is_base = (i == 0)
            color = scenario_colors[i % len(scenario_colors)]

            ax.plot(
                bal.index, bal.values,
                color=color,
                linewidth=2.5 if is_base else 1.8,
                linestyle="-" if is_base else "--",
                label=name,
                alpha=1.0 if is_base else 0.85,
            )

        ax.axhline(y=0, color="black", linewidth=0.8, alpha=0.5)

        # Shade forecast region
        ax.axvspan(
            mdates.date2num(self.last_actual),
            ax.get_xlim()[1],
            alpha=0.06, color="#ffc107", zorder=0,
        )
        ax.axvline(
            self.last_actual, color="#ffc107",
            linestyle="--", linewidth=1, alpha=0.6,
        )

        ax.set_title("Scenario Analysis: Global Oil Balance")
        ax.set_ylabel("Balance (mb/d) — positive = surplus, negative = deficit")
        ax.legend(loc="best", fontsize=9, framealpha=0.9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))

        fig.tight_layout()

        if save_path:
            from pathlib import Path
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="white")

        return fig

    def plot_opec_comparison(self, save_path: str = None) -> plt.Figure:
        """
        Compare OPEC production vs Call on OPEC across scenarios.
        Shows how much OPEC is over/under-producing relative to market needs.
        """
        if not self.results:
            self.run_all()

        fig, ax = plt.subplots(figsize=(14, 6))

        scenario_colors = [
            "#2c3e50", "#e74c3c", "#3498db", "#27ae60", "#f39c12", "#9b59b6",
        ]

        # Plot call on OPEC for each scenario (dashed)
        for i, (name, res) in enumerate(self.results.items()):
            bal = res["balance"]
            color = scenario_colors[i % len(scenario_colors)]
            is_base = (i == 0)

            ax.plot(
                bal.index, bal["call_on_opec"],
                color=color,
                linewidth=2 if is_base else 1.5,
                linestyle="-" if is_base else "--",
                label=f"{name} — Call",
                alpha=0.7,
            )

            ax.plot(
                bal.index, bal["opec_crude"],
                color=color,
                linewidth=2 if is_base else 1.5,
                linestyle="-" if is_base else ":",
                label=f"{name} — Actual",
                alpha=1.0,
            )

        ax.axvline(
            self.last_actual, color="#ffc107",
            linestyle="--", linewidth=1, alpha=0.6,
        )

        ax.set_title("OPEC Production vs Call on OPEC — Scenario Comparison")
        ax.set_ylabel("mb/d")
        ax.legend(loc="best", fontsize=8, framealpha=0.9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))

        fig.tight_layout()

        if save_path:
            from pathlib import Path
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="white")

        return fig

    def print_summary(self):
        """Print a readable summary of all scenarios."""
        if not self.results:
            self.run_all()

        forecast_months = self.steo_data.index[self.forecast_mask]
        if forecast_months.empty:
            print("No forecast months to analyze.")
            return

        print(f"{'Scenario':<30s} {'Avg Balance':>12s} {'H2 2026 Avg':>12s} {'Market':>10s}")
        print("-" * 70)

        for name, res in self.results.items():
            bal = res["balance"]["balance"]
            forecast_bal = bal[self.forecast_mask]
            avg = forecast_bal.mean()

            # H2 2026 average
            h2_mask = (bal.index >= "2026-07") & (bal.index <= "2026-12")
            h2_avg = bal[h2_mask].mean() if h2_mask.any() else np.nan

            state = "Surplus" if avg > 0.1 else ("Deficit" if avg < -0.1 else "Balanced")

            print(f"{name:<30s} {avg:>+10.2f}  {h2_avg:>+10.2f}  {state:>10s}")
