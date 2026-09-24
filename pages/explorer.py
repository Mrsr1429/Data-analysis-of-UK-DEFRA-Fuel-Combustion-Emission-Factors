"""EMISSION FACTOR EXPLORER - search, filter, inspect and download factors."""

from __future__ import annotations

import streamlit as st

from src.ui import eyebrow, get_data

st.title("🔎 Emission Factor Explorer")
st.caption("Search and filter the full catalogue of DEFRA fuel-combustion emission factors.")

df, _ = get_data()

DISPLAY_COLS = ["name", "value", "unit", "gas", "ghg_scope", "ghg_category", "source_id", "key"]

eyebrow("Filters")
search = st.text_input("🔍 Search by name or key", placeholder="e.g. aviation turbine fuel …")

f1, f2, f3, f4, f5 = st.columns(5)
with f1:
    scope = st.multiselect("GHG scope", sorted(df["ghg_scope"].dropna().unique().tolist()))
with f2:
    category = st.multiselect("GHG category", sorted(df["ghg_category"].dropna().unique().tolist()))
with f3:
    gas = st.multiselect("Gas", sorted(df["gas"].dropna().unique().tolist()))
with f4:
    gwp = st.multiselect("GWP set", sorted(df["gwp_set"].dropna().unique().tolist()))
with f5:
    unit = st.multiselect("Unit", sorted(df["unit"].dropna().unique().tolist()))

filtered = df.copy()

if search:
    needle = search.strip().lower()
    mask = filtered["name"].str.lower().str.contains(needle, na=False) | \
        filtered["key"].str.lower().str.contains(needle, na=False)
    filtered = filtered[mask]
if scope:
    filtered = filtered[filtered["ghg_scope"].isin(scope)]
if category:
    filtered = filtered[filtered["ghg_category"].isin(category)]
if gas:
    filtered = filtered[filtered["gas"].isin(gas)]
if gwp:
    filtered = filtered[filtered["gwp_set"].isin(gwp)]
if unit:
    filtered = filtered[filtered["unit"].isin(unit)]

st.write(
    f"Showing **{len(filtered):,}** of **{len(df):,}** emission factors."
)

if filtered.empty:
    st.warning("No emission factors match the current filters. Try widening your selection.")
else:
    view = filtered[DISPLAY_COLS].rename(
        columns={"ghg_scope": "scope", "ghg_category": "category", "source_id": "source"}
    )
    st.dataframe(
        view,
        width="stretch",
        hide_index=True,
        height=460,
        column_config={
            "value": st.column_config.NumberColumn("value", format="%.4f", help="kg CO2e (or CO2) per activity unit"),
            "name": st.column_config.TextColumn("name", width="large"),
        },
    )

    st.download_button(
        "⬇️ Download filtered dataset (CSV)",
        data=filtered.to_csv(index=False).encode("utf-8-sig"),
        file_name="defra_emission_factors_filtered.csv",
        mime="text/csv",
    )
