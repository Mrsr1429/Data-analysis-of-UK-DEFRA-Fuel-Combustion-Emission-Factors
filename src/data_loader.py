"""Pure data-loading utilities (framework-free, unit-testable).

Responsibilities
----------------
* Locate the immutable raw DEFRA CSV that was uploaded to the workspace.
* Load it without ever mutating the file.
* Load the cleaned CSV, transparently building it from the raw source the
  first time the project is run.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------- #
# Path resolution
# --------------------------------------------------------------------------- #
# This file lives in  <workspace>/defra-emission-dashboard/src/data_loader.py
PKG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PKG_DIR.parent                       # .../defra-emission-dashboard
WORKSPACE_ROOT = PROJECT_ROOT.parent                # .../UK DEFRA ... analysis

DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"

# The uploaded source of truth (never written to).
RAW_CSV_CANDIDATES = [
    WORKSPACE_ROOT / "defra-emission-factors.csv",
    PROJECT_ROOT / "defra-emission-factors.csv",
    DATA_DIR / "defra-emission-factors.csv",
]
# The cleaned artefact produced by this pipeline.
CLEAN_CSV = DATA_DIR / "defra_emission_factors_clean.csv"

# Canonical column schema we expect from DEFRA.
EXPECTED_COLUMNS = [
    "key", "name", "value", "unit", "gas", "gwp_set", "ghg_scope",
    "ghg_category", "source_id", "source_ref", "retrieved", "note", "updated",
]


def find_raw_csv() -> Path:
    """Return the first existing raw CSV path, raising a helpful error if none."""
    for path in RAW_CSV_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Could not locate the raw DEFRA CSV. Searched:\n  "
        + "\n  ".join(str(p) for p in RAW_CSV_CANDIDATES)
    )


def load_raw(path: Path | None = None) -> pd.DataFrame:
    """Load the raw DEFRA CSV as strings-safe frame (file is never modified)."""
    path = path or find_raw_csv()
    # utf-8-sig transparently strips a leading BOM if present.
    df = pd.read_csv(path, encoding="utf-8-sig")
    return df


def load_clean() -> pd.DataFrame:
    """Load the cleaned CSV. Assumes it already exists (see build_clean_csv)."""
    if not CLEAN_CSV.exists():
        raise FileNotFoundError(
            f"Cleaned dataset not found at {CLEAN_CSV}. "
            "Run scripts/build_clean_dataset.py first."
        )
    return pd.read_csv(CLEAN_CSV, encoding="utf-8-sig")


def load_clean_or_build() -> tuple[pd.DataFrame, dict]:
    """Return (df_clean, metrics), building the cleaned CSV on first run.

    Deferred import of the cleaning module keeps this loader import-clean and
    avoids any circular dependency.
    """
    from src.data_cleaning import clean, save_clean  # local import

    if CLEAN_CSV.exists():
        df = load_clean()
        # Recompute metrics cheaply from the cleaned frame for the DQ page.
        from src.data_cleaning import compute_metrics_from_clean

        metrics = compute_metrics_from_clean(df)
        return df, metrics

    raw = load_raw()
    df_clean, metrics = clean(raw)
    save_clean(df_clean)
    return df_clean, metrics
