# Global Oil Supply/Demand Balance Model

A fundamental oil balance model that aggregates public data on global crude oil supply and demand, calculates whether the market is in surplus or deficit each month, and runs scenario analysis to test how different OPEC production and demand assumptions change that picture.

This is the same type of framework that analysts on physical commodity trading desks (Glencore, Vitol, Trafigura, Engelhart, etc.) maintain internally to inform positioning. The difference is they pay for Kpler, Vortexa, and proprietary field-level data. This one runs entirely on free, publicly available sources.

## Why this exists

Every barrel of oil produced either gets consumed or goes into storage. If supply exceeds demand, inventories build and the market is in surplus. If demand exceeds supply, inventories draw and the market is in deficit. That surplus or deficit is the single most important driver of oil prices and the shape of the futures curve (contango vs backwardation).

Trading desks track this monthly. They pull numbers from three agencies (EIA, OPEC, IEA), each of which publishes its own estimate of global supply and demand. The agencies disagree with each other, and none of them are exactly right. The analyst's job is to take those numbers, decide where they think the agencies are wrong, layer in their own assumptions, and figure out what the balance actually looks like going forward.

That's what this model does.

## What it actually calculates

```
Total Supply = OPEC Crude + OPEC NGLs + Non-OPEC Liquids
Total Demand = OECD + Non-OECD consumption

Balance = Total Supply - Total Demand = Implied Stock Change (mb/d)
```

- Positive balance = surplus. Inventories are building. Tends to push the Brent curve into contango (front month cheaper than deferred).
- Negative balance = deficit. Inventories are drawing. Tends to push the curve into backwardation (front month premium).

The model also calculates **Call on OPEC**, which is what OPEC would need to produce to keep the market balanced:

```
Call on OPEC = Total Demand - Non-OPEC Supply - OPEC NGLs
```

If OPEC is producing above the call, the market is oversupplied. Below the call, undersupplied. This is the number traders watch to gauge whether OPEC has room to increase production or needs to cut.

## Data sources

The EIA's Short-Term Energy Outlook (STEO) is the backbone of the model. It's a single Excel workbook published monthly that contains a complete global oil balance with 18 months of forecasts. It's free and publicly available. The model downloads it automatically.

| Source | What we pull | How it gets in |
|--------|-------------|----------------|
| **EIA STEO** | Full global S/D balance, OPEC/non-OPEC production, demand by region, implied stock change, 18-month forecast | Auto-downloaded, parsed from Excel |
| **EIA API v2** | US commercial crude oil inventories, weekly, excluding the SPR | Auto-fetched via API (free key required) |
| **OPEC MOMR** | Country-level OPEC crude production from secondary sources | Manual CSV entry from the Monthly Oil Market Report |
| **IEA OMR** | Non-OPEC supply revisions, demand estimates | Manual CSV entry (the IEA report is paywalled) |

The STEO provides everything needed to run the model out of the box. OPEC and IEA data are optional overrides, plugged in through CSV templates. When present, the model applies a priority cascade: IEA > OPEC > STEO. So if the IEA says non-OPEC supply is 0.3 mb/d higher than the EIA thinks, the model uses the IEA number.

## Scenario analysis

This is the core feature. The EIA publishes one view of the future. The scenario engine lets you test alternatives.

You define scenarios as adjustments (in mb/d) to the forecast period. Actual historical data is never touched. The engine recalculates the full balance under each scenario and produces a side-by-side comparison.

```python
engine = ScenarioEngine(steo_data, last_actual_month="2026-02")

engine.add_scenario("OPEC Holds Cuts", opec_crude_adj=+4.0)
engine.add_scenario("China Demand Weakness", demand_adj=-0.4)
engine.add_scenario("Bull Case", opec_crude_adj=+2.0, demand_adj=+0.3)
engine.add_scenario("Bear Case", opec_crude_adj=-0.5, demand_adj=-0.5, non_opec_adj=+0.3)

results = engine.run_all()
engine.summary_table()       # quarterly balance under each scenario
engine.plot_comparison()     # all scenarios overlaid on one chart
```

**Four adjustment levers:**

- `opec_crude_adj` (mb/d): shift OPEC crude production forecast up or down
- `non_opec_adj` (mb/d): shift non-OPEC supply forecast
- `demand_adj` (mb/d): shift global demand forecast
- `opec_crude_override` (mb/d): set OPEC crude to a specific level instead of adjusting

**Why this matters right now (March 2026):** The STEO forecasts OPEC crude dropping from 29.25 mb/d in February to 23.08 mb/d in March, a 6 mb/d collapse in a single month. That looks like the EIA modelling an aggressive OPEC+ production unwind. Most market participants expect something less dramatic. The "OPEC Holds Cuts" scenario tests what happens if OPEC stays closer to current levels, and it shifts the Q2 balance from deficit to a +4.7 mb/d surplus. That's a completely different trading environment.

The notebook ships with 5 predefined scenarios (base case + 4 alternatives). You can edit the numbers or add your own.

## How the model is structured

Everything runs through two Jupyter notebooks, backed by a modular Python codebase.

