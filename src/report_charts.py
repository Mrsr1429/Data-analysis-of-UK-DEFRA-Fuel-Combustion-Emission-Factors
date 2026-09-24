"""Matplotlib chart builders for the Word report.

Matplotlib (not Plotly) is used here so figures can be embedded as static PNGs
without a JavaScript/Kaleido dependency. All data comes from the cleaned frame.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless backend
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.data_loader import REPORTS_DIR  # noqa: E402

FIG_DIR = REPORTS_DIR / "figs"

# Professional, consistent palette.
PALETTE = ["#1f5c99", "#4c9be8", "#2f7d32", "#f0a202", "#c1440e", "#7b2cbf",
           "#0e7c7b", "#d62828", "#5f6caf", "#8d99ae", "#bc6c25"]

plt.rcParams.update({
    "figure.dpi": 130,
    "savefig.dpi": 130,
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
})


def _ensure_dir() -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    return FIG_DIR


def _finish(fig, name: str) -> Path:
    path = _ensure_dir() / name
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def bar_counts(df: pd.DataFrame, col: str, name: str, title: str) -> Path:
    vc = df[col].fillna("(none)").value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(7, 3.8))
    bars = ax.barh([str(i) for i in vc.index], vc.values,
                   color=PALETTE[: len(vc)][::-1] if len(vc) <= len(PALETTE) else "#4c9be8")
    ax.bar_label(bars, padding=3, fontsize=8)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel("Number of factors")
    ax.grid(axis="y", visible=False)
    return _finish(fig, name)


def gas_donut(df: pd.DataFrame) -> Path:
    vc = df["gas"].fillna("(none)").value_counts()
    fig, ax = plt.subplots(figsize=(5.2, 3.8))
    wedges, _texts, autotexts = ax.pie(
        vc.values, labels=[str(i) for i in vc.index], autopct="%1.0f%%",
        startangle=90, colors=PALETTE[: len(vc)],
        wedgeprops={"width": 0.42, "edgecolor": "white"},
    )
    for t in autotexts:
        t.set_color("black"); t.set_fontsize(9); t.set_fontweight("bold")
    ax.set_title("Share of factors by gas basis", fontsize=12, fontweight="bold")
    return _finish(fig, "gas_donut.png")


def unit_box(df: pd.DataFrame, unit: str) -> Path:
    sub = df[df["unit"] == unit]["value"].dropna()
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    box = ax.boxplot(sub, vert=False, widths=0.6, patch_artist=True,
                     medianprops={"color": "#c1440e", "linewidth": 2})
    box["boxes"][0].set_facecolor("#bfe0ff")
    # Overlay individual points (jittered) for transparency.
    ax.scatter(sub, [1] * len(sub), s=12, alpha=0.5, color="#1f5c99")
    ax.set_yticks([])
    ax.set_title(f"Distribution of factors — unit: {unit}", fontsize=12, fontweight="bold")
    ax.set_xlabel("Emission factor")
    ax.grid(axis="y", visible=False)
    return _finish(fig, "unit_box.png")


def top_factors(df: pd.DataFrame, n: int = 12) -> Path:
    top = df.sort_values("value", ascending=False).head(n).copy()
    top["label"] = top["name"].str.slice(0, 34) + "…"
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    bars = ax.barh(top["label"][::-1], top["value"][::-1], color="#1f5c99")
    ax.bar_label(bars, fmt="%.3g", padding=3, fontsize=7)
    ax.set_xscale("log")
    ax.set_title(f"Top {n} emission factors (log scale — different units)",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Emission factor (log scale — units differ!)")
    ax.grid(axis="y", visible=False)
    return _finish(fig, "top_factors.png")


def all_figures(df: pd.DataFrame) -> dict[str, Path]:
    """Generate the full set of report charts and return name->path map."""
    dom_unit = df["unit"].value_counts().index[0]
    return {
        "scope": bar_counts(df, "ghg_scope", "by_scope.png", "Factors by GHG scope"),
        "category": bar_counts(df, "ghg_category", "by_category.png", "Factors by GHG category"),
        "unit": bar_counts(df, "unit", "by_unit.png", "Factors by activity unit"),
        "gas": gas_donut(df),
        "box": unit_box(df, dom_unit),
        "top": top_factors(df),
    }
