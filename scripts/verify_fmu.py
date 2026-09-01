"""Build and exercise the OpenModelica FMU, then publish a metadata-only receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from opensteamopt.fmu import build_fmu, simulate_fmu
from opensteamopt.profiles import synthetic_day
from opensteamopt.rto import solve_rto


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=Path("build/fmu"))
    parser.add_argument("--receipt", type=Path, default=Path("artifacts/fmu-verification.json"))
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    receipt = build_fmu(project, project / args.build)
    fmu = Path(receipt["fmu"])
    schedule = solve_rto(synthetic_day()).schedule
    frame = simulate_fmu(fmu, schedule)
    omc_version = subprocess.run(
        [receipt["omc"], "--version"],
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    ).stdout.strip()
    public = {
        "schema_version": 1,
        "kind": "local_fmu_build_and_simulation_not_plant_validation",
        "model": "OpenSteamOpt.TwoBoilerSteamPlant",
        "fmi_version": "2.0",
        "fmi_type": "CoSimulation",
        "openmodelica": omc_version,
        "modelica_source_sha256": _sha(project / "modelica/OpenSteamOpt/package.mo"),
        "fmu_sha256": _sha(fmu),
        "fmu_bytes": fmu.stat().st_size,
        "samples": len(frame),
        "start_time_seconds": float(frame.time.iloc[0]),
        "stop_time_seconds": float(frame.time.iloc[-1]),
        "outputs_finite": True,
        "hp_pressure_bar": {
            "min": float(frame.hpPressure.min()),
            "max": float(frame.hpPressure.max()),
        },
        "mp_pressure_bar": {
            "min": float(frame.mpPressure.min()),
            "max": float(frame.mpPressure.max()),
        },
        "limitations": [
            "Synthetic grey-box dynamics; no plant measurements or steam-property library.",
            "Setpoints are applied only to the local FMU; no DCS, OPC UA or actuator connection.",
            "The proportional pressure trim is not model-predictive control.",
        ],
    }
    target = project / args.receipt
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(public, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": str(target), "samples": len(frame)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
