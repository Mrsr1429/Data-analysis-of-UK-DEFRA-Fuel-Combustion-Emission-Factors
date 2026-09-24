"""Automated checks for the DEFRA dashboard pipeline.

Run:  python -m tests.test_pipeline   (or)   python tests/test_pipeline.py
Uses plain asserts so it works without pytest, but is pytest-compatible.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import analysis
from src.calculations import CalculationError, calculate_emissions
from src.data_cleaning import clean
from src.data_loader import load_raw


def test_cleaning_pipeline():
    raw = load_raw()
    assert len(raw) == 221, f"expected 221 raw rows, got {len(raw)}"
    df, metrics = clean(raw)

    assert metrics["original_rows"] == len(raw)
    assert metrics["cleaned_rows"] == len(df)
    assert metrics["duplicates_removed"] == 0
    assert metrics["duplicate_keys"] == 0
    assert metrics["invalid_values"] == 0
    assert metrics["core_missing_after_cleaning"] == 0
    assert df["value"].gt(0).all(), "all values must be strictly positive"
    assert df["key"].is_unique
    # original raw frame untouched
    assert len(raw) == 221 and list(raw.columns)[:3] == ["key", "name", "value"]
    print("[ok] cleaning pipeline")


def test_example_calculation():
    # Activity = 100, factor = 2.33116 kg CO2e/litre
    r = calculate_emissions(
        100, 2.33116,
        factor_name="UK Aviation spirit — combustion (litres)",
        factor_key="fuels.gbr.aviation_spirit.litre",
        factor_unit="kg CO2e per litre",
        activity_unit="litre",
    )
    assert abs(r.kg_co2e - 233.116) < 1e-9, r.kg_co2e
    assert abs(r.tonnes_co2e - 0.233116) < 1e-9, r.tonnes_co2e
    print("[ok] example calculation -> 233.116 kg / 0.233116 t")


def test_validation_rejections():
    for bad_amount in (-5, "abc", None):
        try:
            calculate_emissions(bad_amount, 2.0, factor_unit="kg CO2e per litre", activity_unit="litre")
            raise AssertionError(f"should have rejected amount={bad_amount!r}")
        except CalculationError:
            pass
    # zero / negative factor
    try:
        calculate_emissions(10, 0, factor_unit="kg CO2e per litre", activity_unit="litre")
        raise AssertionError("zero factor should be rejected")
    except CalculationError:
        pass
    # incompatible unit
    try:
        calculate_emissions(10, 2.0, factor_unit="kg CO2e per litre", activity_unit="tonne")
        raise AssertionError("incompatible unit should be rejected")
    except CalculationError:
        pass
    print("[ok] invalid inputs rejected")


def test_insights_and_kpis():
    df, _ = clean(load_raw())
    insights = analysis.build_insights(df)
    assert len(insights) >= 10, len(insights)
    assert all(isinstance(s, str) and s for s in insights)
    kpi = analysis.compute_kpis(df)
    assert kpi["total_factors"] == len(df)
    print(f"[ok] {len(insights)} dynamic insights generated")


def test_chart_builders():
    import plotly.graph_objects as go
    df, _ = clean(load_raw())
    unit = analysis.units_sorted_by_frequency(df)[0]
    figs = [
        analysis.fig_counts_bar(df, "ghg_scope", "t"),
        analysis.fig_gas_pie(df),
        analysis.fig_distribution_by_unit(df, unit),
        analysis.fig_median_by_category_within_unit(df, unit),
        analysis.fig_top_factors(df),
        analysis.fig_records_by_date(df),
    ]
    assert all(isinstance(f, go.Figure) for f in figs)
    print(f"[ok] {len(figs)} Plotly figures built")


def run_all():
    test_cleaning_pipeline()
    test_example_calculation()
    test_validation_rejections()
    test_insights_and_kpis()
    test_chart_builders()
    print("\nALL TESTS PASSED ✅")


if __name__ == "__main__":
    run_all()
