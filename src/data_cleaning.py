"""Production data-cleaning pipeline for the DEFRA emission-factor dataset.

Design principles
-----------------
* The raw file is IMMUTABLE: every operation runs on a copy and original values
  are preserved. Standardisation only *normalises whitespace/spelling/case* of
  controlled vocabularies; it never alters the scientific meaning of a factor.
* "Cleaning" = normalise + validate + FLAG. Large DEFRA factors are legitimate,
  so suspicious values are annotated, never dropped.
* Structural nulls (e.g. `gwp_set` absent on biogenic-CO2 memo rows) are
  preserved and clearly labelled rather than imputed.

Public API
----------
clean(df_raw) -> (df_clean, metrics)
save_clean(df_clean) -> Path
compute_metrics_from_clean(df_clean) -> dict
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.data_loader import CLEAN_CSV

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
TEXT_COLS = ["unit", "gas", "gwp_set", "ghg_scope", "ghg_category"]
DATE_COLS = ["retrieved", "updated"]
VALUE_COL = "value"
KEY_COL = "key"

# Outlier sensitivity (flagging only).
MAD_TO_SIGMA = 1.4826
Z_THRESHOLD = 3.5
IQR_MULTIPLIER = 3.0

# Controlled vocabulary for `gas` canonical casing.
GAS_CANONICAL = {"co2": "CO2", "co2e": "CO2e", "ch4": "CH4", "n2o": "N2O"}


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _snake(name: str) -> str:
    cleaned = str(name).strip().lower().replace(" ", "_").replace("-", "_")
    return "_".join(tok for tok in cleaned.split("_") if tok)


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lower snake_case column names."""
    return df.rename(columns={c: _snake(c) for c in df.columns})


