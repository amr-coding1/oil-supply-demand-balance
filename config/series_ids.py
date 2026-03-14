"""
EIA STEO series IDs used in the oil balance model.
Full list: https://www.eia.gov/opendata/browser/steo

All values in million barrels per day (mb/d) unless noted.
"""

# === SUPPLY SERIES ===
SUPPLY_SERIES = {
    "COPR_OPEC":    "OPEC Crude Oil Production",
    "PAPR_OPEC":    "OPEC Total Petroleum and Other Liquids Production",
    "NGPL_OPEC":    "OPEC Non-Crude Liquids (NGLs + Condensate)",
    "PAPR_NONOPEC": "Non-OPEC Petroleum and Other Liquids Production",
    "PAPR_WORLD":   "World Total Petroleum and Other Liquids Production",
    "COPR_US":      "US Crude Oil Production",
    "PAPR_US":      "US Total Liquid Fuels Production",
}

# === DEMAND SERIES ===
DEMAND_SERIES = {
    "PATC_WORLD":    "World Petroleum and Other Liquids Consumption",
    "PATC_OECD":     "OECD Petroleum Consumption",
    "PATC_NON_OECD": "Non-OECD Petroleum Consumption",
    "PATC_US":       "US Petroleum Consumption",
    "PATC_CHINA":    "China Petroleum Consumption",
}

# === BALANCE / INVENTORY SERIES ===
BALANCE_SERIES = {
    "T3_STCHG_WORLD": "World Implied Stock Change and Balance",
}

# === ALL SERIES (for bulk fetch) ===
ALL_SERIES = {**SUPPLY_SERIES, **DEMAND_SERIES, **BALANCE_SERIES}

# === EIA API v2 Routes (for non-STEO data) ===
EIA_ROUTES = {
    "us_crude_production": {
        "route": "petroleum/crd/crpdn/data",
        "frequency": "monthly",
        "facets": {"duoarea": ["NUS"], "process": ["YPT"]},
    },
    "us_crude_stocks": {
        "route": "petroleum/stoc/wstk/data",
        "frequency": "weekly",
        "facets": {"product": ["EPC0"], "process": ["SAE"]},
    },
}

# OPEC member countries (for production-by-country tracking)
OPEC_COUNTRIES = [
    "Saudi Arabia", "Iraq", "Iran", "UAE", "Kuwait",
    "Nigeria", "Libya", "Algeria", "Congo", "Gabon",
    "Equatorial Guinea", "Venezuela",
]
