"""Day-ahead mixed-integer real-time-optimisation scheduling layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import pyomo.environ as pyo  # type: ignore[import-untyped]

from .config import PlantConfig, default_plant


@dataclass(frozen=True)
class RTOResult:
    schedule: pd.DataFrame
    kpis: dict[str, float | int | str]
    solver: dict[str, str]


def _validate_profiles(profiles: pd.DataFrame) -> None:
    required = {
        "hour",
        "hp_demand_tph",
        "mp_demand_tph",
        "electric_demand_mw",
        "electricity_price_eur_per_mwh",
        "natural_gas_price_eur_per_mwh_fuel",
        "biofuel_price_eur_per_mwh_fuel",
        "carbon_price_eur_per_tco2",
    }
    if set(profiles.columns) != required:
        raise ValueError(f"Profile columns differ from the RTO contract: {sorted(required)}")
    if profiles.empty or profiles.hour.tolist() != list(range(len(profiles))):
        raise ValueError("Profiles need consecutive zero-based hourly records")
    numeric = profiles.select_dtypes(include="number")
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy()).all():
        raise ValueError("Profiles must be finite")
    if (profiles.drop(columns="hour") < 0).any().any():
        raise ValueError("Demand and price inputs must be nonnegative in v0.1")


def _piecewise_fuel_data(plant: PlantConfig) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for boiler in plant.boilers:
        minimum, middle, maximum = boiler.fuel_breakpoints(plant.steam_energy_mwh_per_tonne)
        result[boiler.name] = {
            "minimum": minimum,
            "slope_1": (middle - minimum) / (boiler.midpoint_steam_tph - boiler.min_steam_tph),
            "slope_2": (maximum - middle) / (boiler.max_steam_tph - boiler.midpoint_steam_tph),
        }
    return result


def boiler_fuel_for_load(boiler_name: str, load_tph: float, plant: PlantConfig) -> float:
    """Evaluate the same ordered piecewise fuel curve used by the MILP."""

    boiler = next(item for item in plant.boilers if item.name == boiler_name)
    if load_tph == 0:
        return 0.0
    if not boiler.min_steam_tph <= load_tph <= boiler.max_steam_tph:
        raise ValueError(f"{boiler_name} load is outside its on-state range")
    data = _piecewise_fuel_data(plant)[boiler_name]
    first = min(
        load_tph - boiler.min_steam_tph,
        boiler.midpoint_steam_tph - boiler.min_steam_tph,
    )
    second = max(load_tph - boiler.midpoint_steam_tph, 0.0)
    return data["minimum"] + data["slope_1"] * first + data["slope_2"] * second


def build_model(profiles: pd.DataFrame, plant: PlantConfig | None = None) -> pyo.ConcreteModel:
    """Build but do not solve the audited RTO MILP."""

    _validate_profiles(profiles)
    plant = plant or default_plant()
    plant.validate()
    boiler_by_name = {boiler.name: boiler for boiler in plant.boilers}
    fuel_data = _piecewise_fuel_data(plant)
    records = profiles.set_index("hour").to_dict(orient="index")
    model = pyo.ConcreteModel(name="OpenSteamOpt-v0.1")
    model.T = pyo.RangeSet(0, len(profiles) - 1)
    model.B = pyo.Set(initialize=tuple(boiler_by_name))
    model.on = pyo.Var(model.B, model.T, domain=pyo.Binary)
    model.startup = pyo.Var(model.B, model.T, domain=pyo.Binary)
    model.shutdown = pyo.Var(model.B, model.T, domain=pyo.Binary)
    model.high_segment = pyo.Var(model.B, model.T, domain=pyo.Binary)
    model.segment_1 = pyo.Var(model.B, model.T, domain=pyo.NonNegativeReals)
    model.segment_2 = pyo.Var(model.B, model.T, domain=pyo.NonNegativeReals)
    model.boiler_steam = pyo.Var(model.B, model.T, domain=pyo.NonNegativeReals)
    model.boiler_fuel = pyo.Var(model.B, model.T, domain=pyo.NonNegativeReals)
    model.turbine_flow = pyo.Var(model.T, bounds=(0, plant.turbine_max_flow_tph))
    model.prv_flow = pyo.Var(model.T, bounds=(0, plant.prv_max_flow_tph))
    model.grid_import = pyo.Var(model.T, bounds=(0, plant.grid_import_limit_mw))
    model.grid_export = pyo.Var(model.T, bounds=(0, plant.grid_export_limit_mw))
    model.unmet_hp = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.unmet_mp = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.unmet_power = pyo.Var(model.T, domain=pyo.NonNegativeReals)

    def steam_definition(m: pyo.ConcreteModel, boiler_name: str, t: int) -> Any:
        boiler = boiler_by_name[boiler_name]
        return m.boiler_steam[boiler_name, t] == (
            boiler.min_steam_tph * m.on[boiler_name, t]
            + m.segment_1[boiler_name, t]
            + m.segment_2[boiler_name, t]
        )

    model.steam_definition = pyo.Constraint(model.B, model.T, rule=steam_definition)

    def segment_1_cap(m: pyo.ConcreteModel, boiler_name: str, t: int) -> Any:
        boiler = boiler_by_name[boiler_name]
        return (
            m.segment_1[boiler_name, t]
            <= (boiler.midpoint_steam_tph - boiler.min_steam_tph) * m.on[boiler_name, t]
        )

    model.segment_1_cap = pyo.Constraint(model.B, model.T, rule=segment_1_cap)

    def segment_2_cap(m: pyo.ConcreteModel, boiler_name: str, t: int) -> Any:
        boiler = boiler_by_name[boiler_name]
        return (
            m.segment_2[boiler_name, t]
            <= (boiler.max_steam_tph - boiler.midpoint_steam_tph) * m.high_segment[boiler_name, t]
        )

    model.segment_2_cap = pyo.Constraint(model.B, model.T, rule=segment_2_cap)

    def segment_order(m: pyo.ConcreteModel, boiler_name: str, t: int) -> Any:
        boiler = boiler_by_name[boiler_name]
        return (
            m.segment_1[boiler_name, t]
            >= (boiler.midpoint_steam_tph - boiler.min_steam_tph) * m.high_segment[boiler_name, t]
        )

    model.segment_order = pyo.Constraint(model.B, model.T, rule=segment_order)

    def segment_on(m: pyo.ConcreteModel, boiler_name: str, t: int) -> Any:
        return m.high_segment[boiler_name, t] <= m.on[boiler_name, t]

    model.segment_on = pyo.Constraint(model.B, model.T, rule=segment_on)

    def fuel_definition(m: pyo.ConcreteModel, boiler_name: str, t: int) -> Any:
        data = fuel_data[boiler_name]
        return m.boiler_fuel[boiler_name, t] == (
            data["minimum"] * m.on[boiler_name, t]
            + data["slope_1"] * m.segment_1[boiler_name, t]
            + data["slope_2"] * m.segment_2[boiler_name, t]
        )

    model.fuel_definition = pyo.Constraint(model.B, model.T, rule=fuel_definition)

    def transition(m: pyo.ConcreteModel, boiler_name: str, t: int) -> Any:
        previous = 0 if t == 0 else m.on[boiler_name, t - 1]
        return m.on[boiler_name, t] - previous == (
            m.startup[boiler_name, t] - m.shutdown[boiler_name, t]
        )

    model.transition = pyo.Constraint(model.B, model.T, rule=transition)

    def ramp_up(m: pyo.ConcreteModel, boiler_name: str, t: int) -> Any:
        boiler = boiler_by_name[boiler_name]
        previous_flow = 0 if t == 0 else m.boiler_steam[boiler_name, t - 1]
        previous_on = 0 if t == 0 else m.on[boiler_name, t - 1]
        return m.boiler_steam[boiler_name, t] - previous_flow <= (
            boiler.ramp_up_tph_per_hour * previous_on
            + boiler.max_steam_tph * m.startup[boiler_name, t]
        )

    model.ramp_up = pyo.Constraint(model.B, model.T, rule=ramp_up)

    def ramp_down(m: pyo.ConcreteModel, boiler_name: str, t: int) -> Any:
        boiler = boiler_by_name[boiler_name]
        previous_flow = 0 if t == 0 else m.boiler_steam[boiler_name, t - 1]
        return previous_flow - m.boiler_steam[boiler_name, t] <= (
            boiler.ramp_down_tph_per_hour * m.on[boiler_name, t]
            + boiler.max_steam_tph * m.shutdown[boiler_name, t]
        )

    model.ramp_down = pyo.Constraint(model.B, model.T, rule=ramp_down)

    def hp_balance(m: pyo.ConcreteModel, t: int) -> Any:
        return sum(m.boiler_steam[b, t] for b in m.B) + m.unmet_hp[t] == (
            records[t]["hp_demand_tph"] + m.turbine_flow[t] + m.prv_flow[t]
        )

    model.hp_balance = pyo.Constraint(model.T, rule=hp_balance)

    def mp_balance(m: pyo.ConcreteModel, t: int) -> Any:
        return m.turbine_flow[t] + m.prv_flow[t] + m.unmet_mp[t] == records[t]["mp_demand_tph"]

    model.mp_balance = pyo.Constraint(model.T, rule=mp_balance)

    def turbine_demand_bound(m: pyo.ConcreteModel, t: int) -> Any:
        return m.turbine_flow[t] <= records[t]["mp_demand_tph"]

    model.turbine_demand_bound = pyo.Constraint(model.T, rule=turbine_demand_bound)

    def turbine_ramp_up(m: pyo.ConcreteModel, t: int) -> Any:
        previous = 0 if t == 0 else m.turbine_flow[t - 1]
        return m.turbine_flow[t] - previous <= plant.turbine_ramp_tph_per_hour

    model.turbine_ramp_up = pyo.Constraint(model.T, rule=turbine_ramp_up)

    def turbine_ramp_down(m: pyo.ConcreteModel, t: int) -> Any:
        previous = 0 if t == 0 else m.turbine_flow[t - 1]
        return previous - m.turbine_flow[t] <= plant.turbine_ramp_tph_per_hour

    model.turbine_ramp_down = pyo.Constraint(model.T, rule=turbine_ramp_down)

    def power_balance(m: pyo.ConcreteModel, t: int) -> Any:
        return (
            m.grid_import[t]
            - m.grid_export[t]
            + plant.turbine_power_mw_per_tph * m.turbine_flow[t]
            + m.unmet_power[t]
            == records[t]["electric_demand_mw"]
        )

    model.power_balance = pyo.Constraint(model.T, rule=power_balance)

    def objective(m: pyo.ConcreteModel) -> Any:
        total = 0
        for t in m.T:
            price = records[t]["electricity_price_eur_per_mwh"]
            carbon_price = records[t]["carbon_price_eur_per_tco2"]
            for boiler_name in m.B:
                boiler = boiler_by_name[boiler_name]
                fuel_price = records[t][f"{boiler.fuel}_price_eur_per_mwh_fuel"]
                total += m.boiler_fuel[boiler_name, t] * (
                    fuel_price + boiler.emission_tco2_per_mwh_fuel * carbon_price
                )
                total += boiler.startup_cost_eur * m.startup[boiler_name, t]
            turbine_power = plant.turbine_power_mw_per_tph * m.turbine_flow[t]
            total += plant.turbine_variable_om_eur_per_mwh * turbine_power
            total += price * m.grid_import[t]
            total -= plant.export_price_fraction * price * m.grid_export[t]
            total += plant.unmet_steam_penalty_eur_per_tonne * (m.unmet_hp[t] + m.unmet_mp[t])
            total += plant.unmet_power_penalty_eur_per_mwh * m.unmet_power[t]
        return total

    model.total_cost = pyo.Objective(rule=objective, sense=pyo.minimize)
    model._profiles = records
    model._plant = plant
    return model


def _value(variable: Any) -> float:
    value = pyo.value(variable)
    if value is None or not np.isfinite(value):
        raise ValueError("Solver returned an absent/non-finite value")
    return float(value)


def extract_schedule(model: pyo.ConcreteModel) -> pd.DataFrame:
    """Extract a solved model and independently reconstruct all accounting terms."""

    plant: PlantConfig = model._plant
    boiler_by_name = {boiler.name: boiler for boiler in plant.boilers}
    rows: list[dict[str, float | int]] = []
    for t in model.T:
        record = model._profiles[int(t)]
        row: dict[str, float | int] = {"hour": int(t)}
        fuel_cost = carbon_cost = startup_cost = emissions = 0.0
        for boiler_name in model.B:
            boiler = boiler_by_name[str(boiler_name)]
            steam = _value(model.boiler_steam[boiler_name, t])
            fuel = _value(model.boiler_fuel[boiler_name, t])
            startup = int(round(_value(model.startup[boiler_name, t])))
            row[f"{str(boiler_name).lower()}_steam_tph"] = steam
            row[f"{str(boiler_name).lower()}_fuel_mwh"] = fuel
            row[f"{str(boiler_name).lower()}_on"] = int(round(_value(model.on[boiler_name, t])))
            row[f"{str(boiler_name).lower()}_startup"] = startup
            price = float(record[f"{boiler.fuel}_price_eur_per_mwh_fuel"])
            co2 = fuel * boiler.emission_tco2_per_mwh_fuel
            fuel_cost += fuel * price
            carbon_cost += co2 * float(record["carbon_price_eur_per_tco2"])
            emissions += co2
            startup_cost += startup * boiler.startup_cost_eur
        turbine_flow = _value(model.turbine_flow[t])
        turbine_power = turbine_flow * plant.turbine_power_mw_per_tph
        grid_import = _value(model.grid_import[t])
        grid_export = _value(model.grid_export[t])
        electricity_cost = float(record["electricity_price_eur_per_mwh"]) * (
            grid_import - plant.export_price_fraction * grid_export
        )
        turbine_cost = turbine_power * plant.turbine_variable_om_eur_per_mwh
        unmet_hp = _value(model.unmet_hp[t])
        unmet_mp = _value(model.unmet_mp[t])
        unmet_power = _value(model.unmet_power[t])
        penalty = plant.unmet_steam_penalty_eur_per_tonne * (unmet_hp + unmet_mp)
        penalty += plant.unmet_power_penalty_eur_per_mwh * unmet_power
        row.update(
            hp_demand_tph=float(record["hp_demand_tph"]),
            mp_demand_tph=float(record["mp_demand_tph"]),
            electric_demand_mw=float(record["electric_demand_mw"]),
            electricity_price_eur_per_mwh=float(record["electricity_price_eur_per_mwh"]),
            carbon_price_eur_per_tco2=float(record["carbon_price_eur_per_tco2"]),
            turbine_flow_tph=turbine_flow,
            turbine_power_mw=turbine_power,
            prv_flow_tph=_value(model.prv_flow[t]),
            grid_import_mw=grid_import,
            grid_export_mw=grid_export,
            unmet_hp_tph=unmet_hp,
            unmet_mp_tph=unmet_mp,
            unmet_power_mw=unmet_power,
            fuel_cost_eur=fuel_cost,
            carbon_cost_eur=carbon_cost,
            electricity_cost_eur=electricity_cost,
            turbine_cost_eur=turbine_cost,
            startup_cost_eur=startup_cost,
            penalty_cost_eur=penalty,
            emissions_tco2=emissions,
            total_cost_eur=(
                fuel_cost + carbon_cost + electricity_cost + turbine_cost + startup_cost + penalty
            ),
        )
        row["hp_balance_residual_tph"] = (
            float(row["b1_steam_tph"])
            + float(row["b2_steam_tph"])
            + unmet_hp
            - float(record["hp_demand_tph"])
            - turbine_flow
            - float(row["prv_flow_tph"])
        )
        row["mp_balance_residual_tph"] = (
            turbine_flow + float(row["prv_flow_tph"]) + unmet_mp - float(record["mp_demand_tph"])
        )
        row["power_balance_residual_mw"] = (
            grid_import
            - grid_export
            + turbine_power
            + unmet_power
            - float(record["electric_demand_mw"])
        )
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(schedule: pd.DataFrame, objective: float) -> dict[str, float | int | str]:
    reconstructed = float(schedule.total_cost_eur.sum())
    max_residual = float(
        schedule[
            ["hp_balance_residual_tph", "mp_balance_residual_tph", "power_balance_residual_mw"]
        ]
        .abs()
        .to_numpy()
        .max()
    )
    if not np.isclose(reconstructed, objective, rtol=1e-8, atol=1e-5):
        raise ValueError("Independent objective reconstruction failed")
    if max_residual > 1e-6:
        raise ValueError("Physical balance residual exceeds tolerance")
    return {
        "solver_status": "optimal",
        "total_cost_eur": reconstructed,
        "fuel_cost_eur": float(schedule.fuel_cost_eur.sum()),
        "electricity_cost_eur": float(schedule.electricity_cost_eur.sum()),
        "carbon_cost_eur": float(schedule.carbon_cost_eur.sum()),
        "startup_cost_eur": float(schedule.startup_cost_eur.sum()),
        "emissions_tco2": float(schedule.emissions_tco2.sum()),
        "grid_import_mwh": float(schedule.grid_import_mw.sum()),
        "grid_export_mwh": float(schedule.grid_export_mw.sum()),
        "turbine_generation_mwh": float(schedule.turbine_power_mw.sum()),
        "unmet_steam_tonnes": float(schedule.unmet_hp_tph.sum() + schedule.unmet_mp_tph.sum()),
        "unmet_power_mwh": float(schedule.unmet_power_mw.sum()),
        "boiler_startups": int(schedule.b1_startup.sum() + schedule.b2_startup.sum()),
        "max_balance_residual": max_residual,
        "objective_reconstruction_error_eur": reconstructed - objective,
    }


def solve_rto(profiles: pd.DataFrame, plant: PlantConfig | None = None) -> RTOResult:
    """Solve the v0.1 RTO with open-source HiGHS and verify the result."""

    model = build_model(profiles, plant)
    solver = pyo.SolverFactory("appsi_highs")
    result = solver.solve(model)
    termination = str(result.solver.termination_condition).lower()
    status = str(result.solver.status).lower()
    if termination != "optimal":
        raise RuntimeError(f"RTO failed with {status}/{termination}")
    objective = _value(model.total_cost)
    schedule = extract_schedule(model)
    kpis = summarize(schedule, objective)
    return RTOResult(
        schedule=schedule,
        kpis=kpis,
        solver={"name": "HiGHS", "status": status, "termination": termination},
    )
