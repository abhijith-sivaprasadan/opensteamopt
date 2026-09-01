"""Deterministic synthetic profiles; no observed plant or ABB data are implied."""

from __future__ import annotations

import numpy as np
import pandas as pd

SCENARIOS = ("base", "power_price_spike", "high_carbon")


def synthetic_day(scenario: str = "base") -> pd.DataFrame:
    """Create a 24-hour explanatory schedule input with declared units."""

    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario!r}; choose from {SCENARIOS}")
    hour = np.arange(24)
    hp = 28.0 + 4.0 * np.sin((hour - 5) * np.pi / 12) + np.where((hour >= 8) & (hour < 18), 7, 0)
    mp = 34.0 + 5.0 * np.sin((hour - 7) * np.pi / 12) + np.where((hour >= 6) & (hour < 21), 6, 0)
    electric = (
        7.0 + 1.1 * np.sin((hour - 8) * np.pi / 12) + np.where((hour >= 7) & (hour < 19), 1.2, 0)
    )
    power_price = np.array(
        [
            8,
            7,
            6,
            6,
            8,
            12,
            58,
            74,
            82,
            76,
            64,
            57,
            52,
            48,
            45,
            51,
            69,
            96,
            112,
            88,
            66,
            53,
            45,
            40,
        ],
        dtype=float,
    )
    carbon = np.full(24, 85.0)
    if scenario == "power_price_spike":
        power_price[0:6] += 95.0
    elif scenario == "high_carbon":
        carbon[:] = 170.0
    frame = pd.DataFrame(
        {
            "hour": hour,
            "hp_demand_tph": hp.round(3),
            "mp_demand_tph": mp.round(3),
            "electric_demand_mw": electric.round(3),
            "electricity_price_eur_per_mwh": power_price,
            "natural_gas_price_eur_per_mwh_fuel": 34.0,
            "biofuel_price_eur_per_mwh_fuel": 47.0,
            "carbon_price_eur_per_tco2": carbon,
        }
    )
    if frame.isna().any().any() or (frame.drop(columns="hour") < 0).any().any():
        raise ValueError("Synthetic profiles must be finite and nonnegative")
    return frame
