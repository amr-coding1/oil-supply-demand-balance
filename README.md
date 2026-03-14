# Global Oil Supply/Demand Balance Model

A Python model that takes the EIA's Short-Term Energy Outlook (the publicly available global oil balance), parses it into a usable format, and adds a scenario engine on top so you can test different OPEC production and demand assumptions against the EIA's baseline forecast.

The core data source is a single Excel workbook that the EIA publishes monthly. The model automates downloading and parsing it, fetches US crude inventory data from the EIA API for cross-checking, and lets you run "what if" scenarios on the forecast period. It's the conceptual starting point for the kind of supply/demand work done on physical commodity trading desks, built with free public data.

## Why this exists

Every barrel of oil produced either gets consumed or goes into storage. If supply exceeds demand, inventories build (surplus). If demand exceeds supply, inventories draw (deficit). That balance drives oil prices and the shape of the futures curve: surplus pushes toward contango, deficit toward backwardation.

Commodity analysts track this monthly. The three major agencies (EIA, OPEC, IEA) each publish their own estimate of global supply and demand, and they disagree with each other. The analyst's job is to take a baseline, decide where they think it's wrong, and layer in their own view to figure out what the balance actually looks like forward.

This model uses the EIA STEO as that baseline and the scenario engine as the place to layer in your own assumptions.

## What it calculates

```
Total Supply = OPEC Crude + OPEC NGLs + Non-OPEC Liquids
Total Demand = OECD + Non-OECD consumption

Balance = Total Supply - Total Demand = Implied Stock Change (mb/d)
```

Positive balance = surplus (builds). Negative = deficit (draws).

It also calculates **Call on OPEC**, which is what OPEC would need to produce to keep the market balanced:

```
Call on OPEC = Total Demand - Non-OPEC Supply - OPEC NGLs
```

If OPEC is producing above the call, the market is oversupplied. Below the call, undersupplied.

## Data sources

This is primarily a single-source model. The EIA STEO does the heavy lifting. It's a complete global oil balance with 18 months of forecasts in one Excel workbook, published monthly for free.

| Source | What it provides | How it gets in |
|--------|-----------------|----------------|
| **EIA STEO** | Full global S/D balance, OPEC/non-OPEC production, demand by region, 18-month forecast | Auto-downloaded, parsed from Excel |
| **EIA API v2** | US commercial crude oil inventories, weekly, excluding the SPR | Auto-fetched via API (free key) |

