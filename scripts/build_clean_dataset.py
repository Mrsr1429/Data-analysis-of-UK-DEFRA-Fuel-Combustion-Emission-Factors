"""CLI: build the cleaned dataset artefact from the raw DEFRA CSV.

Usage:  python scripts/build_clean_dataset.py
Writes: data/defra_emission_factors_clean.csv  and prints a quality summary.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is importable when run as a script.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_cleaning import build_quality_report_text, clean, save_clean  # noqa: E402
from src.data_loader import load_raw  # noqa: E402


def main() -> None:
    raw = load_raw()
    df_clean, metrics = clean(raw)
    out_path = save_clean(df_clean)
    print(build_quality_report_text(metrics))
    print(f"\nMissing-value table:")
    miss = df_clean.isna().sum()
    print(miss[miss > 0].to_string())
    print(f"\nSaved cleaned dataset -> {out_path}")


if __name__ == "__main__":
    main()
