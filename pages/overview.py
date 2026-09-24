"""OVERVIEW page - KPIs, interactive Plotly charts and automatic insights."""

from __future__ import annotations

import streamlit as st

from src import analysis
from src.ui import eyebrow, fmt, get_data, kpi_row

st.title("🌍 UK DEFRA Emission Factor Explorer")
st.caption(
    "An interactive explorer and carbon calculator built on the official UK "
    "DEFRA / BEIS fuel-combustion emission factors. All figures are derived "
    "directly from the uploaded dataset — nothing is mocked."
)

df, _ = get_data()
kpi = analysis.compute_kpis(df)

eyebrow("Key metrics")
kpi_row(
    [
        {"label": "Emission factors", "value": f"{kpi['total_factors']:,}", "help": "Total rows in the cleaned dataset"},
        {"label": "GHG categories", "value": kpi["n_categories"], "help": "Distinct ghg_category values"},
        {"label": "Activity units", "value": kpi["n_units"], "help": "Distinct denominator units (not cross-comparable)"},
        {"label": "Gas bases", "value": kpi["n_gases"], "help": "e.g. CO2e / CO2"},
        {"label": "GHG scopes", "value": kpi["n_scopes"], "help": "e.g. scope1 / outside_scopes"},
        {"label": "GWP sets", "value": kpi["n_gwp_sets"], "help": "Distinct GWP bases present"},
    ]
)

st.divider()
eyebrow("Composition (record counts — safe to compare)")
left, right = st.columns(2)
with left:
    st.plotly_chart(analysis.fig_counts_bar(df, "ghg_scope", "Factors by GHG scope"), width="stretch")
with right:
    st.plotly_chart(analysis.fig_counts_bar(df, "ghg_category", "Factors by GHG category"), width="stretch")

c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(analysis.fig_counts_bar(df, "unit", "Factors by activity unit", color="Cividis"), width="stretch")
with c2:
    st.plotly_chart(analysis.fig_gas_pie(df), width="stretch")

st.divider()
eyebrow("Magnitude (compared only WITHIN a single unit)")
st.info(
    "Emission factors use different denominators (per kWh, per tonne, per litre …). "
    "Their magnitudes are **not** directly comparable, so pick one unit to inspect its distribution.",
    icon="ℹ️",
)
units = analysis.units_sorted_by_frequency(df)
unit_choice = st.selectbox("Select activity unit", units, index=0)
d1, d2 = st.columns(2)
with d1:
    st.plotly_chart(analysis.fig_distribution_by_unit(df, unit_choice), width="stretch")
with d2:
    st.plotly_chart(analysis.fig_median_by_category_within_unit(df, unit_choice), width="stretch")

summary = analysis.within_unit_summary(df, unit_choice)
st.caption(
    f"**{unit_choice}** — n={int(summary['count']):,} · mean={fmt(summary['mean'])} · "
    f"median={fmt(summary['50%'])} · min={fmt(summary['min'])} · max={fmt(summary['max'])}"
)

st.divider()
eyebrow("Highest factors")
st.plotly_chart(analysis.fig_top_factors(df, n=12), width="stretch")
st.caption("Bars are coloured by unit — remember that a tall bar may simply use a mass/volume denominator (per tonne).")

st.divider()
eyebrow("Data currency")
r_dates = analysis.fig_records_by_date(df)
st.plotly_chart(r_dates, width="stretch")

st.divider()
eyebrow("Automatic insights")
for i, line in enumerate(analysis.build_insights(df), start=1):
    st.markdown(
        f'<div class="insight-card"><b>{i:02d}.</b> {line}</div>',
        unsafe_allow_html=True,
    )

st.divider()
st.download_button(
    "⬇️ Download cleaned dataset (CSV)",
    data=df.to_csv(index=False).encode("utf-8-sig"),
    file_name="defra_emission_factors_clean.csv",
    mime="text/csv",
    width="stretch",
)
