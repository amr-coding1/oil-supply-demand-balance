"""
Professional styling for charts and tables.
Designed for interview-ready output.
"""

import matplotlib.pyplot as plt
import matplotlib as mpl

# Color palette following oil market convention
COLORS = {
    "supply": "#1f77b4",
    "demand": "#d62728",
    "build": "#2ca02c",
    "draw": "#d62728",
    "opec": "#ff7f0e",
    "non_opec": "#1f77b4",
    "ngls": "#9467bd",
    "us": "#17becf",
    "oecd": "#2c3e50",
    "non_oecd": "#e67e22",
    "china": "#c0392b",
    "india": "#27ae60",
    "forecast_bg": "#fff3cd",
    "grid": "#e0e0e0",
    "text": "#2c3e50",
    "surplus_fill": "#d5f5e3",
    "deficit_fill": "#fadbd8",
}

# OPEC country colors (distinct palette for stacked charts)
OPEC_COUNTRY_COLORS = {
    "saudi_arabia": "#1a5276",
    "iraq": "#c0392b",
    "iran": "#7d3c98",
    "uae": "#2e86c1",
    "kuwait": "#28b463",
    "nigeria": "#d4ac0d",
    "libya": "#e67e22",
    "algeria": "#16a085",
    "congo": "#839192",
    "gabon": "#5d6d7e",
    "eq_guinea": "#a04000",
    "venezuela": "#1abc9c",
}


def apply_professional_style():
    """Apply a clean, professional matplotlib style."""
    style_params = {
        "figure.figsize": (12, 6),
        "figure.dpi": 100,
        "figure.facecolor": "white",
        "font.size": 11,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.labelsize": 12,
        "axes.grid": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.facecolor": "white",
        "grid.alpha": 0.3,
        "grid.color": COLORS["grid"],
        "legend.fontsize": 10,
        "legend.framealpha": 0.9,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
    }
    # Try Helvetica Neue, fall back gracefully
    try:
        mpl.font_manager.findfont("Helvetica Neue", fallback_to_default=False)
        style_params["font.family"] = "Helvetica Neue"
    except Exception:
        style_params["font.family"] = "sans-serif"

    mpl.rcParams.update(style_params)


def style_balance_table(styler, last_actual_month: str = None):
    """
    Apply professional styling to a pandas Styler object for the balance table.
    Returns the styled object.
    """
    styler = styler.set_table_styles([
        {"selector": "caption", "props": [
            ("font-size", "16px"), ("font-weight", "bold"),
            ("text-align", "left"), ("padding-bottom", "10px"),
            ("color", COLORS["text"]),
        ]},
        {"selector": "th", "props": [
            ("background-color", COLORS["oecd"]),
            ("color", "white"), ("font-weight", "bold"),
            ("text-align", "center"), ("padding", "8px"),
            ("border-bottom", "2px solid #1a252f"),
        ]},
        {"selector": "td", "props": [
            ("text-align", "right"), ("padding", "6px 10px"),
            ("border-bottom", "1px solid #ecf0f1"),
        ]},
        {"selector": "tr:hover td", "props": [
            ("background-color", "#eaf2f8"),
        ]},
    ])

    return styler


def format_number(val, decimals=2):
    """Format a number for display in tables."""
    if isinstance(val, (int, float)):
        if abs(val) >= 1000:
            return f"{val:,.{decimals}f}"
        return f"{val:.{decimals}f}"
    return val
