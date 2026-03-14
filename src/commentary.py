"""
Templated market commentary generator.
Uses Jinja2 to produce editable markdown from balance model data.
"""

from jinja2 import Template
import pandas as pd
import numpy as np


BALANCE_COMMENTARY_TEMPLATE = """## Oil Market Balance Summary — {{ report_month }}

**Supply:** Global oil supply averaged **{{ "%.1f"|format(total_supply) }} mb/d** in {{ report_month }}, \
{{ "up" if supply_mom_change > 0 else "down" }} {{ "%.1f"|format(supply_mom_change|abs) }} mb/d month-over-month. \
{% if opec_crude is defined %}OPEC crude production stood at **{{ "%.1f"|format(opec_crude) }} mb/d**{% endif %}\
{% if non_opec is defined %}, while non-OPEC supply was **{{ "%.1f"|format(non_opec) }} mb/d**{% endif %}.

**Demand:** Global oil demand is estimated at **{{ "%.1f"|format(total_demand) }} mb/d**\
{% if demand_yoy_change is defined and demand_yoy_change is not none %}, \
{{ "up" if demand_yoy_change > 0 else "down" }} {{ "%.1f"|format(demand_yoy_change|abs) }} mb/d \
year-over-year ({{ "%.1f"|format(demand_yoy_pct) }}%){% endif %}.

**Balance:** The implied stock change is **{{ "%.2f"|format(stock_change) }} mb/d** \
(a {{ "build" if stock_change > 0 else "draw" }}), suggesting the market is \
**{{ "oversupplied" if stock_change > 0 else "undersupplied" }}** by approximately \
{{ "%.2f"|format(stock_change|abs) }} mb/d, or roughly {{ "%.0f"|format(stock_change|abs * 30) }} million barrels per month.

{% if us_stock_change is not none %}**Inventory Cross-Check:** US crude stocks \
{{ "rose" if us_stock_change > 0 else "fell" }} by \
{{ "%.1f"|format(us_stock_change|abs) }} million barrels in the month, \
{{ "consistent with" if (us_stock_change > 0) == (stock_change > 0) else "diverging from" }} \
the implied global balance.
{% endif %}

**Key Variables to Watch:**
- OPEC+ production compliance and upcoming meeting decisions
- China demand trajectory amid economic uncertainty
- Non-OPEC supply growth (US, Brazil, Guyana, Canada)
- Geopolitical risk premium and sanctions impacts
"""


class CommentaryGenerator:
    def __init__(self, template_str: str = None):
        self.template = Template(template_str or BALANCE_COMMENTARY_TEMPLATE)

    def generate(self, data: dict) -> str:
        """Generate commentary from a data dict."""
        # Set defaults for optional fields
        defaults = {
            "supply_mom_change": 0.0,
            "demand_yoy_change": None,
            "demand_yoy_pct": None,
            "us_stock_change": None,
        }
        for k, v in defaults.items():
            data.setdefault(k, v)

        return self.template.render(**data)

    def generate_for_latest_month(self, model) -> str:
        """Extract latest month data from balance model and generate commentary."""
        data = model.get_latest_month_data()
        return self.generate(data)
