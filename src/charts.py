"""
Professional chart functions for the oil balance model.
All charts use matplotlib for publication-quality static output.
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from pathlib import Path

from src.styling import COLORS, OPEC_COUNTRY_COLORS


def _save_or_show(fig, save_path):
    """Save chart to file if path provided, otherwise just return."""
    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="white")
    return fig


def _add_forecast_shading(ax, last_actual_month, label="Forecast"):
    """Add shaded background for forecast region."""
    if last_actual_month is not None:
        xlim = ax.get_xlim()
        ax.axvspan(
            mdates.date2num(last_actual_month),
            xlim[1],
            alpha=0.08, color="#ffc107", zorder=0,
        )
        ax.axvline(
            last_actual_month, color="#ffc107",
            linestyle="--", linewidth=1, alpha=0.7, label=label,
        )


def plot_supply_vs_demand(
    balance_df: pd.DataFrame,
    last_actual_month=None,
    save_path: str = None,
) -> plt.Figure:
    """
    Two-line time series: Total Supply vs Total Demand.
    Shaded area between them (green = surplus, red = deficit).
    """
    fig, ax = plt.subplots(figsize=(14, 6))

    supply = balance_df["total_supply"]
    demand = balance_df["total_demand"]
    dates = balance_df.index

    ax.plot(dates, supply, color=COLORS["supply"], linewidth=2, label="Total Supply")
    ax.plot(dates, demand, color=COLORS["demand"], linewidth=2, label="Total Demand")

    # Fill between: green where supply > demand, red where demand > supply
    ax.fill_between(
        dates, supply, demand,
        where=(supply >= demand),
        color=COLORS["surplus_fill"], alpha=0.5, interpolate=True, label="Surplus",
    )
    ax.fill_between(
        dates, supply, demand,
        where=(supply < demand),
        color=COLORS["deficit_fill"], alpha=0.5, interpolate=True, label="Deficit",
    )

    _add_forecast_shading(ax, last_actual_month)

    ax.set_title("Global Oil Supply vs Demand")
    ax.set_ylabel("Million Barrels per Day (mb/d)")
    ax.legend(loc="upper left", framealpha=0.9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))

    fig.tight_layout()
    return _save_or_show(fig, save_path)


def plot_balance_bar(
    balance_df: pd.DataFrame,
    last_actual_month=None,
    save_path: str = None,
) -> plt.Figure:
    """
    Monthly bar chart of implied stock change.
    Green bars = builds, red bars = draws.
    """
    fig, ax = plt.subplots(figsize=(14, 5))

    values = balance_df["implied_stock_change"]
    dates = balance_df.index
    colors = [COLORS["build"] if v >= 0 else COLORS["draw"] for v in values]

    bar_width = 20  # days
    ax.bar(dates, values, width=bar_width, color=colors, alpha=0.8, edgecolor="none")
    ax.axhline(y=0, color="black", linewidth=0.8)

    _add_forecast_shading(ax, last_actual_month)

    ax.set_title("Global Oil Balance — Implied Stock Change")
    ax.set_ylabel("mb/d (positive = build, negative = draw)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))

    fig.tight_layout()
    return _save_or_show(fig, save_path)


def plot_implied_vs_actual_inventory(
    balance_df: pd.DataFrame,
    last_actual_month=None,
    save_path: str = None,
) -> plt.Figure:
    """
    Dual-axis chart comparing cumulative implied stock change
    with actual US crude oil inventories.
    """
    fig, ax1 = plt.subplots(figsize=(14, 6))

    dates = balance_df.index

    # Left axis: cumulative implied stock change
    if "cumulative_stock_change_mb" in balance_df.columns:
        ax1.plot(
            dates, balance_df["cumulative_stock_change_mb"],
            color=COLORS["supply"], linewidth=2, label="Cum. Implied Stock Change (mb)",
        )
    ax1.set_ylabel("Cumulative Implied Stock Change (million bbl)", color=COLORS["supply"])
    ax1.tick_params(axis="y", labelcolor=COLORS["supply"])

    # Right axis: actual US crude stocks
    if "us_crude_stocks_mmbbl" in balance_df.columns:
        ax2 = ax1.twinx()
        us_stocks = balance_df["us_crude_stocks_mmbbl"].dropna()
        ax2.plot(
            us_stocks.index, us_stocks.values,
            color=COLORS["demand"], linewidth=2, linestyle="--",
            label="US Crude Stocks (mmb)",
        )
        ax2.set_ylabel("US Crude Stocks (million bbl)", color=COLORS["demand"])
        ax2.tick_params(axis="y", labelcolor=COLORS["demand"])
        ax2.legend(loc="upper right")

    _add_forecast_shading(ax1, last_actual_month)

    ax1.set_title("Implied vs Actual Inventory Changes")
    ax1.legend(loc="upper left")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))

    fig.tight_layout()
    return _save_or_show(fig, save_path)


def plot_opec_production_stacked(
    opec_df: pd.DataFrame,
    save_path: str = None,
) -> plt.Figure:
    """
    Stacked bar chart of OPEC crude production by country.
    """
    fig, ax = plt.subplots(figsize=(14, 7))

    # Exclude non-country columns
    country_cols = [c for c in opec_df.columns if c not in ("total_opec_crude", "data_type")]
    data = opec_df[country_cols].dropna(how="all")

    if data.empty:
        ax.text(0.5, 0.5, "No OPEC country-level data available",
                ha="center", va="center", transform=ax.transAxes, fontsize=14)
        return _save_or_show(fig, save_path)

    # Sort countries by average production (largest at bottom)
    col_order = data.mean().sort_values(ascending=False).index.tolist()
    data = data[col_order]

    # Assign colors
    colors = [OPEC_COUNTRY_COLORS.get(col, "#95a5a6") for col in col_order]

    data.plot.bar(stacked=True, ax=ax, color=colors, width=0.8, edgecolor="none")

    ax.set_title("OPEC Crude Oil Production by Country")
    ax.set_ylabel("mb/d")
    ax.legend(
        loc="upper left", bbox_to_anchor=(1.01, 1),
        title="Country", fontsize=9,
    )

    # Format x-axis dates
    tick_labels = [d.strftime("%b %Y") for d in data.index]
    ax.set_xticklabels(tick_labels, rotation=45, ha="right", fontsize=8)

    fig.tight_layout()
    return _save_or_show(fig, save_path)


def plot_supply_breakdown(
    supply_df: pd.DataFrame,
    last_actual_month=None,
    save_path: str = None,
) -> plt.Figure:
    """
    Stacked area chart: OPEC Crude + OPEC NGLs + Non-OPEC Supply.
    """
    fig, ax = plt.subplots(figsize=(14, 6))

    dates = supply_df.index
    components = []
    labels = []
    colors_list = []

    for col, label, color in [
        ("opec_crude", "OPEC Crude", COLORS["opec"]),
        ("opec_ngls", "OPEC NGLs", COLORS["ngls"]),
        ("non_opec_supply", "Non-OPEC Supply", COLORS["non_opec"]),
    ]:
        if col in supply_df.columns:
            components.append(supply_df[col].values)
            labels.append(label)
            colors_list.append(color)

    if components:
        ax.stackplot(dates, *components, labels=labels, colors=colors_list, alpha=0.8)

    _add_forecast_shading(ax, last_actual_month)

    ax.set_title("Global Oil Supply Breakdown")
    ax.set_ylabel("mb/d")
    ax.legend(loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))

    fig.tight_layout()
    return _save_or_show(fig, save_path)


def plot_demand_by_region(
    demand_df: pd.DataFrame,
    last_actual_month=None,
    save_path: str = None,
) -> plt.Figure:
    """
    Stacked area chart: OECD vs Non-OECD demand.
    """
    fig, ax = plt.subplots(figsize=(14, 6))

    dates = demand_df.index
    components = []
    labels = []
    colors_list = []

    for col, label, color in [
        ("oecd_demand", "OECD Demand", COLORS["oecd"]),
        ("non_oecd_demand", "Non-OECD Demand", COLORS["non_oecd"]),
    ]:
        if col in demand_df.columns:
            components.append(demand_df[col].values)
            labels.append(label)
            colors_list.append(color)

    if components:
        ax.stackplot(dates, *components, labels=labels, colors=colors_list, alpha=0.8)

    _add_forecast_shading(ax, last_actual_month)

    ax.set_title("Global Oil Demand by Region")
    ax.set_ylabel("mb/d")
    ax.legend(loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))

    fig.tight_layout()
    return _save_or_show(fig, save_path)


def plot_call_on_opec(
    balance_df: pd.DataFrame,
    supply_df: pd.DataFrame,
    last_actual_month=None,
    save_path: str = None,
) -> plt.Figure:
    """
    Call on OPEC vs actual OPEC production.
    Shows whether OPEC is over- or under-producing relative to market needs.
    """
    fig, ax = plt.subplots(figsize=(14, 6))

    dates = balance_df.index

    if "call_on_opec" in balance_df.columns:
        ax.plot(
            dates, balance_df["call_on_opec"],
            color=COLORS["demand"], linewidth=2, label="Call on OPEC",
        )

    if "opec_crude" in supply_df.columns:
        ax.plot(
            dates, supply_df["opec_crude"],
            color=COLORS["opec"], linewidth=2, label="OPEC Actual Production",
        )

    _add_forecast_shading(ax, last_actual_month)

    ax.set_title("Call on OPEC vs Actual OPEC Production")
    ax.set_ylabel("mb/d")
    ax.legend(loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))

    fig.tight_layout()
    return _save_or_show(fig, save_path)
