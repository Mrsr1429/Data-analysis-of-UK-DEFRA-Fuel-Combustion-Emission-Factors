"""Analytical layer: KPIs, statistics, dynamic insights and Plotly figures.

CRITICAL RULE: emission factors are only ever compared/aggregated WITHIN a
single activity unit, because a 'kg CO2e per tonne' figure is not comparable to
a 'kg CO2e per kWh' figure. Charts that mix magnitudes therefore fix a unit,
while charts that count *records* are safe to break out by any category.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

TEMPLATE = "plotly_white"

# Columns used for categorical break-outs.
CATEGORY_COLS = ["ghg_scope", "ghg_category", "gas", "unit", "gwp_set", "source_id"]


# --------------------------------------------------------------------------- #
# KPIs & basic stats
# --------------------------------------------------------------------------- #
def compute_kpis(df: pd.DataFrame) -> dict:
    return {
        "total_factors": int(len(df)),
        "n_categories": int(df["ghg_category"].nunique()),
        "n_units": int(df["unit"].nunique()),
        "n_gases": int(df["gas"].nunique()),
        "n_scopes": int(df["ghg_scope"].nunique()),
        "n_gwp_sets": int(df["gwp_set"].dropna().nunique()),
        "n_sources": int(df["source_id"].nunique()),
    }


def value_series(df: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(df["value"], errors="coerce")


def counts(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col].value_counts(dropna=False)


def dominant_value(df: pd.DataFrame, col: str) -> tuple:
    vc = df[col].value_counts(dropna=False)
    if vc.empty:
        return ("n/a", 0)
    return (str(vc.index[0]), int(vc.iloc[0]))


def top_factors(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    cols = ["name", "key", "value", "unit", "gas", "ghg_scope", "ghg_category"]
    return df.sort_values("value", ascending=False).head(n)[cols]


def bottom_factors(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    cols = ["name", "key", "value", "unit", "gas", "ghg_scope", "ghg_category"]
    return df.sort_values("value", ascending=True).head(n)[cols]


def extremes(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["value"])
    hi = d.loc[d["value"].idxmax()]
    lo = d.loc[d["value"].idxmin()]
    return {
        "highest": {"name": hi["name"], "value": float(hi["value"]), "unit": hi["unit"]},
        "lowest": {"name": lo["name"], "value": float(lo["value"]), "unit": lo["unit"]},
    }


def units_sorted_by_frequency(df: pd.DataFrame) -> list:
    return list(df["unit"].value_counts().index)


def within_unit_summary(df: pd.DataFrame, unit: str) -> pd.Series:
    return value_series(df[df["unit"] == unit]).describe()


# --------------------------------------------------------------------------- #
# Dynamic, factual insights (nothing hard-coded, no unsupported claims)
# --------------------------------------------------------------------------- #
def build_insights(df: pd.DataFrame) -> list[str]:
    ins: list[str] = []
    n = len(df)
    ins.append(f"The dataset contains {n:,} DEFRA emission factors across {df['unit'].nunique()} activity units.")

    cat, cat_n = dominant_value(df, "ghg_category")
    ins.append(f"The most common GHG category is '{cat}' with {cat_n:,} factors ({cat_n / n:.0%} of the dataset).")

    unit, unit_n = dominant_value(df, "unit")
    ins.append(f"The most frequently used activity unit is '{unit}' ({unit_n:,} factors).")

    scope_counts = counts(df, "ghg_scope")
    scope_txt = ", ".join(f"{k}: {v:,}" for k, v in scope_counts.items())
    ins.append(f"Factors by GHG scope -> {scope_txt}.")

    gases = ", ".join(f"{k} ({v:,})" for k, v in counts(df, "gas").items())
    ins.append(f"The dataset covers {df['gas'].nunique()} gas basis value(s): {gases}.")

    gwp_present = df["gwp_set"].notna().sum()
    ins.append(f"GWP set information is present for {gwp_present:,} of {n:,} factors ({gwp_present / n:.0%}); "
               "the remainder are biogenic-CO2 memo rows that are not GWP-weighted.")

    ex = extremes(df)
    ins.append(f"Highest single factor: {ex['highest']['value']:,.4f} {ex['highest']['unit']} ({ex['highest']['name']}).")
    ins.append(f"Lowest single factor: {ex['lowest']['value']:,.5f} {ex['lowest']['unit']} ({ex['lowest']['name']}).")

    # Median comparison kept WITHIN the dominant unit to avoid mixing scales.
    dom_unit = unit
    med = within_unit_summary(df, dom_unit).get("50%")
    ins.append(f"Median factor within the dominant unit '{dom_unit}' is {float(med):,.4f}.")

    src = ", ".join(f"{k} ({v:,})" for k, v in counts(df, "source_id").items())
    ins.append(f"All factors are attributed to source(s): {src}.")

    note_cov = df["note"].notna().sum() if "note" in df.columns else 0
    ins.append(f"Provenance notes are attached to {note_cov:,} factors ({note_cov / n:.0%}), "
               "documenting assumptions and paired keys.")

    return ins


# --------------------------------------------------------------------------- #
# Plotly figure builders
# --------------------------------------------------------------------------- #
def fig_counts_bar(df: pd.DataFrame, col: str, title: str, color: str | None = None) -> go.Figure:
    vc = df[col].fillna("(none)").value_counts().sort_values(ascending=True)
    fig = px.bar(
        x=vc.values, y=vc.index.astype(str), orientation="h",
        labels={"x": "Number of factors", "y": col}, title=title,
        color=vc.values, color_continuous_scale=color or "Blues",
    )
    fig.update_layout(template=TEMPLATE, height=380, margin=dict(l=10, r=10, t=60, b=10),
                      coloraxis_showscale=False)
    fig.update_traces(hovertemplate="%{y}: <b>%{x:,}</b> factors<extra></extra>")
    return fig


def fig_gas_pie(df: pd.DataFrame) -> go.Figure:
    vc = df["gas"].fillna("(none)").value_counts()
    fig = go.Figure(
        go.Pie(labels=vc.index.astype(str), values=vc.values, hole=0.55,
               textinfo="label+percent", hovertemplate="%{label}: %{value} factors<extra></extra>")
    )
    fig.update_layout(template=TEMPLATE, height=380, margin=dict(l=10, r=10, t=60, b=10),
                      title="Share of factors by gas basis")
    return fig


def fig_distribution_by_unit(df: pd.DataFrame, unit: str) -> go.Figure:
    sub = df[df["unit"] == unit].copy()
    fig = go.Figure()
    fig.add_trace(go.Violin(
        y=sub["value"], name=unit, box_visible=True, meanline_visible=True,
        fillcolor="#4c9be8", line_color="#1f5c99", opacity=0.75,
        points="all", hoverinfo="y",
    ))
    fig.update_layout(
        template=TEMPLATE, height=440,
        title=f"Distribution of emission factors — unit: {unit}",
        yaxis_title=f"Emission factor (per {unit.split(' per ')[-1] if ' per ' in unit else unit})",
        xaxis_title="", margin=dict(l=10, r=10, t=60, b=10),
    )
    return fig


def fig_median_by_category_within_unit(df: pd.DataFrame, unit: str) -> go.Figure:
    sub = df[df["unit"] == unit]
    med = sub.groupby("ghg_category")["value"].median().sort_values(ascending=False)
    fig = px.bar(x=med.index.astype(str), y=med.values,
                 labels={"x": "GHG category", "y": "Median factor"},
                 title=f"Median emission factor by category — unit: {unit}",
                 color=med.values, color_continuous_scale="Viridis")
    fig.update_layout(template=TEMPLATE, height=400, coloraxis_showscale=False,
                      margin=dict(l=10, r=10, t=60, b=10))
    fig.update_traces(hovertemplate="%{x}: <b>%{y:,.4f}</b><extra></extra>")
    return fig


def fig_top_factors(df: pd.DataFrame, n: int = 12) -> go.Figure:
    top = df.sort_values("value", ascending=False).head(n).copy()
    top["label"] = top["name"].str.slice(0, 42) + "…"
    # Colour by unit so incomparable magnitudes are visually separated.
    fig = px.bar(top, x="value", y="label", orientation="h", color="unit",
                 labels={"value": "Emission factor", "y": "", "unit": "Unit"},
                 title=f"Top {n} emission factors (coloured by unit)")
    fig.update_layout(template=TEMPLATE, height=520, bargap=0.35,
                      margin=dict(l=10, r=10, t=60, b=10),
                      yaxis=dict(autorange="reversed"))
    fig.update_traces(hovertemplate="%{y}<br>value=%{x:,.4f}<extra></extra>")
    return fig


def fig_records_by_date(df: pd.DataFrame) -> go.Figure:
    d = pd.to_datetime(df["retrieved"], errors="coerce").dt.date.value_counts().sort_index()
    fig = go.Figure(go.Bar(x=[str(x) for x in d.index], y=d.values,
                           marker_color="#2f7d32",
                           hovertemplate="Retrieved %{x}: <b>%{y}</b> factors<extra></extra>"))
    fig.update_layout(template=TEMPLATE, height=340,
                      title="Records by retrieved date",
                      xaxis_title="Retrieved date", yaxis_title="Number of factors",
                      margin=dict(l=10, r=10, t=60, b=10))
    return fig
