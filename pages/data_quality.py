"""DATA QUALITY page - transparency on cleaning results and anomalies."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ui import eyebrow, get_data

st.title("✅ Data Quality")
st.caption("A transparent view of how the raw DEFRA export was validated and cleaned.")

df, metrics = get_data()

# --- Dataset dimensions & source ------------------------------------------ #
eyebrow("Dataset dimensions & source")
d1, d2, d3, d4 = st.columns(4)
d1.metric("Rows", f"{len(df):,}")
d2.metric("Columns", f"{df.shape[1]:,}")
d3.metric("Duplicate keys", metrics.get("duplicate_keys", 0))
d4.metric("Exact duplicates", metrics.get("duplicates_removed", 0))

sources = df["source_id"].value_counts()
retrieved = pd.to_datetime(df["retrieved"], errors="coerce")
updated = pd.to_datetime(df["updated"], errors="coerce")
r1, r2, r3 = st.columns(3)
r1.metric("Source(s)", ", ".join(sources.index.tolist()))
r2.metric("Retrieved", f"{retrieved.min():%Y-%m-%d} → {retrieved.max():%Y-%m-%d}")
r3.metric("Updated", f"{updated.min():%Y-%m-%d} → {updated.max():%Y-%m-%d}")

st.divider()

# --- Missing values -------------------------------------------------------- #
eyebrow("Missing values")
src_cols = ["key", "name", "value", "unit", "gas", "gwp_set", "ghg_scope",
            "ghg_category", "source_id", "source_ref", "retrieved", "note", "updated"]
missing = (
    df[src_cols].isna().sum().rename("missing_count").to_frame()
    .assign(missing_pct=lambda t: (t["missing_count"] / len(df) * 100).round(2))
)
missing = missing[missing["missing_count"] > 0].sort_values("missing_count", ascending=False)

if missing.empty:
    st.success("No missing values in the source columns.")
else:
    st.dataframe(missing, width="stretch")
    st.info(
        f"`gwp_set` is null on {int(df['gwp_set'].isna().sum())} rows — these are the "
        "**biogenic-CO₂ memo** factors (scope `outside_scopes`), which are not GWP-weighted. "
        "This is a *structural* null by design, not a data defect, so it is preserved rather than imputed. "
        f"Unexpected `gwp_set` nulls: **{metrics.get('gwp_set_missing_unexpected', 0)}**.",
        icon="🧬",
    )
    st.info("`note` is an optional provenance field; blanks are expected and left untouched.", icon="📝")

st.divider()

# --- Data types ------------------------------------------------------------ #
eyebrow("Data types")
dtypes = df[src_cols].dtypes.astype(str).rename("dtype").to_frame()
st.dataframe(dtypes, width="stretch")

st.divider()

# --- Invalid values -------------------------------------------------------- #
eyebrow("Invalid values")
invalid_count = metrics.get("invalid_values", 0)
if invalid_count == 0:
    st.success("All `value` entries parsed cleanly as positive numbers — no non-numeric or null factors.")
else:
    bad = df[df.get("value_invalid", pd.Series(False, index=df.index))]
    st.warning(f"{invalid_count} value(s) could not be parsed as numeric.")
    st.dataframe(bad[["key", "value", "unit"]], width="stretch")

# Non-positive magnitude scan (should be none in this dataset)
val = pd.to_numeric(df["value"], errors="coerce")
st.caption(
    f"Zero values: **{int((val == 0).sum())}** · Negative values: **{int((val < 0).sum())}** · "
    f"Null values: **{int(val.isna().sum())}**"
)

st.divider()

# --- Suspicious / outlier records ----------------------------------------- #
eyebrow("Suspicious records (flagged, never removed)")
st.markdown(
    "DEFRA legitimately publishes factors spanning several orders of magnitude, so large values are "
    "**not** removed. A scale-aware detector (robust z-score on log value + Tukey fence, computed *within* "
    "each activity unit) flags records for human review."
)
susp_count = int(df.get("outlier_flag", pd.Series(False, index=df.index)).sum())
st.metric("Flagged for review", susp_count)

if susp_count:
    susp = df.loc[df["outlier_flag"], ["name", "value", "unit", "ghg_category", "outlier_reason"]]
    st.dataframe(
        susp,
        width="stretch",
        hide_index=True,
        height=360,
        column_config={"value": st.column_config.NumberColumn(format="%.4f")},
    )
    st.download_button(
        "⬇️ Download suspicious records (CSV)",
        data=susp.to_csv(index=False).encode("utf-8-sig"),
        file_name="defra_suspicious_records.csv",
        mime="text/csv",
    )

st.divider()
st.download_button(
    "⬇️ Download full cleaned dataset (CSV)",
    data=df.to_csv(index=False).encode("utf-8-sig"),
    file_name="defra_emission_factors_clean.csv",
    mime="text/csv",
)