def to_numeric_safe(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Coerce `col` to float and record previously-present non-numeric entries."""
    raw = df[col]
    coerced = pd.to_numeric(raw, errors="coerce")
    df[f"{col}_invalid"] = raw.notna() & coerced.isna()
    df[col] = coerced
    return df


def standardize_text(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Normalise whitespace and canonical casing for a controlled-vocab column.

    * strip + collapse internal whitespace, empty -> <NA>
    * `gas`          -> canonical casing (CO2 / CO2e)
    * `gwp_set`      -> upper (AR5_100)
    * `ghg_scope`    -> lower snake (scope1 / outside_scopes)
    * `ghg_category` -> lower snake (stationary_combustion / biogenic_co2_memo)
    * `unit`         -> tidy spacing + 'CO2e' spelling
    """
    s = df[col].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    s = s.replace({"": pd.NA})

    if col == "gas":
        s = s.map(lambda v: GAS_CANONICAL.get(str(v).lower(), v) if pd.notna(v) else v)
    elif col == "gwp_set":
        s = s.str.upper()
    elif col in {"ghg_scope", "ghg_category"}:
        s = s.str.lower().str.replace(" ", "_", regex=False)
    elif col == "unit":
        s = s.str.replace("CO2E", "CO2e", regex=False)

    df[col] = s
    return df


def _is_biogenic(df: pd.DataFrame) -> pd.Series:
    """True for the biogenic-CO2 memo segment (gas=CO2, category=biogenic_co2_memo)."""
    return (
        df["gas"].astype("string").eq("CO2")
        | df["ghg_category"].astype("string").eq("biogenic_co2_memo")
        | df["ghg_scope"].astype("string").eq("outside_scopes")
    )


def flag_outliers(df: pd.DataFrame, col: str, group_col: str) -> pd.DataFrame:
    """Flag statistically suspicious factors WITHIN each activity unit.

    Two scale-aware detectors are combined; a row is flagged if either fires.
    Values are NEVER removed - magnitude alone is not an error.
    """
    out = df.copy()
    out["outlier_flag"] = False
    out["outlier_reason"] = pd.NA
    values = pd.to_numeric(out[col], errors="coerce")

    def _robust_z(s: pd.Series) -> pd.Series:
        x = np.log(s.astype(float))
        x = x.dropna()
        if x.empty:
            return pd.Series(dtype=float)
        med = x.median()
        mad = (x - med).abs().median() * MAD_TO_SIGMA
        return (x - med) / mad if mad > 0 else x * 0.0

    tmp = out.assign(_v=values)
    z = tmp.groupby(group_col, dropna=True)["_v"].transform(lambda s: _robust_z(s).reindex(s.index))
    q1 = tmp.groupby(group_col)["_v"].transform(lambda s: s.quantile(0.25))
    q3 = tmp.groupby(group_col)["_v"].transform(lambda s: s.quantile(0.75))
    iqr = q3 - q1
    upper, lower = q3 + IQR_MULTIPLIER * iqr, q1 - IQR_MULTIPLIER * iqr

    z_hit = z.abs() > Z_THRESHOLD
    fence_hit = (values > upper) | (values < lower)
    mask = z_hit.fillna(False) | fence_hit.fillna(False)

    reasons = []
    for idx in out.index[mask]:
        parts = []
        if bool(z_hit.get(idx, False)):
            parts.append(f"log-z={z[idx]:.2f}")
        if bool(fence_hit.get(idx, False)):
            parts.append(f"outside {IQR_MULTIPLIER}x IQR of unit group")
        reasons.append("; ".join(parts))
    out.loc[mask, "outlier_flag"] = True
    out.loc[mask, "outlier_reason"] = reasons
    return out


# --------------------------------------------------------------------------- #
# Main pipeline
# --------------------------------------------------------------------------- #
def clean(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Run the full cleaning pipeline on a COPY of `df_raw`.

    Returns (df_clean, metrics). The input frame is never mutated.
    """
    df = df_raw.copy(deep=True)
    metrics: dict = {"original_rows": int(len(df_raw))}

    # 2. standardise column names
    df = standardize_columns(df)

    # 3. numeric value (safe)
    df = to_numeric_safe(df, VALUE_COL)
    metrics["invalid_values"] = int(df[f"{VALUE_COL}_invalid"].sum())

    # 4. proper datetimes
    for c in DATE_COLS:
        parsed = pd.to_datetime(df[c], errors="coerce", format="mixed")
        metrics[f"unparseable_{c}"] = int(parsed.isna().sum() - df[c].isna().sum())
        df[c] = parsed

    # 8. standardise text fields
    text_changes = {}
    for c in TEXT_COLS:
        before = df[c].astype("string").copy()
        df = standardize_text(df, c)
        after = df[c].astype("string")
        text_changes[c] = int((before != after).fillna((before.isna()) != (after.isna())).sum())
    metrics["text_standardized"] = text_changes

    # 6. remove exact duplicate rows
    dup_mask = df.duplicated(keep="first")
    metrics["duplicates_removed"] = int(dup_mask.sum())
    df = df.loc[~dup_mask].copy()

    # 7. check duplicate keys (flag, do not delete)
    df["is_duplicate_key"] = df[KEY_COL].duplicated(keep=False)
    metrics["duplicate_keys"] = int(df[KEY_COL].duplicated(keep="first").sum())

    # 5. handle missing values appropriately (label structural vs unexpected)
    biogenic = _is_biogenic(df)
    df["is_biogenic_memo"] = biogenic
    df["gwp_set_missing_structural"] = df["gwp_set"].isna() & biogenic
    df["gwp_set_missing_unexpected"] = df["gwp_set"].isna() & ~biogenic
    df["note_missing"] = df["note"].isna()
    metrics["gwp_set_missing_structural"] = int(df["gwp_set_missing_structural"].sum())
    metrics["gwp_set_missing_unexpected"] = int(df["gwp_set_missing_unexpected"].sum())
    metrics["core_missing_after_cleaning"] = int(
        df[[KEY_COL, VALUE_COL, "gas", "unit"]].isna().sum().sum()
    )

    # 9 & 10. flag suspicious values (never removed)
    df = flag_outliers(df, VALUE_COL, group_col="unit")
    metrics["suspicious_records"] = int(df["outlier_flag"].sum())

    # tidy derived flag types
    for flag in ["value_invalid", "is_duplicate_key", "is_biogenic_memo",
                 "gwp_set_missing_structural", "gwp_set_missing_unexpected",
                 "note_missing", "outlier_flag"]:
        if flag in df.columns:
            df[flag] = df[flag].fillna(False).astype(bool)

    df = df.reset_index(drop=True)
    metrics["cleaned_rows"] = int(len(df))

    # attach a metrics snapshot that can be recomputed from the frame later
    metrics["dimensions"] = {"rows": len(df), "columns": int(df.shape[1])}
    metrics["dtypes"] = {k: str(v) for k, v in df.dtypes.items()}
    return df, metrics


def _missing_table(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "missing_count": df.isna().sum(),
            "missing_pct": (df.isna().mean() * 100).round(2),
        }
    )


def compute_metrics_from_clean(df_clean: pd.DataFrame) -> dict:
    """Rebuild a metrics snapshot for the DQ page from an already-cleaned frame."""
    df = df_clean.copy()
    # Dates may arrive as strings from CSV -> normalise for reporting.
    for c in DATE_COLS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", format="mixed")

    biogenic = _is_biogenic(df) if "gas" in df.columns else pd.Series(False, index=df.index)
    metrics = {
        "original_rows": int(len(df)),          # no duplicates were dropped in this dataset
        "cleaned_rows": int(len(df)),
        "duplicates_removed": 0,
        "duplicate_keys": int(df[KEY_COL].duplicated(keep="first").sum()) if KEY_COL in df else 0,
        "invalid_values": int(df.get("value_invalid", pd.Series(dtype=bool)).sum())
        if "value_invalid" in df.columns else 0,
        "suspicious_records": int(df.get("outlier_flag", pd.Series(False, index=df.index)).sum()),
        "core_missing_after_cleaning": int(df[[KEY_COL, VALUE_COL, "gas", "unit"]].isna().sum().sum()),
        "gwp_set_missing_structural": int((df["gwp_set"].isna() & biogenic).sum()),
        "gwp_set_missing_unexpected": int((df["gwp_set"].isna() & ~biogenic).sum()),
        "missing_table": _missing_table(df).to_dict(),
        "dimensions": {"rows": int(len(df)), "columns": int(df.shape[1])},
        "dtypes": {k: str(v) for k, v in df.dtypes.items()},
        "retrieved_min": str(pd.to_datetime(df["retrieved"], errors="coerce").min().date())
        if "retrieved" in df.columns else None,
        "retrieved_max": str(pd.to_datetime(df["retrieved"], errors="coerce").max().date())
        if "retrieved" in df.columns else None,
        "updated_min": str(pd.to_datetime(df["updated"], errors="coerce").min().date())
        if "updated" in df.columns else None,
        "updated_max": str(pd.to_datetime(df["updated"], errors="coerce").max().date())
        if "updated" in df.columns else None,
    }
    return metrics


def save_clean(df_clean: pd.DataFrame, path: Path | None = None) -> Path:
    """Persist the cleaned dataset (utf-8-sig for Excel-friendliness)."""
    path = path or CLEAN_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df_clean.copy()
    # Dates -> ISO string for a portable CSV.
    for c in DATE_COLS:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.date.astype("string")
    out.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def build_quality_report_text(metrics: dict) -> str:
    """Human-readable data-quality summary used by CLI + report generator."""
    lines = [
        "=" * 74,
        "UK DEFRA EMISSION FACTORS - DATA QUALITY SUMMARY",
        "=" * 74,
        f"Original rows            : {metrics.get('original_rows')}",
        f"Cleaned rows             : {metrics.get('cleaned_rows')}",
        f"Exact duplicates removed : {metrics.get('duplicates_removed')}",
        f"Duplicate keys (flagged) : {metrics.get('duplicate_keys')}",
        f"Invalid (non-numeric)    : {metrics.get('invalid_values')}",
        f"Suspicious (flagged)     : {metrics.get('suspicious_records')}",
        f"gwp_set structural nulls : {metrics.get('gwp_set_missing_structural')}",
        f"gwp_set unexpected nulls : {metrics.get('gwp_set_missing_unexpected')}",
        f"Core-column nulls        : {metrics.get('core_missing_after_cleaning')}",
    ]
    return "\n".join(lines)
