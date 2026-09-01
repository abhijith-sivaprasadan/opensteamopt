"""Declared rule-based comparator for the measured reference run."""

from __future__ import annotations

import pandas as pd

from .config import PlantConfig, default_plant
from .rto import RTOResult, _validate_profiles, boiler_fuel_for_load, summarize


def rule_based_baseline(profiles: pd.DataFrame, plant: PlantConfig | None = None) -> RTOResult:
    """Operate B1 alone up to 75 t/h, then hold B1 at 60 t/h and start B2.

    The turbine receives half of MP demand. This is a transparent comparator,
    not a claim about how an industrial plant or ABB OPTIMAX is operated.
    """

    _validate_profiles(profiles)
    plant = plant or default_plant()
    rows: list[dict[str, float | int]] = []
    previous_on = {"B1": 0, "B2": 0}
    for record in profiles.to_dict(orient="records"):
        total_steam = float(record["hp_demand_tph"] + record["mp_demand_tph"])
        if total_steam <= 75.0:
            b1, b2 = total_steam, 0.0
        else:
            b1, b2 = 60.0, total_steam - 60.0
        if b1 > plant.boilers[0].max_steam_tph or b2 > plant.boilers[1].max_steam_tph:
            raise ValueError("Rule-based baseline exceeds boiler capacity")
        turbine = min(0.5 * float(record["mp_demand_tph"]), plant.turbine_max_flow_tph)
        prv = float(record["mp_demand_tph"]) - turbine
        turbine_power = turbine * plant.turbine_power_mw_per_tph
        power_net = float(record["electric_demand_mw"]) - turbine_power
        grid_import, grid_export = max(power_net, 0.0), max(-power_net, 0.0)
        if grid_import > plant.grid_import_limit_mw or grid_export > plant.grid_export_limit_mw:
            raise ValueError("Rule-based baseline exceeds grid capacity")
        loads = {"B1": b1, "B2": b2}
        fuel_cost = carbon_cost = startup_cost = emissions = 0.0
        row: dict[str, float | int] = {"hour": int(record["hour"])}
        for boiler in plant.boilers:
            load = loads[boiler.name]
            on = int(load > 0)
            startup = int(on and not previous_on[boiler.name])
            previous_on[boiler.name] = on
            fuel = boiler_fuel_for_load(boiler.name, load, plant)
            price = float(record[f"{boiler.fuel}_price_eur_per_mwh_fuel"])
            co2 = fuel * boiler.emission_tco2_per_mwh_fuel
            row[f"{boiler.name.lower()}_steam_tph"] = load
            row[f"{boiler.name.lower()}_fuel_mwh"] = fuel
            row[f"{boiler.name.lower()}_on"] = on
            row[f"{boiler.name.lower()}_startup"] = startup
            fuel_cost += fuel * price
            carbon_cost += co2 * float(record["carbon_price_eur_per_tco2"])
            startup_cost += startup * boiler.startup_cost_eur
            emissions += co2
        electricity_cost = float(record["electricity_price_eur_per_mwh"]) * (
            grid_import - plant.export_price_fraction * grid_export
        )
        turbine_cost = turbine_power * plant.turbine_variable_om_eur_per_mwh
        total_cost = fuel_cost + carbon_cost + startup_cost + electricity_cost + turbine_cost
        row.update(
            hp_demand_tph=float(record["hp_demand_tph"]),
            mp_demand_tph=float(record["mp_demand_tph"]),
            electric_demand_mw=float(record["electric_demand_mw"]),
            electricity_price_eur_per_mwh=float(record["electricity_price_eur_per_mwh"]),
            carbon_price_eur_per_tco2=float(record["carbon_price_eur_per_tco2"]),
            turbine_flow_tph=turbine,
            turbine_power_mw=turbine_power,
            prv_flow_tph=prv,
            grid_import_mw=grid_import,
            grid_export_mw=grid_export,
            unmet_hp_tph=0.0,
            unmet_mp_tph=0.0,
            unmet_power_mw=0.0,
            fuel_cost_eur=fuel_cost,
            carbon_cost_eur=carbon_cost,
            electricity_cost_eur=electricity_cost,
            turbine_cost_eur=turbine_cost,
            startup_cost_eur=startup_cost,
            penalty_cost_eur=0.0,
            emissions_tco2=emissions,
            total_cost_eur=total_cost,
            hp_balance_residual_tph=(b1 + b2 - float(record["hp_demand_tph"]) - turbine - prv),
            mp_balance_residual_tph=turbine + prv - float(record["mp_demand_tph"]),
            power_balance_residual_mw=(
                grid_import - grid_export + turbine_power - float(record["electric_demand_mw"])
            ),
        )
        rows.append(row)
    schedule = pd.DataFrame(rows)
    kpis = summarize(schedule, float(schedule.total_cost_eur.sum()))
    return RTOResult(
        schedule=schedule,
        kpis=kpis,
        solver={"name": "declared rule", "status": "not-applicable", "termination": "feasible"},
    )
