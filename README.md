# 🌍 UK DEFRA Emission Factor Explorer & Carbon Calculator

A production-quality **Data Analyst portfolio project**: an interactive Streamlit
dashboard, a validated data-cleaning pipeline, a carbon calculation engine, and an
auto-generated Word report — all built on the real **UK DEFRA / BEIS fuel-combustion
emission factors** dataset. Every number shown comes directly from the uploaded CSV.
**No mock data, no invented statistics.**

---

## 1. Project overview

This project turns a raw government emission-factor export into a decision-ready tool:

1. **Understand** the dataset (schema, distributions, quality issues).
2. **Clean & validate** it into a reproducible artefact (`defra_emission_factors_clean.csv`).
3. **Explore** it interactively (composition, distributions, trends).
4. **Calculate** carbon emissions from real activity data (`Emissions = Amount × Factor`).
5. **Report** the findings in an auto-generated, chart-rich Word document.

## 2. Business problem

Organisations reporting under the GHG Protocol need accurate, well-documented Scope 1
emission factors for fuel combustion. Raw DEFRA spreadsheets are hard to explore,
mix incompatible units, and contain structural nulls that are easy to misread. This
tool provides a single, trustworthy interface to **find** the right factor and **apply**
it correctly — while being explicit about data quality and unit compatibility.

## 3. Objectives

- Deliver a clean, reproducible dataset with a transparent quality report.
- Prevent analytical errors caused by comparing emission factors across incompatible units.
- Provide a validated, unit-aware emission calculator.
- Ship a modern, responsive dashboard suitable for a professional portfolio.

## 4. Dataset description

| Attribute | Value |
|---|---|
| Source | UK DEFRA / BEIS Greenhouse Gas emission factors (2026) | https://www.kaggle.com/code/greencalculus/uk-company-carbon-footprint-secr-scope-1-2?select=defra-emission-factors.csv
| Rows | **221** emission factors |
| Columns | **13** source columns |
| Primary key | `key` (unique) |
| Two segments | 166 **fossil** factors (`CO2e`, `scope1`, `stationary_combustion`) · 55 **biogenic-CO₂ memo** factors (`CO2`, `outside_scopes`) |

**Column meanings**

| Column | Meaning |
|---|---|
| `key` | Stable dotted identifier for the factor |
| `name` | Human-readable label |
| `value` | Emission factor magnitude |
| `unit` | Activity denominator (e.g. `kg CO2e per litre`) |
| `gas` | Impact basis — `CO2e` or `CO2` |
| `gwp_set` | Global Warming Potential basis (e.g. `AR5_100`); null for biogenic memo rows |
| `ghg_scope` | GHG-Protocol scope (`scope1` / `outside_scopes`) |
| `ghg_category` | Reporting category (`stationary_combustion` / `biogenic_co2_memo`) |
| `source_id` | Dataset edition (`DEFRA_2026`) |
| `source_ref` | Cell provenance in the source workbook (e.g. `'Fuels'!D62`) |
| `retrieved` / `updated` | Snapshot / revision dates |
| `note` | Optional provenance & methodology caveats |

## 5. Data cleaning

- Column names standardised; `value` coerced to numeric (non-numeric → flagged, none found).
- `retrieved` / `updated` parsed to real datetimes.
- Text fields (`unit`, `gas`, `gwp_set`, `ghg_scope`, `ghg_category`) trimmed and case-normalised
  to canonical spellings.
- Exact duplicates removed (**0** present); duplicate `key`s detected and **flagged, not deleted** (**0** present).
- **Structural nulls preserved & labelled** — `gwp_set` is intentionally null on biogenic-CO₂ memo rows.
- Outliers are **flagged for review, never removed** (DEFRA factors legitimately span orders of magnitude).
- The original CSV is treated as **immutable**; all work happens on copies. `df_clean` is exported to
  `data/defra_emission_factors_clean.csv`.

## 6. Exploratory data analysis

Interactive **Plotly** charts (dashboard) and **matplotlib** figures (Word report):