**Notebook 1: Data Ingestion** (`01_data_ingestion.ipynb`)
- Downloads the STEO workbook from the EIA website (cached locally, auto-refreshes after 7 days)
- Reads the workbook's `Dates` sheet to auto-detect the last month of actual data vs. forecast
- Fetches US crude inventories from the EIA API (weekly data, resampled to monthly)
- Checks whether OPEC/IEA data has been manually entered in the CSV templates
- Saves everything to `data/processed/`

**Notebook 2: Balance Model** (`02_oil_balance_model.ipynb`)
- Loads the processed data
- Builds the supply table (OPEC crude + NGLs + non-OPEC, with MOMR/OMR overrides if available)
- Builds the demand table (OECD + non-OECD, with regional breakdowns)
- Calculates the balance: supply minus demand = implied stock change
- Compares implied stock changes against actual US crude inventory movements
- Flags each row as "Actual" or "Forecast" based on the auto-detected cutoff
- Runs scenario analysis
- Generates 8 charts and a market commentary summary
- Exports the balance table as CSV and Excel

**The model is fully dynamic.** It reads the STEO publication date and last historical month directly from the workbook metadata. There are no hardcoded dates to update. When the EIA publishes a new STEO (around the 10th of each month), just re-run both notebooks and everything updates.

## Project structure

```
.
├── notebooks/
│   ├── 01_data_ingestion.ipynb        # data fetching and validation
│   └── 02_oil_balance_model.ipynb     # balance model, scenarios, charts
├── src/
│   ├── steo_loader.py                 # downloads and parses the STEO workbook
│   ├── eia_client.py                  # EIA API v2 client for inventory data
│   ├── opec_loader.py                 # loads OPEC country production from CSV
│   ├── iea_loader.py                  # loads IEA supply/demand from CSV
│   ├── futures_loader.py              # Brent futures curve (yfinance + CSV)
│   ├── balance_model.py               # core supply/demand/balance calculations
│   ├── scenario.py                    # scenario analysis engine
│   ├── charts.py                      # 8 matplotlib chart functions
│   ├── commentary.py                  # Jinja2 templated market commentary
│   └── styling.py                     # color palette and chart theme
├── config/
│   ├── settings.py                    # paths, API URLs, cache settings
│   └── series_ids.py                  # EIA series ID mappings, OPEC country list
├── data/
│   ├── raw/steo/                      # cached STEO workbook (gitignored)
│   ├── processed/                     # parsed CSVs and metadata (gitignored)
│   └── templates/                     # CSV templates for manual OPEC/IEA entry
├── output/
│   ├── charts/                        # exported PNG charts (gitignored)
│   └── tables/                        # balance table as CSV and Excel (gitignored)
├── .env                               # EIA API key (gitignored)
├── .gitignore
└── requirements.txt
```

## Charts

The model generates 8 charts. All of them shade the forecast region so you can see where actuals end and projections begin.

1. **Global Supply vs Demand** - two lines with green/red fill between them showing surplus or deficit
2. **Balance Bar Chart** - monthly implied stock change as bars (green = build, red = draw)
3. **Implied vs Actual Inventory** - cumulative model-implied stock changes plotted against actual US crude inventory levels
4. **OPEC Production by Country** - stacked bar chart of individual OPEC member production
5. **Supply Breakdown** - stacked area showing OPEC crude, OPEC NGLs, and non-OPEC
6. **Demand by Region** - stacked area showing OECD vs non-OECD demand
7. **Call on OPEC** - what the market needs from OPEC vs what OPEC is actually producing
8. **Scenario Comparison** - balance paths under each scenario overlaid on one chart

## Setup

```bash
pip install -r requirements.txt
```

Dependencies: pandas, numpy, matplotlib, openpyxl, requests, python-dotenv, Jinja2, yfinance, jupyter.

You need a free EIA API key. Register at https://www.eia.gov/opendata/register.php, then create a `.env` file in the project root:

```
EIA_API_KEY=your_key_here
```

Open the notebooks in VS Code or JupyterLab and run them in order. That's it.

## How to add OPEC/IEA data

The model runs fine on just the STEO and EIA API. But if you want to incorporate data from the OPEC Monthly Oil Market Report or the IEA Oil Market Report, fill in the CSV templates in `data/templates/`:

- `opec_production_template.csv` - OPEC crude production by country (from MOMR Table 5.13, secondary sources). Already pre-populated with STEO-derived estimates for 2023-2026.
- `iea_supply_template.csv` - IEA non-OPEC supply estimates
- `iea_demand_template.csv` - IEA demand estimates by region
- `opec_ngls_template.csv` - OPEC NGL/condensate production
- `brent_futures_template.csv` - Brent futures curve data (M1 through M12)

When these are filled in, the model automatically uses them as overrides over the STEO baseline.

## Technical details

- All volumes are in million barrels per day (mb/d) unless stated otherwise
- US inventory is in million barrels (stock level), converted from weekly to monthly average
- Time range: January 2023 to December 2026 (configurable in settings)
- The STEO's stock change series (`t3_stchange_world`) uses an opposite sign convention to ours. In the STEO, positive = inventory draws. In our model, positive = inventory builds. This is handled internally in the parser.
- OPEC country-level production from the STEO is only available for historical months. For forecast months, individual countries are blank but the aggregate OPEC total is still available from the EIA's capacity model.
- The auto-refresh checks the file modification time of the cached STEO workbook. If it's older than 7 days, the next run downloads a fresh copy. You can force a re-download with `steo.download(force=True)`.
