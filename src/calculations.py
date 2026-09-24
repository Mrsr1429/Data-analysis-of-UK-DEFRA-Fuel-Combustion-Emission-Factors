"""Carbon calculation logic - pure, dependency-free, and fully unit-testable.

Core methodology (unchanged, standards-based):

    Emissions (kg CO2e) = Activity Amount  x  Emission Factor (kg CO2e per unit)
    Emissions (t  CO2e) = Emissions (kg CO2e) / 1000

An activity amount is always expressed in the SAME unit that appears in the
emission factor's denominator (e.g. a factor of "kg CO2e per litre" requires the
user to supply litres). This is what lets us reject incompatible-unit calculations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

import pandas as pd

KG_PER_TONNE = 1000.0


class CalculationError(ValueError):
    """Raised when inputs are invalid or units are incompatible."""


# --------------------------------------------------------------------------- #
# Unit helpers
# --------------------------------------------------------------------------- #
def parse_unit_denominator(unit: str) -> str:
    """Return the activity (denominator) unit from a DEFRA factor string.

    'kg CO2e per litre' -> 'litre'
    'kg CO2 per GJ'     -> 'GJ'
    """
    if not unit or " per " not in str(unit):
        raise CalculationError(f"Unrecognised emission-factor unit format: {unit!r}")
    return str(unit).split(" per ", 1)[1].strip()


def parse_unit_numerator(unit: str) -> str:
    """Return the impact (numerator) unit, e.g. 'kg CO2e'."""
    if not unit or " per " not in str(unit):
        raise CalculationError(f"Unrecognised emission-factor unit format: {unit!r}")
    return str(unit).split(" per ", 1)[0].strip()


def are_units_compatible(factor_unit: str, activity_unit: str) -> bool:
    """Case/space-insensitive comparison of the activity unit to the denominator."""
    denom = parse_unit_denominator(factor_unit).lower().replace(" ", "")
    return activity_unit.lower().replace(" ", "") == denom


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #
@dataclass
class EmissionResult:
    factor_name: str
    factor_key: str
    activity_amount: float
    activity_unit: str
    emission_factor: float
    emission_factor_unit: str
    gas: str
    ghg_scope: str
    ghg_category: str
    kg_co2e: float
    tonnes_co2e: float
    calculated_at: str

    def as_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Calculation
# --------------------------------------------------------------------------- #
def calculate_emissions(
    activity_amount,
    emission_factor,
    *,
    factor_name: str = "",
    factor_key: str = "",
    factor_unit: str = "kg CO2e per unit",
    activity_unit: str | None = None,
    gas: str = "",
    ghg_scope: str = "",
    ghg_category: str = "",
) -> EmissionResult:
    """Validate inputs and compute CO2e emissions.

    Raises CalculationError on any of:
      * non-numeric / non-finite activity amount or factor
      * negative activity amount
      * zero or negative emission factor
      * activity unit that is incompatible with the factor's denominator
    """
    # --- activity amount validation -------------------------------------- #
    try:
        amount = float(activity_amount)
    except (TypeError, ValueError):
        raise CalculationError(f"Activity amount must be numeric, got {activity_amount!r}.")
    if pd.isna(amount):
        raise CalculationError("Activity amount must not be empty.")
    if amount < 0:
        raise CalculationError("Activity amount must not be negative.")

    # --- emission factor validation -------------------------------------- #
    try:
        factor = float(emission_factor)
    except (TypeError, ValueError):
        raise CalculationError(f"Emission factor must be numeric, got {emission_factor!r}.")
    if pd.isna(factor) or factor <= 0:
        raise CalculationError("Emission factor must be a positive number.")

    # --- unit-compatibility guard ---------------------------------------- #
    denom = parse_unit_denominator(factor_unit)
    effective_activity_unit = activity_unit or denom
    if not are_units_compatible(factor_unit, effective_activity_unit):
        raise CalculationError(
            f"Incompatible units: factor expects activity in '{denom}' "
            f"but '{effective_activity_unit}' was supplied."
        )

    kg_co2e = amount * factor
    tonnes_co2e = kg_co2e / KG_PER_TONNE

    return EmissionResult(
        factor_name=factor_name,
        factor_key=factor_key,
        activity_amount=amount,
        activity_unit=effective_activity_unit,
        emission_factor=factor,
        emission_factor_unit=factor_unit,
        gas=gas,
        ghg_scope=ghg_scope,
        ghg_category=ghg_category,
        kg_co2e=round(kg_co2e, 6),
        tonnes_co2e=round(tonnes_co2e, 6),
        calculated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def result_to_dataframe(result: EmissionResult) -> pd.DataFrame:
    """Convert a calculation result to a one-row DataFrame for CSV export."""
    row = result.as_dict()
    # Present in a friendly column order.
    order = [
        "factor_name", "activity_amount", "activity_unit", "emission_factor",
        "emission_factor_unit", "kg_co2e", "tonnes_co2e", "calculated_at",
    ]
    return pd.DataFrame([{k: row[k] for k in order}])


def emissions_to_csv_bytes(result: EmissionResult) -> bytes:
    """Return the calculator result as UTF-8 CSV bytes (for st.download_button)."""
    return result_to_dataframe(result).to_csv(index=False).encode("utf-8-sig")
