from __future__ import annotations

import numpy as np
import pytest

from opensteamopt.baseline import rule_based_baseline
from opensteamopt.profiles import synthetic_day
from opensteamopt.rto import build_model, solve_rto


@pytest.fixture(scope="module")
def base_result():
    return solve_rto(synthetic_day("base"))


def test_base_rto_is_optimal_balanced_and_serves_load(base_result) -> None:
    assert base_result.solver["termination"] == "optimal"
    assert float(base_result.kpis["max_balance_residual"]) < 1e-8
    assert float(base_result.kpis["unmet_steam_tonnes"]) == pytest.approx(0)
    assert float(base_result.kpis["unmet_power_mwh"]) == pytest.approx(0)
    assert float(base_result.kpis["objective_reconstruction_error_eur"]) == pytest.approx(
        0, abs=1e-6
    )


def test_rto_respects_boiler_and_grid_limits(base_result) -> None:
    frame = base_result.schedule
    assert frame.b1_steam_tph.between(0, 80).all()
    assert frame.b2_steam_tph.between(0, 60).all()
    assert frame.grid_import_mw.between(0, 12).all()
    assert frame.grid_export_mw.between(0, 8).all()
    assert ((frame.b1_on == 0) == frame.b1_steam_tph.abs().lt(1e-8)).all()
    assert ((frame.b2_on == 0) == frame.b2_steam_tph.abs().lt(1e-8)).all()


def test_rule_baseline_is_feasible_and_costlier(base_result) -> None:
    baseline = rule_based_baseline(synthetic_day("base"))
    assert float(baseline.kpis["max_balance_residual"]) < 1e-8
    assert float(base_result.kpis["total_cost_eur"]) < float(baseline.kpis["total_cost_eur"])


def test_price_spike_changes_turbine_dispatch() -> None:
    base = solve_rto(synthetic_day("base"))
    spike = solve_rto(synthetic_day("power_price_spike"))
    assert (
        spike.schedule.loc[:5, "turbine_power_mw"].sum()
        > base.schedule.loc[:5, "turbine_power_mw"].sum()
    )


def test_high_carbon_changes_boiler_mix() -> None:
    base = solve_rto(synthetic_day("base"))
    high = solve_rto(synthetic_day("high_carbon"))
    assert high.schedule.b2_steam_tph.sum() > base.schedule.b2_steam_tph.sum()
    assert high.schedule.b1_steam_tph.sum() < base.schedule.b1_steam_tph.sum()


def test_bad_profile_contract_fails_before_solve() -> None:
    bad = synthetic_day().drop(columns="mp_demand_tph")
    with pytest.raises(ValueError, match="Profile columns"):
        build_model(bad)


def test_nonfinite_profile_rejected() -> None:
    bad = synthetic_day()
    bad.loc[0, "hp_demand_tph"] = np.nan
    with pytest.raises(ValueError, match="finite"):
        solve_rto(bad)


def test_nonconsecutive_hours_rejected() -> None:
    bad = synthetic_day().copy()
    bad.loc[3, "hour"] = 4
    with pytest.raises(ValueError, match="consecutive"):
        solve_rto(bad)


def test_negative_input_rejected() -> None:
    bad = synthetic_day().copy()
    bad.loc[0, "electricity_price_eur_per_mwh"] = -1
    with pytest.raises(ValueError, match="nonnegative"):
        solve_rto(bad)


def test_model_contains_integer_commitment_decisions() -> None:
    model = build_model(synthetic_day())
    assert model.on["B1", 0].is_binary()
    assert model.startup["B2", 0].is_binary()
