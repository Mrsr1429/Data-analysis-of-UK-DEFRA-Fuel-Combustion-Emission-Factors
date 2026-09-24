"""CARBON CALCULATOR - convert an activity amount into CO2e using a chosen factor."""

from __future__ import annotations

import streamlit as st

from src.calculations import CalculationError, calculate_emissions, emissions_to_csv_bytes
from src.ui import eyebrow, fmt, get_data

st.title("🧮 Carbon Calculator")
st.caption("Pick a DEFRA emission factor, enter your activity amount, and get CO2e instantly.")

df, _ = get_data()

eyebrow("Step 1 · Choose an emission factor")
# Build a readable, unique label per factor (name + key disambiguates duplicates).
labels = [f"{r['name']}  ·  {r['unit']}  ·  {r['key']}" for _, r in df.iterrows()]
label_to_idx = dict(zip(labels, df.index.tolist()))

choice = st.selectbox("Emission factor", labels, index=0)
row = df.loc[label_to_idx[choice]]

# --- Factor detail card ---------------------------------------------------- #
c1, c2, c3, c4 = st.columns(4)
c1.metric("Value", fmt(row["value"]))
c2.metric("Gas", str(row["gas"]))
c3.metric("Scope", str(row["ghg_scope"]))
c4.metric("Category", str(row["ghg_category"]))
st.caption(f"**Unit:** {row['unit']}  ·  **Source:** {row['source_id']} ({row['source_ref']})")
if st.toggle("Show full name & key"):
    st.write(row["name"])
    st.code(str(row["key"]), language=None)

st.divider()
eyebrow("Step 2 · Enter activity amount")

required_unit = str(row["unit"]).split(" per ")[-1]

form_col, calc_col = st.columns([2, 1])
with form_col:
    amount = st.number_input(
        f"Activity amount (in **{required_unit}**)",
        min_value=0.0, value=100.0, step=1.0, format="%.4f",
        help=f"The factor expects activity in '{required_unit}'. Other units are rejected.",
    )
    # Offer every known activity unit; choosing a wrong one demonstrates the guard.
    all_activity_units = sorted({str(u).split(" per ")[-1] for u in df["unit"].dropna().unique()})
    activity_unit = st.selectbox(
        "Activity unit", all_activity_units,
        index=all_activity_units.index(required_unit) if required_unit in all_activity_units else 0,
    )

with calc_col:
    st.write("")
    st.write("")
    run = st.button("Calculate", type="primary", width="stretch")

st.markdown(
    '<div class="formula">Emissions (kg CO2e) = Activity Amount × Emission Factor&nbsp;&nbsp;|&nbsp;&nbsp;'
    "tonnes CO2e = kg CO2e ÷ 1000</div>",
    unsafe_allow_html=True,
)

if run:
    try:
        result = calculate_emissions(
            amount,
            row["value"],
            factor_name=str(row["name"]),
            factor_key=str(row["key"]),
            factor_unit=str(row["unit"]),
            activity_unit=activity_unit,
            gas=str(row["gas"]),
            ghg_scope=str(row["ghg_scope"]),
            ghg_category=str(row["ghg_category"]),
        )
    except CalculationError as exc:
        st.error(f"⛔ {exc}")
    else:
        st.success("Calculation complete.")
        m1, m2 = st.columns(2)
        m1.metric("Emissions (kg CO2e)", fmt(result.kg_co2e, 3))
        m2.metric("Emissions (tonnes CO2e)", fmt(result.tonnes_co2e, 6))

        st.markdown(
            f"**{result.activity_amount:,.4g} {result.activity_unit}** "
            f"× **{result.emission_factor:,.5f} {result.emission_factor_unit}** "
            f"= **{result.kg_co2e:,.3f} kg CO2e** "
            f"(**{result.tonnes_co2e:,.6f} t CO2e**)"
        )

        st.session_state["last_calc_csv"] = emissions_to_csv_bytes(result)

if "last_calc_csv" in st.session_state:
    st.download_button(
        "⬇️ Download calculation result (CSV)",
        data=st.session_state["last_calc_csv"],
        file_name="defra_calculation_result.csv",
        mime="text/csv",
    )
