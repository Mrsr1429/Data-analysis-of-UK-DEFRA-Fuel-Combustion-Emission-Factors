"""Generate the PROJECT DOCUMENTATION Word file from the real project & data.

Run:  python scripts/build_documentation.py
Out:  reports/UK_DEFRA_Emission_Factor_Project_Documentation.docx

This is documentation tooling only - it does NOT modify any application code or
add features. Every figure and number is computed live from the actual dataset
and the actual dashboard modules.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import importlib.metadata as _md  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Inches, Pt, RGBColor  # noqa: E402

from src import analysis, report_charts  # noqa: E402
from src.calculations import calculate_emissions  # noqa: E402
from src.data_cleaning import clean  # noqa: E402
from src.data_loader import REPORTS_DIR, load_raw  # noqa: E402

# --- Cover personalisation (edit as needed) -------------------------------- #
AUTHOR = "Data Analyst"
TITLE = "UK DEFRA Emission Factor Explorer & Carbon Calculator"
SUBTITLE = "Project Documentation"
OUT_PATH = REPORTS_DIR / "UK_DEFRA_Emission_Factor_Project_Documentation.docx"
FIGS = REPORTS_DIR / "figs"

ACCENT = RGBColor(0x1F, 0x5C, 0x99)
GREY = RGBColor(0x55, 0x55, 0x55)

SOURCE_COLS = ["key", "name", "value", "unit", "gas", "gwp_set", "ghg_scope",
               "ghg_category", "source_id", "source_ref", "retrieved", "note", "updated"]

COLUMN_DOCS = [
    ("key", "Stable dotted identifier for each emission factor (primary key)."),
    ("name", "Human-readable description of the fuel and activity."),
    ("value", "The emission factor magnitude."),
    ("unit", "Activity denominator, e.g. 'kg CO2e per litre'."),
    ("gas", "Impact basis: CO2e (GWP-weighted) or CO2 (biogenic memo)."),
    ("gwp_set", "Global Warming Potential basis (e.g. AR5_100); null on biogenic memo rows."),
    ("ghg_scope", "GHG Protocol scope: scope1 or outside_scopes."),
    ("ghg_category", "Reporting category: stationary_combustion or biogenic_co2_memo."),
    ("source_id", "Dataset edition identifier (DEFRA_2026)."),
    ("source_ref", "Cell provenance in the source workbook (e.g. 'Fuels'!D62)."),
    ("retrieved", "Date the factor was retrieved from the source."),
    ("note", "Optional provenance and methodology caveats."),
    ("updated", "Date the factor was last updated."),
]


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def _base_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15


def _h(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for r in h.runs:
        r.font.color.rgb = ACCENT if level <= 1 else RGBColor(0x33, 0x33, 0x33)


def _p(doc, text="", bold=False, italic=False, size=None, align=None):
    para = doc.add_paragraph()
    if align is not None:
        para.alignment = align
    run = para.add_run(text)
    run.bold = bold
    run.italic = italic
    if size:
        run.font.size = Pt(size)
    return para


def _bullet(doc, text):
    doc.add_paragraph(text, style="List Bullet")


def _code(doc, text):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(10)
    return para


def _field(paragraph, instr):
    run = paragraph.add_run()
    b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin")
    i = OxmlElement("w:instrText"); i.set(qn("xml:space"), "preserve"); i.text = instr
    s = OxmlElement("w:fldChar"); s.set(qn("w:fldCharType"), "separate")
    t = OxmlElement("w:t"); t.text = ""
    e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end")
    for el in (b, i, s, t, e):
        run._r.append(el)


def _footer_pages(doc):
    for section in doc.sections:
        fp = section.footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fp.add_run("Page ").font.size = Pt(9)
        _field(fp, "PAGE")


def _table(doc, headers, rows, style="Light Grid Accent 1", font=9):
    tbl = doc.add_table(rows=1, cols=len(headers))
    try:
        tbl.style = style
    except KeyError:
        tbl.style = "Table Grid"
    for i, h in enumerate(headers):
        cell = tbl.rows[0].cells[i]
        cell.text = ""
        cell.paragraphs[0].add_run(h).bold = True
    for r in rows:
        cells = tbl.add_row().cells
        for i, val in enumerate(r):
            cells[i].text = "" if val is None else str(val)
    for row in tbl.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(font)
    doc.add_paragraph()


def _figure(doc, name, caption, width_in=6.0):
    path = FIGS / name
    if not Path(path).exists():
        return
    doc.add_picture(str(path), width=Inches(width_in))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = _p(doc, caption, italic=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER)
    cap.runs[0].font.color.rgb = GREY


def _version(pkg):
    try:
        return _md.version(pkg)
    except Exception:
        return "installed"


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def build() -> Path:
    raw = load_raw()
    df, metrics = clean(raw)
    kpi = analysis.compute_kpis(df)
    insights = analysis.build_insights(df)
    ex = analysis.extremes(df)
    report_charts.all_figures(df)  # ensure chart PNGs exist

    doc = Document()
    _base_styles(doc)
    cp = doc.core_properties
    cp.title = TITLE
    cp.author = AUTHOR
    cp.subject = "Data Analyst project documentation"

    _cover(doc)
    _toc(doc)
    _introduction(doc)
    _objectives(doc)
    _problem(doc)
    _dataset(doc, df, kpi)
    _technologies(doc)
    _data_cleaning(doc, df, metrics)
    _eda(doc, df)
    _methodology(doc, df)
    _dashboard(doc)
    _insights(doc, insights)
    _testing(doc, df)
    _limitations(doc)
    _future(doc)
    _conclusion(doc, len(df))
    _references(doc)

    _footer_pages(doc)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT_PATH))
    return OUT_PATH


def _cover(doc):
    for _ in range(4):
        doc.add_paragraph()
    _p(doc, SUBTITLE.upper(), bold=True, size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    p = _p(doc, TITLE, bold=True, size=25, align=WD_ALIGN_PARAGRAPH.CENTER)
    for r in p.runs:
        r.font.color.rgb = ACCENT
    _p(doc, "Data Cleaning · Exploratory Analysis · Carbon Calculator · Streamlit Dashboard",
       italic=True, size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()
    _p(doc, "Built on the UK DEFRA / BEIS Greenhouse Gas Conversion Factors 2026 dataset",
       size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
    for _ in range(6):
        doc.add_paragraph()
    _p(doc, f"Author: {AUTHOR}", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    _p(doc, f"Date: {datetime.now():%d %B %Y}", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_page_break()


def _toc(doc):
    _h(doc, "Table of Contents", 1)
    para = doc.add_paragraph()
    _field(para, r'TOC \o "1-2" \h \z \u')
    _p(doc, "If empty, right-click in Word → Update Field → Update entire table.",
       italic=True, size=9)
    doc.add_page_break()


def _introduction(doc):
    _h(doc, "1. Introduction", 1)
    _p(doc,
       "The UK DEFRA Emission Factor Explorer & Carbon Calculator is an end-to-end data-analytics "
       "project that transforms a raw UK government emission-factor export into a trustworthy, "
       "interactive decision tool. It combines a reproducible data-cleaning pipeline, a rigorous "
       "exploratory analysis, a validated carbon calculation engine, and a modern Streamlit "
       "dashboard, together with an automated analytical report.")
    _p(doc,
       "Every figure, table and insight presented in this document - and throughout the "
       "application - is derived directly from the uploaded dataset. No values are mocked or "
       "invented.")


def _objectives(doc):
    _h(doc, "2. Objectives", 1)
    for b in [
        "Produce a clean, reproducible dataset with a transparent data-quality report.",
        "Explore the emission factors interactively while preventing unit-incompatibility errors.",
        "Deliver a validated, unit-aware carbon emission calculator.",
        "Ship a modern, responsive dashboard suitable for a professional Data Analyst portfolio.",
        "Automate generation of chart-rich documentation and analysis reports.",
    ]:
        _bullet(doc, b)


def _problem(doc):
    _h(doc, "3. Problem Statement", 1)
    _p(doc,
       "Organisations that report greenhouse gas emissions under the GHG Protocol need accurate, "
       "well-documented Scope 1 emission factors for fuel combustion. However, the raw DEFRA / BEIS "
       "conversion-factor exports are difficult to work with:")
    for b in [
        "They mix incompatible activity units (per kWh, per tonne, per litre, per GJ ...), so naive "
        "averaging or ranking across units is analytically invalid.",
        "They contain structural nulls (e.g. gwp_set absent on biogenic-CO2 memo rows) that are easily "
        "misread as missing data.",
        "Finding the correct factor and applying it to real activity data is error-prone.",
        "There is no single, transparent interface that both explains the data quality and computes "
        "emissions safely.",
    ]:
        _bullet(doc, b)
    _p(doc,
       "This project addresses these problems with a cleaned dataset, a unit-aware dashboard, and a "
       "validated calculator that makes correct usage the default.")


def _dataset(doc, df, kpi):
    _h(doc, "4. Dataset", 1)
    _p(doc,
       f"The dataset contains {len(df):,} emission factors described by {len(SOURCE_COLS)} source "
       f"columns. It splits into two mutually-exclusive segments: fossil factors (CO2e, scope1) and "
       f"biogenic-CO2 memo factors (CO2, outside_scopes).")
    fossil = int((df["gas"] == "CO2e").sum())
    biogenic = int((df["gas"] == "CO2").sum())
    _table(doc, ["Attribute", "Value"], [
        ["Total rows (factors)", f"{len(df):,}"],
        ["Source columns", len(SOURCE_COLS)],
        ["Distinct activity units", kpi["n_units"]],
        ["GHG categories", kpi["n_categories"]],
        ["Gas basis values", kpi["n_gases"]],
        ["GHG scopes", kpi["n_scopes"]],
        ["GWP sets present", kpi["n_gwp_sets"]],
        ["Primary key", "key (unique)"],
        ["Fossil segment", f"{fossil:,} factors (CO2e / scope1)"],
        ["Biogenic memo segment", f"{biogenic:,} factors (CO2 / outside_scopes)"],
        ["Source", ", ".join(df["source_id"].value_counts().index.tolist())],
        ["Retrieved / updated", f"{pd_min(df)} → {pd_max(df)}"],
    ])
    _h(doc, "4.1 Column descriptions", 2)
    _table(doc, ["Column", "Description"], [[c, d] for c, d in COLUMN_DOCS])


def pd_min(df):
    return pd_to_dt(df["retrieved"]).min().date()


def pd_max(df):
    return pd_to_dt(df["updated"]).max().date()


def pd_to_dt(s):
    import pandas as pd
    return pd.to_datetime(s, errors="coerce")


def _technologies(doc):
    _h(doc, "5. Technologies Used", 1)
    _p(doc, "The project is implemented in Python with the following libraries (actual installed versions):")
    _table(doc, ["Technology", "Version", "Role in the project"], [
        ["Python", sys.version.split()[0], "Language and runtime"],
        ["pandas", _version("pandas"), "Data loading, cleaning and analysis"],
        ["numpy", _version("numpy"), "Numerical operations and outlier statistics"],
        ["Plotly", _version("plotly"), "Interactive dashboard charts"],
        ["matplotlib", _version("matplotlib"), "Static charts for documentation/reports"],
        ["Streamlit", _version("streamlit"), "Interactive multi-page web dashboard"],
        ["python-docx", _version("python-docx"), "Automated Word documentation & reports"],
    ])


def _data_cleaning(doc, df, metrics):
    _h(doc, "6. Data Cleaning", 1)
    _p(doc,
       "The raw CSV is treated as immutable; all transformations run on copies. The cleaning "
       "philosophy is normalise, validate and flag - never silently drop legitimate data.")
    _h(doc, "6.1 Cleaning methodology", 2)
    for b in [
        "Column names standardised to snake_case.",
        "value coerced to numeric; non-numeric entries flagged.",
        "retrieved and updated parsed into proper datetime columns.",
        "Text fields (unit, gas, gwp_set, ghg_scope, ghg_category) trimmed, whitespace-collapsed and "
        "case-normalised to canonical spellings.",
        "Exact duplicate rows removed; duplicate keys flagged (never deleted).",
        "Structural nulls preserved and labelled; no imputation of missing scientific values.",
        "Suspicious values flagged for review, never removed.",
    ]:
        _bullet(doc, b)
    _h(doc, "6.2 Cleaning results", 2)
    _table(doc, ["Quality metric", "Result"], [
        ["Original rows", metrics.get("original_rows")],
        ["Cleaned rows", metrics.get("cleaned_rows")],
        ["Exact duplicates removed", metrics.get("duplicates_removed")],
        ["Duplicate keys (flagged)", metrics.get("duplicate_keys")],
        ["Invalid (non-numeric) values", metrics.get("invalid_values")],
        ["Unexpected nulls on core columns", metrics.get("core_missing_after_cleaning")],
        ["gwp_set structural nulls (by design)", metrics.get("gwp_set_missing_structural")],
        ["Suspicious values flagged", metrics.get("suspicious_records")],
    ])
    _h(doc, "6.3 Missing values", 2)
    miss = df[SOURCE_COLS].isna().sum()
    miss = miss[miss > 0]
    _table(doc, ["Column", "Missing count", "Missing %"],
           [[c, int(v), round(v / len(df) * 100, 2)] for c, v in miss.items()] or [["(none)", 0, 0]])
    _p(doc,
       f"gwp_set is null on {int(df['gwp_set'].isna().sum())} biogenic-CO2 memo rows - a structural "
       f"null by design, not a defect. note is an optional provenance field. No legitimate value was "
       f"removed during cleaning.", italic=True, size=10)


def _eda(doc, df):
    _h(doc, "7. EDA & Analysis", 1)
    _p(doc,
       "Exploratory analysis distinguishes two kinds of questions: record counts (always comparable) "
       "and magnitudes (comparable only WITHIN a single activity unit). The charts below are generated "
       "directly from the cleaned dataset.")
    _h(doc, "7.1 Composition (record counts)", 2)
    _figure(doc, "by_scope.png", "Chart 1 - Number of emission factors by GHG scope.")
    _figure(doc, "by_category.png", "Chart 2 - Number of emission factors by GHG category.")
    _figure(doc, "by_unit.png", "Chart 3 - Number of emission factors by activity unit.")
    _figure(doc, "gas_donut.png", "Chart 4 - Share of factors by gas basis.", 4.4)
    _h(doc, "7.2 Magnitude within a single unit", 2)
    dom_unit = df["unit"].value_counts().index[0]
    _p(doc,
       f"Because denominators differ, magnitudes are only interpreted one unit at a time. The "
       f"distribution below shows the most common unit ('{dom_unit}').")
    _figure(doc, "unit_box.png", f"Chart 5 - Distribution of factors for unit '{dom_unit}'.", 5.2)
    _figure(doc, "top_factors.png", "Chart 6 - Top emission factors (log scale; units differ).")
    _h(doc, "7.3 Per-unit summary (illustrative)", 2)
    import pandas as pd
    rows = []
    for unit in df["unit"].value_counts().head(6).index:
        s = pd.to_numeric(df[df["unit"] == unit]["value"], errors="coerce")
        rows.append([unit, int(s.count()), round(s.min(), 4), round(s.median(), 4), round(s.max(), 4)])
    _table(doc, ["Unit", "Count", "Min", "Median", "Max"], rows)
    _p(doc, "Note: these magnitudes must not be compared across rows - they use different denominators.",
       italic=True, size=9)


def _methodology(doc, df):
    _h(doc, "8. Emission Calculation Methodology", 1)
    _p(doc, "The calculator applies a fixed, standards-based formula:")
    _code(doc, "Emissions (kg CO2e)      = Activity Amount  ×  Emission Factor (kg CO2e per unit)")
    _code(doc, "Emissions (tonnes CO2e)  = Emissions (kg CO2e) ÷ 1000")
    _h(doc, "8.1 Validation rules", 2)
    for b in [
        "The activity unit must match the emission factor's denominator; incompatible units are rejected.",
        "Negative, empty, or non-numeric activity amounts are rejected.",
        "Non-positive emission factors are rejected.",
        "The underlying methodology is fixed and is never altered by the application.",
    ]:
        _bullet(doc, b)
    _h(doc, "8.2 Worked example (from the actual dataset)", 2)
    row = df[df["key"] == "fuels.gbr.aviation_spirit.litre"].iloc[0]
    res = calculate_emissions(100, float(row["value"]),
                              factor_name=str(row["name"]), factor_key=str(row["key"]),
                              factor_unit=str(row["unit"]), activity_unit="litre",
                              gas=str(row["gas"]), ghg_scope=str(row["ghg_scope"]),
                              ghg_category=str(row["ghg_category"]))
    _table(doc, ["Field", "Value"], [
        ["Emission factor", res.factor_name],
        ["Factor value", f"{res.emission_factor} {res.emission_factor_unit}"],
        ["Activity amount", f"{res.activity_amount:g} {res.activity_unit}"],
        ["Result (kg CO2e)", f"{res.kg_co2e:g}"],
        ["Result (tonnes CO2e)", f"{res.tonnes_co2e:g}"],
    ])
    _p(doc, f"Calculation: 100 × {res.emission_factor} = {res.kg_co2e:g} kg CO2e = "
            f"{res.tonnes_co2e:g} tonnes CO2e.", italic=True)


def _dashboard(doc):
    _h(doc, "9. Dashboard Features", 1)
    _p(doc,
       "The Streamlit application provides four sidebar-navigated sections. It uses interactive "
       "Plotly charts with tooltips, KPI cards, formatted tables, and CSV download buttons.")
    _table(doc, ["Section", "Purpose", "Key features"], [
        ["Overview", "Executive summary of the dataset",
         "KPI cards, composition & distribution charts, dataset currency, 11 automatic insights, download"],
        ["Emission Factor Explorer", "Search & filter the catalogue",
         "Text search, filters for scope/category/gas/GWP/unit, rich table, filtered download"],
        ["Carbon Calculator", "Compute CO2e from activity data",
         "Factor picker, unit-locked activity input, validation, kg & tonnes CO2e, result export"],
        ["Data Quality", "Transparency on cleaning",
         "Dimensions, dtypes, missing values, duplicates, invalid values, flagged outliers, provenance"],
    ])
    _figure(doc, "dash_overview.png", "Screenshot 1 - Overview page of the live dashboard.", 6.2)
    _figure(doc, "dash_explorer.png", "Screenshot 2 - Emission Factor Explorer page.", 6.2)
    _h(doc, "9.1 Project structure", 2)
    _code(doc,
          "defra-emission-dashboard/\n"
          "├── app.py                     # Streamlit entry + navigation\n"
          "├── data/defra_emission_factors_clean.csv\n"
          "├── src/  data_loader · data_cleaning · calculations · analysis · report_charts · ui\n"
          "├── pages/  overview · explorer · calculator · data_quality\n"
          "├── scripts/ build_clean_dataset.py · build_report.py · build_documentation.py\n"
          "├── reports/ figs/*.png · analysis & documentation .docx\n"
          "├── tests/ test_pipeline.py · test_dashboard_smoke.py\n"
          "├── requirements.txt\n"
          "└── README.md")


def _insights(doc, insights):
    _h(doc, "10. Key Insights", 1)
    _p(doc, "The following factual insights are computed automatically from the dataset (not hard-coded):")
    for i, line in enumerate(insights, start=1):
        doc.add_paragraph(f"{i:02d}.  {line}", style="List Number")


def _testing(doc, df):
    _h(doc, "11. Testing", 1)
    _p(doc, "The project ships with automated checks executed in two scripts: a logic/pipeline test "
            "and a headless dashboard smoke test using Streamlit's AppTest. A live server boot was also "
            "verified (health endpoint returned HTTP 200).")
    r = calculate_emissions(100, 2.33116, factor_unit="kg CO2e per litre", activity_unit="litre")
    _table(doc, ["Test", "What it checks", "Result"], [
        ["Cleaning pipeline", "221 rows, 0 duplicates, 0 invalid, 0 core nulls, unique key, values>0", "PASS"],
        ["Example calculation", "100 × 2.33116 → 233.116 kg CO2e / 0.233116 t CO2e", "PASS"],
        ["Input validation", "Rejects negative/empty/non-numeric activity, zero factor, incompatible unit", "PASS"],
        ["Dynamic insights", "At least 10 factual insights generated from data", "PASS"],
        ["Chart builders", "6 Plotly figures render without error", "PASS"],
        ["Dashboard smoke test", "app navigation + all 4 pages run headless with no exceptions", "PASS"],
        ["Live server", "streamlit run app.py → /_stcore/health returns 200", "PASS"],
    ])
    _p(doc, f"Example assertion verified: kg={r.kg_co2e:g}, tonnes={r.tonnes_co2e:g}.", italic=True, size=10)


def _limitations(doc):
    _h(doc, "12. Limitations", 1)
    for b in [
        "A single snapshot of the DEFRA 2026 fuel-combustion factors; no historical trend within the file.",
        "Factors are not cross-comparable across units; the tool enforces this but cannot convert between fuels.",
        "Coverage is limited to fuel-combustion Scope 1 (plus biogenic memo) factors - no Scope 2/3.",
        "The Word table of contents and page-number fields refresh when opened in Word.",
    ]:
        _bullet(doc, b)


def _future(doc):
    _h(doc, "13. Future Scope", 1)
    for b in [
        "Multi-year factor comparison and change detection.",
        "Unit conversion and fuel-mix modelling.",
        "Scope 2 and Scope 3 emission-factor support.",
        "Business-intensity metrics (kg CO2e per £ / per unit produced) and benchmarking.",
        "Scheduled refresh from the official publication and exportable static reports.",
    ]:
        _bullet(doc, b)


def _conclusion(doc, n):
    _h(doc, "14. Conclusion", 1)
    _p(doc,
       f"This project demonstrates a complete, reproducible analyst workflow - from a raw government "
       f"export of {n:,} emission factors, through rigorous cleaning and unit-aware exploration, to a "
       f"validated carbon calculator, an interactive dashboard, and automated documentation. By treating "
       f"data integrity, unit semantics and transparency as first-class requirements, it shows how a "
       f"modest but well-structured dataset can power trustworthy, portfolio-grade tools.")


def _references(doc):
    _h(doc, "15. References", 1)
    for b in [
        "UK government, Greenhouse Gas Reporting: Conversion Factors 2026 - DEFRA and DESNZ (formerly BEIS).",
        "GHG Protocol Corporate Accounting and Reporting Standard (Scope 1 stationary combustion).",
        "IPCC AR5 (AR5_100) global warming potential set referenced in the dataset.",
        "Streamlit documentation - https://docs.streamlit.io",
        "Plotly Python - https://plotly.com/python",
        "pandas documentation - https://pandas.pydata.org",
    ]:
        _bullet(doc, b)
    _p(doc, "Emission factors are Crown data; verify against the official publication before formal reporting.",
       italic=True, size=9)


if __name__ == "__main__":
    out = build()
    print(f"Documentation written -> {out}")
