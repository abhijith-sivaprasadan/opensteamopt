from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from opensteamopt.fmu import fmu_input_from_schedule
from opensteamopt.profiles import synthetic_day
from opensteamopt.rto import solve_rto
from opensteamopt.twin import shadow_kpis, simulate_shadow


@pytest.fixture(scope="module")
def schedule() -> pd.DataFrame:
    return solve_rto(synthetic_day()).schedule


def test_shadow_trace_is_finite_and_complete(schedule: pd.DataFrame) -> None:
    trace = simulate_shadow(schedule)
    assert len(trace) == 24 * 60
    assert trace.time_seconds.iloc[0] == 0
    assert trace.time_seconds.iloc[-1] == 24 * 3600 - 60
    assert np.isfinite(trace.select_dtypes("number")).all().all()


def test_pressure_trim_reduces_hp_pressure_deviation(schedule: pd.DataFrame) -> None:
    controlled = shadow_kpis(simulate_shadow(schedule, pressure_trim=True))
    untrimmed = shadow_kpis(simulate_shadow(schedule, pressure_trim=False))
    assert controlled["hp_pressure_max_deviation_bar"] < untrimmed["hp_pressure_max_deviation_bar"]


def test_constant_balanced_schedule_stays_at_nominal(schedule: pd.DataFrame) -> None:
    constant = pd.concat(
        [schedule.iloc[[0]].assign(hour=hour) for hour in range(3)], ignore_index=True
    )
    trace = simulate_shadow(constant)
    assert trace.hp_pressure_bar.max() == pytest.approx(50.0, abs=1e-10)
    assert trace.mp_pressure_bar.max() == pytest.approx(10.0, abs=1e-10)


def test_invalid_shadow_step_rejected(schedule: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="divisor"):
        simulate_shadow(schedule, step_seconds=70)


def test_fmu_input_has_exact_names_and_terminal_hold(schedule: pd.DataFrame) -> None:
    trajectory = fmu_input_from_schedule(schedule)
    assert trajectory.dtype.names == (
        "time",
        "boiler1Setpoint",
        "boiler2Setpoint",
        "turbineSetpoint",
        "prvSetpoint",
        "hpDemand",
        "mpDemand",
    )
    assert trajectory["time"][-1] == 24 * 3600
    assert trajectory["boiler1Setpoint"][-1] == pytest.approx(schedule.b1_steam_tph.iloc[-1])