The model also has CSV templates for entering OPEC MOMR and IEA OMR data as overrides (IEA > OPEC > STEO priority), but in practice the IEA templates are empty (it's a paywalled report) and the OPEC template is pre-populated with STEO-derived numbers, not independently sourced MOMR data. So as it stands, this runs on EIA data.

## Scenario analysis

This is the main feature. The EIA publishes one view of the future. The scenario engine lets you modify the forecast period and see how the balance changes. Historical actuals are never touched.

```python
engine = ScenarioEngine(steo_data, last_actual_month="2026-02")

engine.add_scenario("OPEC Holds Cuts", opec_crude_adj=+4.0)
engine.add_scenario("China Demand Weakness", demand_adj=-0.4)
engine.add_scenario("Bull Case", opec_crude_adj=+2.0, demand_adj=+0.3)
engine.add_scenario("Bear Case", opec_crude_adj=-0.5, demand_adj=-0.5, non_opec_adj=+0.3)

results = engine.run_all()
engine.summary_table()       # quarterly balance comparison
engine.plot_comparison()     # all scenarios on one chart
```

Four levers:
- `opec_crude_adj` (mb/d): shift OPEC crude forecast up or down
- `non_opec_adj` (mb/d): shift non-OPEC supply forecast
- `demand_adj` (mb/d): shift global demand forecast
- `opec_crude_override` (mb/d): set OPEC crude to a flat level

The adjustments are flat deltas applied to all forecast months equally. That's a simplification. A real desk would model a time-varying ramp (e.g. "Saudi goes from 9.0 to 9.5 in Q2, holds through Q3"). But flat deltas are enough to see how sensitive the balance is to different assumptions.

**Example (March 2026):** The STEO forecasts OPEC crude dropping from 29.25 to 23.08 mb/d in a single month. That's a 6 mb/d collapse, likely reflecting the EIA's modelling of an OPEC+ production unwind. The "OPEC Holds Cuts" scenario tests what happens if OPEC stays closer to current levels instead, and it shifts the Q2 average balance from roughly flat (+0.7 mb/d) to a clear surplus (+4.7 mb/d).

The notebook ships with 5 scenarios (base + 4 alternatives). Edit the numbers or add your own.

## How it's structured

Two Jupyter notebooks backed by a modular Python codebase.

**Notebook 1: Data Ingestion** (`01_data_ingestion.ipynb`)
- Downloads the STEO workbook (cached locally, auto-refreshes after 7 days)
- Reads the workbook's `Dates` sheet to auto-detect the last month of actual data vs forecast
- Fetches US crude inventories from the EIA API (weekly data, resampled to monthly)
- Checks whether any OPEC/IEA data has been entered in the CSV templates
- Saves processed data to `data/processed/`

**Notebook 2: Balance Model** (`02_oil_balance_model.ipynb`)
- Parses the STEO workbook directly (with caching)
- Builds supply table (OPEC crude + NGLs + non-OPEC)
- Builds demand table (OECD + non-OECD, with US and China breakouts)
- Calculates the balance and Call on OPEC
- Compares implied stock changes against actual US crude inventories (a rough cross-check; the US is only one piece of global storage, so directional alignment is what matters here, not magnitude)
- Flags each row as Actual or Forecast based on the auto-detected cutoff
- Runs scenario analysis
- Generates 8 charts and a templated commentary summary
- Exports the balance table as CSV and Excel

The model is fully dynamic. It reads the STEO publication date and last historical month from workbook metadata. No hardcoded dates. Re-run both notebooks when a new STEO comes out (~10th of each month) and everything updates.

## Project structure

```
.
├── notebooks/
│   ├── 01_data_ingestion.ipynb        # data fetching and validation
│   └── 02_oil_balance_model.ipynb     # balance model, scenarios, charts
├── src/
│   ├── steo_loader.py                 # STEO workbook parser + metadata extraction
│   ├── eia_client.py                  # EIA API v2 client for inventory data
│   ├── opec_loader.py                 # loads OPEC country production from CSV
│   ├── iea_loader.py                  # loads IEA supply/demand from CSV
│   ├── futures_loader.py              # Brent futures (yfinance + CSV template)
│   ├── balance_model.py               # supply/demand/balance calculations
│   ├── scenario.py                    # scenario analysis engine
│   ├── charts.py                      # 8 matplotlib chart functions
│   ├── commentary.py                  # Jinja2 templated market commentary
│   └── styling.py                     # color palette and chart theme
├── config/
│   ├── settings.py                    # paths, API config, cache settings
│   └── series_ids.py                  # EIA series ID mappings, OPEC country list
├── data/
│   ├── raw/steo/                      # cached STEO workbook (gitignored)
│   ├── processed/                     # parsed CSVs and metadata (gitignored)
│   └── templates/                     # CSV templates for OPEC/IEA entry
├── output/
│   ├── charts/                        # exported PNGs (gitignored)
│   └── tables/                        # balance table CSV + Excel (gitignored)
├── .env                               # EIA API key (gitignored)
├── .gitignore
└── requirements.txt
```

## Charts

8 charts, all with the forecast region shaded:

1. **Global Supply vs Demand** - two lines with surplus/deficit fill between them
2. **Balance Bar** - monthly implied stock change (green = build, red = draw)
3. **Implied vs Actual Inventory** - cumulative model-implied changes vs actual US crude stocks
4. **OPEC Production by Country** - stacked bar of individual OPEC members
5. **Supply Breakdown** - stacked area (OPEC crude, NGLs, non-OPEC)
6. **Demand by Region** - stacked area (OECD vs non-OECD)
7. **Call on OPEC** - market needs vs actual OPEC production
8. **Scenario Comparison** - balance paths under each scenario overlaid

## Setup

```bash
pip install -r requirements.txt
```

You need a free EIA API key. Register at https://www.eia.gov/opendata/register.php, then create a `.env` file:

```
EIA_API_KEY=your_key_here
```

Open the notebooks in VS Code or JupyterLab and run them in order.

## Adding OPEC/IEA data

The model works on just the STEO and EIA API. If you want to incorporate data from other agency reports, fill in the CSV templates in `data/templates/`:

- `opec_production_template.csv` - OPEC crude by country. Pre-populated with STEO-derived estimates, not actual MOMR data. Replace with real MOMR numbers (Table 5.13, secondary sources) if you have them.
- `iea_supply_template.csv` - IEA non-OPEC supply estimates
- `iea_demand_template.csv` - IEA demand by region
- `opec_ngls_template.csv` - OPEC NGL/condensate production
- `brent_futures_template.csv` - Brent futures curve (M1 through M12)

When filled in, the model uses them as overrides over the STEO baseline via a priority cascade (IEA > OPEC > STEO).

## Limitations

Being upfront about what this doesn't do:

- **Single source.** The balance is built almost entirely on EIA STEO data. A desk model would cross-reference against independently sourced OPEC MOMR and IEA OMR numbers. The templates for this exist but aren't populated with independent data.
- **Flat scenario deltas.** The scenario adjustments apply uniformly to all forecast months. A more realistic approach would model time-varying ramps (e.g. OPEC gradually increasing production over 6 months).
- **No price connection.** The model tells you the balance but doesn't quantify what a given surplus/deficit implies for Brent spreads or outright prices. That bridge from fundamentals to trading signal isn't built.
- **US-only inventory cross-check.** The model compares global implied stock changes against US crude inventories, which represent a small slice of global storage. Directional alignment is informative but the magnitudes aren't directly comparable.
- **Templated commentary.** The auto-generated text restates the numbers. It doesn't contain actual market analysis or a view.

## Technical details

- All volumes in mb/d unless stated otherwise. US inventory in million barrels (level).
- Monthly range: Jan 2023 to Dec 2026 (configurable).
- The STEO's stock change series (`t3_stchange_world`) uses opposite sign convention (positive = draws in the STEO, positive = builds in our model). Handled internally.
- OPEC country-level data from the STEO only covers historical months. Forecast months have NaN for individual countries but the aggregate total is still available.
- Cache auto-refresh checks file modification time. Older than 7 days triggers a fresh download. Force with `steo.download(force=True)`.
