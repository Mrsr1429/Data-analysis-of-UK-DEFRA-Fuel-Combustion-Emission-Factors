"""Shared Streamlit UI helpers: page config, CSS, KPI cards, cached data loader.

Centralising these keeps the individual page scripts short and consistent and
avoids duplicated styling/formatting logic.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

# --------------------------------------------------------------------------- #
# Page chrome
# --------------------------------------------------------------------------- #
PAGE_TITLE = "UK DEFRA Emission Factor Explorer & Carbon Calculator"
PAGE_ICON = "🌍"


def configure_page() -> None:
    """Set the single global page config (must run before other st calls)."""
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_css() -> None:
    """Inject a light, professional style layer."""
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: 1300px;}
        h1 {font-size: 2.05rem; font-weight: 800; letter-spacing: -0.5px;}
        h2, h3 {font-weight: 700; letter-spacing: -0.3px;}
        div[data-testid="stMetric"] {
            background: linear-gradient(180deg,#ffffff,#f4f8ff);
            border: 1px solid #e3e9f2; border-radius: 14px;
            padding: 14px 16px; box-shadow: 0 1px 3px rgba(16,24,40,0.06);
        }
        div[data-testid="stMetricValue"] {font-size: 1.6rem; font-weight: 800;}
        .section-tag {
            display:inline-block; font-size:.72rem; font-weight:700; text-transform:uppercase;
            letter-spacing:.7px; color:#1f5c99; background:#eaf2ff;
            padding:3px 10px; border-radius:999px; margin-bottom:.2rem;
        }
        .insight-card {
            background:#f8fbff; border-left:4px solid #2f7d32; border-radius:8px;
            padding:10px 14px; margin-bottom:8px; font-size:.94rem; color:#1f2937;
        }
        .formula {
            background:#0f172a; color:#e2e8f0; border-radius:10px; padding:14px 18px;
            font-family:'JetBrains Mono',ui-monospace,monospace; font-size:1.02rem; margin:.4rem 0;
        }
        footer {visibility: hidden;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def eyebrow(text: str) -> None:
    st.markdown(f'<span class="section-tag">{text}</span>', unsafe_allow_html=True)


def kpi_row(cards: list[dict]) -> None:
    """Render a responsive row of KPI cards using native st.metric."""
    if not cards:
        return
    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        col.metric(label=card["label"], value=card["value"], help=card.get("help"))


def fmt(num: float, digits: int = 4) -> str:
    """Readable thousands-separated number."""
    try:
        return f"{float(num):,.{digits}f}"
    except (TypeError, ValueError):
        return str(num)


# --------------------------------------------------------------------------- #
# Cached data access
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Loading & validating DEFRA dataset…")
def get_data() -> tuple[pd.DataFrame, dict]:
    """Return (df_clean, metrics). The cleaned CSV is auto-built on first run."""
    from src.data_loader import load_clean_or_build

    df, metrics = load_clean_or_build()
    # Ensure dates are real datetimes for downstream charts regardless of source.
    for c in ("retrieved", "updated"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", format="mixed")
    return df, metrics