- Factor counts by GHG scope, category, gas, unit and GWP set (record counts are always comparable).
- Value distributions visualised **within a single unit only** (violin + median-by-category) to respect unit incompatibility.
- Top emission factors (colour-coded by unit) and dataset currency over time.
- **11 dynamic insights** computed live from the data (nothing hard-coded).

## 7. Dashboard features

| Section | Highlights |
|---|---|
| **Overview** | KPI cards, interactive Plotly charts, automatic insights, full-dataset download |
| **Emission Factor Explorer** | Search + multi-filter (scope / category / gas / GWP set / unit), rich table, filtered download |
| **Carbon Calculator** | Factor picker, unit-locked activity input, validation, kg & tonnes CO2e, result export |
| **Data Quality** | Dimensions, dtypes, missing values, duplicates, invalid values, flagged outliers, provenance |

Design: KPI cards, responsive layout, tooltips, readable formatted tables, sidebar navigation.

## 8. Calculation methodology

```
Emissions (kg CO2e) = Activity Amount × Emission Factor (kg CO2e per unit)
Emissions (t  CO2e) = Emissions (kg CO2e) / 1000
```

The activity unit **must** match the factor's denominator; incompatible or negative/invalid
inputs are rejected.

**Example** — 100 litres of UK aviation spirit (factor `2.33116 kg CO2e per litre`):

```
100 × 2.33116 = 233.116 kg CO2e = 0.233116 tonnes CO2e   ✅
```

## 9. Installation

```bash
cd defra-emission-dashboard
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 10. How to run

```bash
# 1) build the cleaned dataset (also runs automatically on first app start)
python scripts/build_clean_dataset.py

# 2) generate the Word report (matplotlib charts + .docx)
python scripts/build_report.py

# 3) launch the dashboard
streamlit run app.py
```

Then open the URL Streamlit prints (default http://localhost:8501).

## 11. Testing

```bash
python tests/test_pipeline.py         # cleaning, calculation, validation, insights, charts
python tests/test_dashboard_smoke.py  # every page runs headless via Streamlit AppTest
```

## 12. Project structure

```
defra-emission-dashboard/
├── app.py                     # Streamlit entry + navigation
├── data/
│   └── defra_emission_factors_clean.csv
├── src/
│   ├── data_loader.py         # path resolution + loading (raw immutable)
│   ├── data_cleaning.py       # clean() pipeline + metrics
│   ├── calculations.py        # emission calculation engine + validation
│   ├── analysis.py            # KPIs, dynamic insights, Plotly figures
│   ├── report_charts.py       # matplotlib figures for the report
│   └── ui.py                  # shared Streamlit helpers (KPI cards, cache)
├── pages/
│   ├── overview.py
│   ├── explorer.py
│   ├── calculator.py
│   └── data_quality.py
├── scripts/
│   ├── build_clean_dataset.py
│   └── build_report.py
├── reports/
│   ├── figs/                  # generated charts
│   └── UK_DEFRA_Emission_Factor_Analysis_Report.docx
├── tests/
├── requirements.txt
└── README.md
```

## 13. Limitations

- A single snapshot of DEFRA 2026 fuel-combustion factors (no historical trend within the file).
- Factors are not cross-comparable across activity units; the tool enforces this but cannot convert fuels.
- The Word TOC field is populated by Word on open (right-click → *Update Field*).

## 14. Future improvements

- Multi-year factor comparison and change detection.
- Unit conversion / fuel-mix modelling and Scope 2/3 support.
- Business-ratio intensity metrics and benchmarking.
- Export of the dashboard as a static report and scheduled refreshes.

## 15. Data source / attribution

> UK government Greenhouse Gas Reporting: Conversion Factors 2026 — DEFRA / BEIS.
> Research commissioned by the UK Department for Environment, Food & Rural Affairs and
> the Department for Energy Security & Net Zero. Emission factors are Crown data; please
> verify against the official publication before formal reporting.

---

*Prepared as a Data Analyst portfolio project. All analysis is reproducible from the uploaded CSV.*
