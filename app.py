"""Streamlit entry point - UK DEFRA Emission Factor Explorer & Carbon Calculator.

Uses the modern `st.navigation` API for a clean, ordered sidebar. Page chrome
(config + CSS) is applied once here; individual pages read the cached dataset.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable no matter the launch directory.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from src.ui import configure_page, inject_css

configure_page()
inject_css()

# Warm the data cache so the first navigation feels instant.
from src.ui import get_data  # noqa: E402
try:
    get_data()
except Exception as exc:  # surface a friendly message instead of a stack trace
    st.error(f"Unable to load the DEFRA dataset: {exc}")
    st.stop()

PAGES = st.navigation(
    [
        st.Page("pages/overview.py", title="Overview", icon="📊", default=True),
        st.Page("pages/explorer.py", title="Emission Factor Explorer", icon="🔎"),
        st.Page("pages/calculator.py", title="Carbon Calculator", icon="🧮"),
        st.Page("pages/data_quality.py", title="Data Quality", icon="✅"),
    ]
)

PAGES.run()
