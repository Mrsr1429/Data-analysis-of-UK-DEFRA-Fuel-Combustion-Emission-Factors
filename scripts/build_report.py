"""Generate the professional Word analysis report from the ACTUAL dataset.

Run:  python scripts/build_report.py
Out:  reports/UK_DEFRA_Emission_Factor_Analysis_Report.docx
      reports/figs/*.png   (matplotlib charts)

Every statistic, table and chart is computed live from the cleaned dataset.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Inches, Pt, RGBColor  # noqa: E402

from src import analysis, report_charts  # noqa: E402
from src.calculations import calculate_emissions  # noqa: E402
from src.data_cleaning import clean  # noqa: E402
from src.data_loader import REPORTS_DIR, load_raw  # noqa: E402

# --- Edit these to personalise the cover page ------------------------------ #
AUTHOR = "Data Analyst"
TITLE = "UK DEFRA Emission Factor Explorer & Carbon Calculator"
REPORT_PATH = REPORTS_DIR / "UK_DEFRA_Emission_Factor_Analysis_Report.docx"

ACCENT = RGBColor(0x1F, 0x5C, 0x99)

COLUMN_DOCS = [
    ("key", "Stable dotted identifier for each emission factor (primary key)."),
    ("name", "Human-readable description of the fuel and activity."),
    ("value", "The emission factor magnitude."),
    ("unit", "Activity denominator, e.g. 'kg CO2e per litre'."),
    ("gas", "Impact basis: CO2e (GWP-weighted) or CO2 (biogenic memo)."),
    ("gwp_set", "Global Warming Potential basis, e.g. AR5_100; null on biogenic memo rows."),
    ("ghg_scope", "GHG Protocol scope: scope1 or outside_scopes."),
    ("ghg_category", "Reporting category: stationary_combustion or biogenic_co2_memo."),
    ("source_id", "Dataset edition identifier (DEFRA_2026)."),
    ("source_ref", "Cell provenance in the source workbook, e.g. 'Fuels'!D62."),
    ("retrieved", "Date the factor was retrieved from the source."),
    ("note", "Optional provenance and methodology caveats."),
    ("updated", "Date the factor was last updated."),
]


# --------------------------------------------------------------------------- #
# Low-level docx helpers
# --------------------------------------------------------------------------- #
def _set_base_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15


def _heading(doc: Document, text: str, level: int = 1) -> None:
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = ACCENT if level <= 1 else RGBColor(0x33, 0x33, 0x33)


def _para(doc: Document, text: str = "", italic: bool = False, bold: bool = False,
          size: int | None = None, align=None) -> None:
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    run = p.add_run(text)
    run.italic = italic
    run.bold = bold
    if size:
        run.font.size = Pt(size)
    return p


def _bullet(doc: Document, text: str) -> None:
    doc.add_paragraph(text, style="List Bullet")


def _add_field(paragraph, instr: str) -> None:
    """Insert a Word field code (used for TOC and PAGE numbers)."""
    run = paragraph.add_run()
    b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin")
    i = OxmlElement("w:instrText"); i.set(qn("xml:space"), "preserve"); i.text = instr
    s = OxmlElement("w:fldChar"); s.set(qn("w:fldCharType"), "separate")
    t = OxmlElement("w:t"); t.text = ""
    e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end")
    for el in (b, i, s, t, e):
        run._r.append(el)


def _page_number_footer(doc: Document) -> None:
    for section in doc.sections:
        footer_p = section.footer.paragraphs[0]
        footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        footer_p.add_run("Page ").font.size = Pt(9)
        _add_field(footer_p, "PAGE")


def _table(doc: Document, headers: list[str], rows: list[list], style: str = "Light Grid Accent 1") -> None:
    tbl = doc.add_table(rows=1, cols=len(headers))
    try:
        tbl.style = style
    except KeyError:
        tbl.style = "Table Grid"
    for i, h in enumerate(headers):
        cell = tbl.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        run.bold = True
    for r in rows:
        cells = tbl.add_row().cells
        for i, val in enumerate(r):
            cells[i].text = "" if val is None else str(val)
    for row in tbl.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(9)
    doc.add_paragraph()


def _figure(doc: Document, path, caption: str, width_in: float = 6.0) -> None:
    if not Path(path).exists():
        return
    doc.add_picture(str(path), width=Inches(width_in))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = _para(doc, caption, italic=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER)
    cap.runs[0].font.color.rgb = RGBColor(0x55, 0x55, 0x55)


# --------------------------------------------------------------------------- #
# Document sections
# --------------------------------------------------------------------------- #
def build_report() -> Path:
    raw = load_raw()
    df, metrics = clean(raw)
    kpi = analysis.compute_kpis(df)
    insights = analysis.build_insights(df)
    ex = analysis.extremes(df)
    figs = report_charts.all_figures(df)

    doc = Document()
    _set_base_styles(doc)

    _cover(doc)
    _toc(doc)

    _introduction(doc)
    _objectives(doc)
    _dataset_description(doc, df, kpi)
    _data_cleaning(doc, df, metrics)
    _eda(doc, df, metrics, kpi, ex, figs)
    _factor_analysis(doc, df)
    _calculator(doc, df)
    _dashboard(doc)
    _key_insights(doc, insights)
    _technologies(doc)
    _architecture(doc)
    _limitations_future_conclusion(doc)
    _references(doc)

    _page_number_footer(doc)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(REPORT_PATH))
    return REPORT_PATH


def _cover(doc: Document) -> None:
    for _ in range(4):
        doc.add_paragraph()
    _para(doc, "DATA ANALYSIS REPORT", bold=True, size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    p = _para(doc, TITLE, bold=True, size=26, align=WD_ALIGN_PARAGRAPH.CENTER)
    for r in p.runs:
        r.font.color.rgb = ACCENT
    _para(doc, "Exploratory Data Analysis · Data Cleaning · Carbon Emission Calculator",
          italic=True, size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()
    _para(doc, f"Based on the UK DEFRA / BEIS Greenhouse Gas Conversion Factors 2026 dataset",
          size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
    for _ in range(6):
        doc.add_paragraph()
    _para(doc, f"Author: {AUTHOR}", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, f"Date: {datetime.now():%d %B %Y}", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_page_break()


def _toc(doc: Document) -> None:
    _heading(doc, "Table of Contents", level=1)
    p = doc.add_paragraph()
    _add_field(p, r'TOC \o "1-2" \h \z \u')
    _para(doc, "If the table of contents is empty, right-click it in Word and choose "
               "\u201cUpdate Field\u201d \u2192 \u201cUpdate entire table\u201d.", italic=True, size=9)
    doc.add_page_break()


def _introduction(doc: Document) -> None:
    _heading(doc, "1. Introduction", 1)
    _heading(doc, "1.1 Background of emission factors", 2)
    _para(doc,
          "Emission factors convert an activity level (such as litres of fuel burned or kWh of "
          "energy consumed) into an equivalent quantity of greenhouse gases, normally expressed in "
          "kilograms of carbon-dioxide equivalent (kg CO2e). They are the arithmetic backbone of "
          "corporate carbon accounting under the GHG Protocol and national inventory systems.")
    _heading(doc, "1.2 Purpose of the DEFRA dataset", 2)
    _para(doc,
          "The UK government's Department for Environment, Food & Rural Affairs (DEFRA), together "
          "with BEIS, publishes annually-revised conversion factors for fuel combustion. This "
          "project builds a reliable, transparent toolchain on top of that export: to clean and "
          "validate it, to explore it interactively, and to apply it safely in emission calculations.")


def _objectives(doc: Document) -> None:
    _heading(doc, "2. Project Objectives", 1)
    for b in [
        "Produce a clean, reproducible dataset with a transparent data-quality report.",
        "Prevent analytical errors from comparing factors across incompatible activity units.",
        "Deliver a validated, unit-aware carbon emission calculator.",
        "Ship a modern, interactive Streamlit dashboard suitable for a professional portfolio.",
        "Automate generation of a chart-rich analytical report.",
    ]:
        _bullet(doc, b)


def _dataset_description(doc: Document, df, kpi) -> None:
    _heading(doc, "3. Dataset Description", 1)
    _para(doc,
          f"The dataset comprises {len(df):,} emission factors described by "
          f"{len(COLUMN_DOCS)} source columns, covering {kpi['n_units']} distinct activity units, "
          f"{kpi['n_categories']} GHG categories, {kpi['n_gases']} gas basis values and "
          f"{kpi['n_scopes']} GHG scopes.")
    _table(doc, ["Attribute", "Value"], [
        ["Total rows (factors)", f"{len(df):,}"],
        ["Source columns", len(COLUMN_DOCS)],
        ["Distinct activity units", kpi["n_units"]],
        ["GHG categories", kpi["n_categories"]],
        ["Gas basis values", kpi["n_gases"]],
        ["GHG scopes", kpi["n_scopes"]],
        ["Primary key", "key (unique)"],
        ["Data source", ", ".join(df['source_id'].value_counts().index.tolist())],
    ])
    _heading(doc, "3.1 Column descriptions", 2)
    _table(doc, ["Column", "Description"], [[c, d] for c, d in COLUMN_DOCS])


def _data_cleaning(doc: Document, df, metrics) -> None:
    _heading(doc, "4. Data Cleaning", 1)
    _para(doc,
          "The raw CSV is treated as immutable; all transformations run on copies. Cleaning means "
          "normalise, validate and flag — never silently drop legitimate data.")
    _heading(doc, "4.1 Missing values", 2)
    miss = df[[c for c, _ in COLUMN_DOCS]].isna().sum()
    miss = miss[miss > 0]
    _table(doc, ["Column", "Missing count", "Missing %"],
           [[c, int(v), round(v / len(df) * 100, 2)] for c, v in miss.items()]
           or [["(none)", 0, 0]])
    _para(doc,
          f"`gwp_set` is null on {int(df['gwp_set'].isna().sum())} rows. These are the biogenic-CO2 "
          "memo factors, which are not GWP-weighted — a structural null by design, preserved rather "
          "than imputed. `note` is an optional provenance field. Unexpected nulls on core columns: "
          f"{metrics.get('core_missing_after_cleaning', 0)}.", italic=True, size=10)
    _heading(doc, "4.2 Duplicate records", 2)
    _para(doc, f"Exact duplicate rows removed: {metrics.get('duplicates_removed', 0)}. "
               f"Duplicate keys (flagged, not removed): {metrics.get('duplicate_keys', 0)}.")
    _heading(doc, "4.3 Data-type corrections", 2)
    _bullet(doc, "`value` coerced to a numeric type; non-numeric entries flagged "
                 f"({metrics.get('invalid_values', 0)} found).")
    _bullet(doc, "`retrieved` and `updated` parsed into proper datetime columns.")
    _bullet(doc, "Text fields trimmed, whitespace-collapsed and case-normalised to canonical spellings.")
    _heading(doc, "4.4 Data-quality issues & methodology", 2)
    _bullet(doc, f"Suspicious values flagged for review (never removed): {metrics.get('suspicious_records', 0)}.")
    _bullet(doc, "Outlier detection uses a robust z-score on log-transformed values plus a conservative "
                 "Tukey fence, computed WITHIN each activity unit to respect incompatible scales.")
    _bullet(doc, "All legitimate DEFRA values — including genuinely high ones — are preserved.")


def _eda(doc: Document, df, metrics, kpi, ex, figs) -> None:
    _heading(doc, "5. Exploratory Data Analysis", 1)
    _para(doc, "Charts are generated directly from the cleaned dataset with matplotlib.")
    _heading(doc, "5.1 Composition", 2)
    _para(doc, "Record counts by category are always comparable, unlike raw magnitudes.")
    _figure(doc, figs["scope"], "Figure 1 — Number of emission factors by GHG scope.")
    _figure(doc, figs["category"], "Figure 2 — Number of emission factors by GHG category.")
    _figure(doc, figs["unit"], "Figure 3 — Number of emission factors by activity unit.")
    _figure(doc, figs["gas"], "Figure 4 — Share of factors by gas basis.", width_in=4.4)
    _heading(doc, "5.2 Distribution (within a single unit)", 2)
    dom_unit = df["unit"].value_counts().index[0]
    summary = analysis.within_unit_summary(df, dom_unit)
    _para(doc,
          f"Emission-factor magnitudes are only comparable within one unit. The distribution below "
          f"shows the most common unit ('{dom_unit}'): median {summary['50%']:,.4f}, "
          f"mean {summary['mean']:,.4f}, min {summary['min']:,.4f}, max {summary['max']:,.4f}.")
    _figure(doc, figs["box"], f"Figure 5 — Distribution of factors for unit '{dom_unit}'.", width_in=5.2)
    _figure(doc, figs["top"], "Figure 6 — Top 12 emission factors (log scale; units differ).")


def _factor_analysis(doc: Document, df) -> None:
    ex = analysis.extremes(df)
    _heading(doc, "6. Emission Factor Analysis", 1)
    _para(doc, "Key statistics segmented by the reporting dimensions present in the dataset.")
    for idx, (col, title) in enumerate([("ghg_scope", "GHG scope"), ("ghg_category", "GHG category"),
                        ("gas", "Gas basis"), ("gwp_set", "GWP set")], start=1):
        vc = df[col].fillna("(none)").value_counts()
        _heading(doc, f"6.{idx} Breakdown by {title}", 3)
        _table(doc, [title, "Count", "Share %"],
               [[str(i), int(v), round(v / len(df) * 100, 1)] for i, v in vc.items()])
    _heading(doc, "6.5 Extremes (contextualised by unit)", 3)
    _table(doc, ["", "Name", "Value", "Unit"], [
        ["Highest", ex["highest"]["name"], f"{ex['highest']['value']:,.4f}", ex["highest"]["unit"]],
        ["Lowest", ex["lowest"]["name"], f"{ex['lowest']['value']:,.5f}", ex["lowest"]["unit"]],
    ])
    _para(doc, "Highest and lowest factors use different units; the comparison is descriptive only, "
               "not a ranking of climate impact.", italic=True, size=9)


def _calculator(doc: Document, df) -> None:
    _heading(doc, "7. Carbon Emission Calculator", 1)
    _para(doc, "Formula:")
    _para(doc, "Emissions (kg CO2e) = Activity Amount  ×  Emission Factor (kg CO2e per unit)", bold=True)
    _para(doc, "Emissions (tonnes CO2e) = Emissions (kg CO2e) ÷ 1000", bold=True)
    _heading(doc, "7.1 Methodology", 2)
    _bullet(doc, "The activity unit must match the emission factor's denominator; incompatible inputs are rejected.")
    _bullet(doc, "Negative, empty, non-numeric activity and non-positive factors are rejected.")
    _bullet(doc, "The underlying calculation methodology is fixed and never altered by the app.")
    _heading(doc, "7.2 Worked example (from the actual dataset)", 2)
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
    _para(doc, f"Calculation: 100 × {res.emission_factor} = {res.kg_co2e:g} kg CO2e "
               f"= {res.tonnes_co2e:g} tonnes CO2e.", italic=True)


def _dashboard(doc: Document) -> None:
    _heading(doc, "8. Interactive Dashboard", 1)
    _para(doc, "The Streamlit application provides four sections with sidebar navigation:")
    _bullet(doc, "Overview — KPI cards, interactive Plotly charts and dynamically generated insights.")
    _bullet(doc, "Emission Factor Explorer — searchable, filterable table with filtered-data download.")
    _bullet(doc, "Carbon Calculator — unit-locked, validated emission computation with result export.")
    _bullet(doc, "Data Quality — dimensions, dtypes, missing values, duplicates, invalid and flagged records.")
    _para(doc, "Screenshots can be captured by running 'streamlit run app.py' and pasted here.",
          italic=True, size=9)


def _key_insights(doc: Document, insights) -> None:
    _heading(doc, "9. Key Insights", 1)
    _para(doc, "The following factual insights were computed automatically from the dataset:")
    for i, line in enumerate(insights, start=1):
        doc.add_paragraph(f"{i:02d}.  {line}", style="List Number")


def _technologies(doc: Document) -> None:
    _heading(doc, "10. Technologies Used", 1)
    _table(doc, ["Technology", "Role"], [
        ["Python 3.11", "Language / analysis runtime"],
        ["pandas", "Data loading, cleaning and manipulation"],
        ["numpy", "Numerical operations"],
        ["Plotly", "Interactive dashboard charts"],
        ["matplotlib", "Static charts embedded in this report"],
        ["Streamlit", "Interactive multi-page web dashboard"],
        ["python-docx", "Automated generation of this report"],
    ])


def _architecture(doc: Document) -> None:
    _heading(doc, "11. Project Architecture", 1)
    _para(doc, "A layered design separates concerns and keeps the modules independently testable:")
    for b in [
        "src/data_loader.py — locates the raw CSV (immutable) and the cleaned artefact.",
        "src/data_cleaning.py — the clean() pipeline and quality metrics.",
        "src/calculations.py — pure, dependency-free emission engine with validation.",
        "src/analysis.py — KPIs, dynamic insights and Plotly figure builders.",
        "src/report_charts.py — matplotlib figures for this report.",
        "src/ui.py — shared Streamlit helpers and cached data access.",
        "pages/ — the four dashboard screens driven by app.py navigation.",
        "tests/ — pipeline assertions and a headless AppTest smoke test.",
    ]:
        _bullet(doc, b)


def _limitations_future_conclusion(doc: Document) -> None:
    _heading(doc, "12. Limitations", 1)
    for b in [
        "A single snapshot of DEFRA 2026 fuel-combustion factors; no historical trend within the file.",
        "Factors are not cross-comparable across units; the tool enforces this but cannot convert fuels.",
        "The table of contents and page-number fields update when the document is opened in Word.",
    ]:
        _bullet(doc, b)
    _heading(doc, "13. Future Improvements", 1)
    for b in [
        "Multi-year factor comparison and change detection.",
        "Unit-conversion and fuel-mix modelling, plus Scope 2 and Scope 3 support.",
        "Business-intensity metrics and peer benchmarking.",
    ]:
        _bullet(doc, b)
    _heading(doc, "14. Conclusion", 1)
    _para(doc,
          "This project demonstrates a complete, reproducible analyst workflow — from a raw "
          "government export through rigorous cleaning, unit-aware exploration and validated "
          "calculation, to an interactive dashboard and an automated report. It shows that a small, "
          "well-structured dataset can power trustworthy tools when data integrity, unit semantics "
          "and transparency are treated as first-class requirements.")


def _references(doc: Document) -> None:
    _heading(doc, "15. Data Source / References", 1)
    _para(doc, "UK government, Greenhouse Gas Reporting: Conversion Factors 2026, "
               "Department for Environment, Food & Rural Affairs (DEFRA) and the Department for "
               "Energy Security & Net Zero (formerly BEIS). Emission factors are Crown data; verify "
               "against the official publication before formal reporting.")


if __name__ == "__main__":
    out = build_report()
    print(f"Report written -> {out}")
