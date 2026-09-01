from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from opensteamopt.config import default_plant
from opensteamopt.profiles import SCENARIOS, synthetic_day
from opensteamopt.rto import boiler_fuel_for_load


def test_default_plant_is_valid_and_non_identical() -> None:
    plant = default_plant()
    plant.validate()
    assert plant.boilers[0].fuel != plant.boilers[1].fuel
    assert plant.boilers[0].max_steam_tph != plant.boilers[1].max_steam_tph
    assert plant.boilers[0].time_constant_seconds != plant.boilers[1].time_constant_seconds


def test_invalid_load_points_fail_closed() -> None:
    plant = default_plant()
    invalid = replace(plant.boilers[0], midpoint_steam_tph=plant.boilers[0].max_steam_tph)
    with pytest.raises(ValueError, match="load points"):
        invalid.validate()


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_profiles_are_complete_finite_days(scenario: str) -> None:
    frame = synthetic_day(scenario)
    assert frame.hour.tolist() == list(range(24))
    assert np.isfinite(frame.select_dtypes("number")).all().all()
    assert (frame.drop(columns="hour") >= 0).all().all()


def test_price_spike_is_bounded_to_declared_hours() -> None:
    base = synthetic_day("base")
    spike = synthetic_day("power_price_spike")
    difference = spike.electricity_price_eur_per_mwh - base.electricity_price_eur_per_mwh
    assert difference.iloc[:6].eq(95).all()
    assert difference.iloc[6:].eq(0).all()


def test_piecewise_fuel_curve_hits_authored_breakpoints() -> None:
    plant = default_plant()
    boiler = plant.boilers[0]
    loads = (boiler.min_steam_tph, boiler.midpoint_steam_tph, boiler.max_steam_tph)
    expected = boiler.fuel_breakpoints(plant.steam_energy_mwh_per_tonne)
    actual = tuple(boiler_fuel_for_load(boiler.name, load, plant) for load in loads)
    assert actual == pytest.approx(expected)
    assert boiler_fuel_for_load(boiler.name, 0, plant) == 0
    with pytest.raises(ValueError, match="outside"):
        boiler_fuel_for_load(boiler.name, boiler.min_steam_tph - 1, plant)


def test_unknown_scenario_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown scenario"):
        synthetic_day("invented")
