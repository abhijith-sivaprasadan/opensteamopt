"""Versioned synthetic plant assumptions used by the optimizer and twin."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class BoilerSpec:
    """Piecewise-linear boiler operating contract in engineering units."""

    name: str
    fuel: str
    min_steam_tph: float
    midpoint_steam_tph: float
    max_steam_tph: float
    efficiency_at_min: float
    efficiency_at_mid: float
    efficiency_at_max: float
    ramp_up_tph_per_hour: float
    ramp_down_tph_per_hour: float
    startup_cost_eur: float
    emission_tco2_per_mwh_fuel: float
    time_constant_seconds: float

    def validate(self) -> None:
        if not 0 < self.min_steam_tph < self.midpoint_steam_tph < self.max_steam_tph:
            raise ValueError(f"Invalid load points for {self.name}")
        efficiencies = (
            self.efficiency_at_min,
            self.efficiency_at_mid,
            self.efficiency_at_max,
        )
        if not all(0 < value <= 1 for value in efficiencies):
            raise ValueError(f"Invalid efficiency for {self.name}")
        if min(self.ramp_up_tph_per_hour, self.ramp_down_tph_per_hour) <= 0:
            raise ValueError(f"Invalid ramp limit for {self.name}")

    def fuel_breakpoints(self, steam_energy_mwh_per_tonne: float) -> tuple[float, float, float]:
        return (
            steam_energy_mwh_per_tonne * self.min_steam_tph / self.efficiency_at_min,
            steam_energy_mwh_per_tonne * self.midpoint_steam_tph / self.efficiency_at_mid,
            steam_energy_mwh_per_tonne * self.max_steam_tph / self.efficiency_at_max,
        )


@dataclass(frozen=True)
class PlantConfig:
    """Synthetic site boundary; values are assumptions, not ABB plant data."""

    boilers: tuple[BoilerSpec, BoilerSpec]
    steam_energy_mwh_per_tonne: float = 0.75
    turbine_max_flow_tph: float = 55.0
    turbine_power_mw_per_tph: float = 0.12
    turbine_variable_om_eur_per_mwh: float = 15.0
    turbine_ramp_tph_per_hour: float = 30.0
    prv_max_flow_tph: float = 70.0
    grid_import_limit_mw: float = 12.0
    grid_export_limit_mw: float = 8.0
    export_price_fraction: float = 0.90
    hp_pressure_nominal_bar: float = 50.0
    mp_pressure_nominal_bar: float = 10.0
    hp_pressure_gain_bar_per_tonne: float = 0.08
    mp_pressure_gain_bar_per_tonne: float = 0.12
    turbine_time_constant_seconds: float = 45.0
    prv_time_constant_seconds: float = 12.0
    pressure_trim_gain_tph_per_bar: float = 2.0
    unmet_steam_penalty_eur_per_tonne: float = 20_000.0
    unmet_power_penalty_eur_per_mwh: float = 30_000.0

    def validate(self) -> None:
        for boiler in self.boilers:
            boiler.validate()
        positive = (
            self.steam_energy_mwh_per_tonne,
            self.turbine_max_flow_tph,
            self.turbine_power_mw_per_tph,
            self.prv_max_flow_tph,
            self.grid_import_limit_mw,
            self.hp_pressure_nominal_bar,
            self.mp_pressure_nominal_bar,
        )
        if not all(value > 0 for value in positive):
            raise ValueError("Plant capacities and nominal states must be positive")
        if not 0 <= self.export_price_fraction <= 1:
            raise ValueError("Export price fraction must be in [0,1]")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_plant() -> PlantConfig:
    """Return the reviewed v0.1 synthetic plant."""

    plant = PlantConfig(
        boilers=(
            BoilerSpec(
                name="B1",
                fuel="natural_gas",
                min_steam_tph=20.0,
                midpoint_steam_tph=50.0,
                max_steam_tph=80.0,
                efficiency_at_min=0.82,
                efficiency_at_mid=0.90,
                efficiency_at_max=0.87,
                ramp_up_tph_per_hour=28.0,
                ramp_down_tph_per_hour=32.0,
                startup_cost_eur=600.0,
                emission_tco2_per_mwh_fuel=0.202,
                time_constant_seconds=90.0,
            ),
            BoilerSpec(
                name="B2",
                fuel="biofuel",
                min_steam_tph=15.0,
                midpoint_steam_tph=37.5,
                max_steam_tph=60.0,
                efficiency_at_min=0.72,
                efficiency_at_mid=0.80,
                efficiency_at_max=0.78,
                ramp_up_tph_per_hour=18.0,
                ramp_down_tph_per_hour=22.0,
                startup_cost_eur=450.0,
                emission_tco2_per_mwh_fuel=0.035,
                time_constant_seconds=150.0,
            ),
        )
    )
    plant.validate()
    return plant
