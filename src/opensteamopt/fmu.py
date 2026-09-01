"""OpenModelica FMU build and simulation adapter with no credential or cloud dependency."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def find_omc() -> Path | None:
    explicit = os.environ.get("OPENSTEAMOPT_OMC")
    candidates = [
        Path(explicit) if explicit else None,
        Path(r"C:\Program Files\OpenModelica1.27.0-64bit\bin\omc.exe"),
        Path(r"C:\Program Files\OpenModelica1.26.3-64bit\bin\omc.exe"),
    ]
    command = shutil.which("omc")
    if command:
        candidates.insert(0, Path(command))
    return next((path for path in candidates if path and path.is_file()), None)


def build_fmu(project_root: Path, output_dir: Path) -> dict[str, Any]:
    """Export the authored Modelica plant as FMI 2.0 Co-Simulation."""

    omc = find_omc()
    if omc is None:
        raise FileNotFoundError("OpenModelica omc was not found; set OPENSTEAMOPT_OMC")
    output_dir.mkdir(parents=True, exist_ok=True)
    script = project_root / "scripts" / "build_fmu.mos"
    completed = subprocess.run(
        [str(omc), str(script)],
        cwd=output_dir,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )
    log = output_dir / "openmodelica-build.log"
    log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    fmu = output_dir / "OpenSteamOptPlant.fmu"
    if completed.returncode != 0 or not fmu.is_file():
        raise RuntimeError(f"OpenModelica FMU export failed; inspect {log}")
    return {
        "omc": str(omc),
        "returncode": completed.returncode,
        "fmu": str(fmu),
        "bytes": fmu.stat().st_size,
        "log": str(log),
    }


def fmu_input_from_schedule(schedule: pd.DataFrame) -> np.ndarray:
    """Convert hourly RTO setpoints to an FMI structured input trajectory."""

    required = {
        "hour",
        "b1_steam_tph",
        "b2_steam_tph",
        "turbine_flow_tph",
        "prv_flow_tph",
        "hp_demand_tph",
        "mp_demand_tph",
    }
    if not required <= set(schedule):
        raise ValueError("Schedule lacks FMU inputs")
    names = [
        "boiler1Setpoint",
        "boiler2Setpoint",
        "turbineSetpoint",
        "prvSetpoint",
        "hpDemand",
        "mpDemand",
    ]
    dtype = [("time", np.float64), *[(name, np.float64) for name in names]]
    rows = np.zeros(len(schedule) + 1, dtype=dtype)
    rows["time"][:-1] = schedule.hour.to_numpy(dtype=float) * 3600.0
    rows["time"][-1] = float(len(schedule) * 3600)
    mapping = {
        "boiler1Setpoint": "b1_steam_tph",
        "boiler2Setpoint": "b2_steam_tph",
        "turbineSetpoint": "turbine_flow_tph",
        "prvSetpoint": "prv_flow_tph",
        "hpDemand": "hp_demand_tph",
        "mpDemand": "mp_demand_tph",
    }
    for name, column in mapping.items():
        rows[name][:-1] = schedule[column].to_numpy(dtype=float)
        rows[name][-1] = float(schedule[column].iloc[-1])
    return rows


def simulate_fmu(fmu: Path, schedule: pd.DataFrame, output_interval: float = 60.0) -> pd.DataFrame:
    """Run a locally exported FMU and return named, finite observations."""

    from fmpy import simulate_fmu as _simulate_fmu  # type: ignore[import-untyped]

    output = [
        "boiler1Flow",
        "boiler2Flow",
        "hpPressure",
        "mpPressure",
        "turbineFlow",
        "prvFlow",
        "turbinePower",
        "boiler1Fuel",
        "boiler2Fuel",
    ]
    result = _simulate_fmu(
        str(fmu),
        start_time=0.0,
        stop_time=float(len(schedule) * 3600),
        input=fmu_input_from_schedule(schedule),
        output=output,
        output_interval=output_interval,
        fmi_type="CoSimulation",
    )
    frame = pd.DataFrame({name: result[name] for name in result.dtype.names or ()})
    if set(frame.columns) != {"time", *output}:
        raise ValueError("FMU output contract changed")
    if frame.empty or not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise ValueError("FMU output is empty or non-finite")
    return frame


def write_build_receipt(receipt: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
