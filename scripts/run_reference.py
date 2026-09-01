"""Generate the v0.1 synthetic reference evidence from a fresh directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from opensteamopt.baseline import rule_based_baseline
from opensteamopt.config import default_plant
from opensteamopt.profiles import SCENARIOS, synthetic_day
from opensteamopt.reporting import plot_reference, write_manifest
from opensteamopt.rto import solve_rto
from opensteamopt.twin import shadow_kpis, simulate_shadow


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/reference"))
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError("Reference output must be absent or empty")
    args.output.mkdir(parents=True, exist_ok=True)
    plant = default_plant()
    summaries: list[dict[str, object]] = []
    base_schedule: pd.DataFrame | None = None
    for scenario in SCENARIOS:
        profiles = synthetic_day(scenario)
        optimized = solve_rto(profiles, plant)
        baseline = rule_based_baseline(profiles, plant)
        optimized.schedule.to_csv(
            args.output / f"{scenario}-optimized.csv", index=False, lineterminator="\n"
        )
        baseline.schedule.to_csv(
            args.output / f"{scenario}-baseline.csv", index=False, lineterminator="\n"
        )
        summaries.append(
            {
                "scenario": scenario,
                "baseline_total_cost_eur": baseline.kpis["total_cost_eur"],
                "optimized_total_cost_eur": optimized.kpis["total_cost_eur"],
                "baseline_emissions_tco2": baseline.kpis["emissions_tco2"],
                "optimized_emissions_tco2": optimized.kpis["emissions_tco2"],
                "optimized_unmet_steam_tonnes": optimized.kpis["unmet_steam_tonnes"],
                "optimized_unmet_power_mwh": optimized.kpis["unmet_power_mwh"],
                "max_balance_residual": optimized.kpis["max_balance_residual"],
            }
        )
        if scenario == "base":
            base_schedule = optimized.schedule
    assert base_schedule is not None
    trace = simulate_shadow(base_schedule, plant=plant)
    trace.to_csv(args.output / "base-shadow-trace.csv", index=False, lineterminator="\n")
    summary = pd.DataFrame(summaries)
    summary.to_csv(args.output / "scenario-kpis.csv", index=False, lineterminator="\n")
    (args.output / "shadow-kpis.json").write_text(
        json.dumps(shadow_kpis(trace, plant), indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    plot_reference(base_schedule, trace, args.output)
    manifest = write_manifest(
        args.output,
        {
            "kind": "synthetic_educational_reference_not_plant_validation",
            "scenarios": list(SCENARIOS),
            "plant": plant.to_dict(),
            "solver": "HiGHS via Pyomo",
        },
    )
    print(json.dumps({"files": len(manifest["files"]), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
