"""Transparent grey-box dynamic twin used for fast tests and FMU cross-checks."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import PlantConfig, default_plant


@dataclass
class TwinState:
    b1_steam_tph: float
    b2_steam_tph: float
    turbine_flow_tph: float
    prv_flow_tph: float
    hp_pressure_bar: float
    mp_pressure_bar: float


def _first_order_rate(
    actual: float, command: float, tau_seconds: float, ramp_tph_h: float
) -> float:
    requested = (command - actual) / tau_seconds
    ramp_per_second = ramp_tph_h / 3600.0
    return float(np.clip(requested, -ramp_per_second, ramp_per_second))


def simulate_shadow(
    schedule: pd.DataFrame,
    *,
    plant: PlantConfig | None = None,
    step_seconds: float = 60.0,
    pressure_trim: bool = True,
) -> pd.DataFrame:
    """Run setpoints through the local dynamic twin without controlling a real plant."""

    plant = plant or default_plant()
    required = {
        "hour",
        "b1_steam_tph",
        "b2_steam_tph",
        "turbine_flow_tph",
        "prv_flow_tph",
        "hp_demand_tph",
        "mp_demand_tph",
    }
    if not required <= set(schedule.columns) or schedule.empty:
        raise ValueError("Schedule lacks dynamic-twin setpoints")
    if step_seconds <= 0 or 3600 % step_seconds != 0:
        raise ValueError("Step must be a positive divisor of one hour")
    initial = schedule.iloc[0]
    state = TwinState(
        b1_steam_tph=float(initial.b1_steam_tph),
        b2_steam_tph=float(initial.b2_steam_tph),
        turbine_flow_tph=float(initial.turbine_flow_tph),
        prv_flow_tph=float(initial.prv_flow_tph),
        hp_pressure_bar=plant.hp_pressure_nominal_bar,
        mp_pressure_bar=plant.mp_pressure_nominal_bar,
    )
    rows: list[dict[str, float | int]] = []
    steps_per_hour = int(3600 / step_seconds)
    for _, setpoint in schedule.iterrows():
        for step in range(steps_per_hour):
            trim = (
                plant.pressure_trim_gain_tph_per_bar
                * (plant.hp_pressure_nominal_bar - state.hp_pressure_bar)
                if pressure_trim
                else 0.0
            )
            b1_command = float(
                np.clip(
                    float(setpoint.b1_steam_tph) + 0.6 * trim,
                    0,
                    plant.boilers[0].max_steam_tph,
                )
            )
            b2_command = float(
                np.clip(
                    float(setpoint.b2_steam_tph) + 0.4 * trim,
                    0,
                    plant.boilers[1].max_steam_tph,
                )
            )
            state.b1_steam_tph += step_seconds * _first_order_rate(
                state.b1_steam_tph,
                b1_command,
                plant.boilers[0].time_constant_seconds,
                plant.boilers[0].ramp_up_tph_per_hour,
            )
            state.b2_steam_tph += step_seconds * _first_order_rate(
                state.b2_steam_tph,
                b2_command,
                plant.boilers[1].time_constant_seconds,
                plant.boilers[1].ramp_up_tph_per_hour,
            )
            state.turbine_flow_tph += step_seconds * _first_order_rate(
                state.turbine_flow_tph,
                float(setpoint.turbine_flow_tph),
                plant.turbine_time_constant_seconds,
                plant.turbine_ramp_tph_per_hour,
            )
            state.prv_flow_tph += step_seconds * _first_order_rate(
                state.prv_flow_tph,
                float(setpoint.prv_flow_tph),
                plant.prv_time_constant_seconds,
                plant.prv_max_flow_tph * 4,
            )
            hp_residual = (
                state.b1_steam_tph
                + state.b2_steam_tph
                - float(setpoint.hp_demand_tph)
                - state.turbine_flow_tph
                - state.prv_flow_tph
            )
            mp_residual = (
                state.turbine_flow_tph + state.prv_flow_tph - float(setpoint.mp_demand_tph)
            )
            state.hp_pressure_bar += (
                step_seconds * plant.hp_pressure_gain_bar_per_tonne * hp_residual / 3600.0
            )
            state.mp_pressure_bar += (
                step_seconds * plant.mp_pressure_gain_bar_per_tonne * mp_residual / 3600.0
            )
            rows.append(
                {
                    "time_seconds": int(float(setpoint.hour) * 3600 + step * step_seconds),
                    "hour": int(setpoint.hour),
                    "b1_setpoint_tph": float(setpoint.b1_steam_tph),
                    "b2_setpoint_tph": float(setpoint.b2_steam_tph),
                    "b1_steam_tph": state.b1_steam_tph,
                    "b2_steam_tph": state.b2_steam_tph,
                    "turbine_flow_tph": state.turbine_flow_tph,
                    "prv_flow_tph": state.prv_flow_tph,
                    "hp_pressure_bar": state.hp_pressure_bar,
                    "mp_pressure_bar": state.mp_pressure_bar,
                    "hp_balance_residual_tph": hp_residual,
                    "mp_balance_residual_tph": mp_residual,
                    "turbine_power_mw": (state.turbine_flow_tph * plant.turbine_power_mw_per_tph),
                }
            )
    result = pd.DataFrame(rows)
    if result.isna().any().any() or not np.isfinite(result.select_dtypes("number")).all().all():
        raise ValueError("Dynamic twin produced non-finite output")
    return result


def shadow_kpis(trace: pd.DataFrame, plant: PlantConfig | None = None) -> dict[str, float]:
    plant = plant or default_plant()
    return {
        "hp_pressure_max_deviation_bar": float(
            (trace.hp_pressure_bar - plant.hp_pressure_nominal_bar).abs().max()
        ),
        "mp_pressure_max_deviation_bar": float(
            (trace.mp_pressure_bar - plant.mp_pressure_nominal_bar).abs().max()
        ),
        "hp_pressure_standard_deviation_bar": float(trace.hp_pressure_bar.std(ddof=0)),
        "mp_pressure_standard_deviation_bar": float(trace.mp_pressure_bar.std(ddof=0)),
        "max_dynamic_mass_imbalance_tph": float(
            trace[["hp_balance_residual_tph", "mp_balance_residual_tph"]].abs().to_numpy().max()
        ),
    }
