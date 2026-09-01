"""Command-line interface for repeatable advisory and shadow runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .profiles import SCENARIOS, synthetic_day
from .rto import solve_rto
from .twin import shadow_kpis, simulate_shadow


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, default="base")
    parser.add_argument("--output", type=Path, default=Path("runs/latest"))
    parser.add_argument(
        "--shadow", action="store_true", help="Run setpoints in the local grey-box twin"
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Output directory must be new to prevent silent overwrite")
    args.output.mkdir(parents=True)
    result = solve_rto(synthetic_day(args.scenario))
    result.schedule.to_csv(args.output / "schedule.csv", index=False, lineterminator="\n")
    summary: dict[str, object] = {
        "scenario": args.scenario,
        "mode": "shadow" if args.shadow else "advisory",
        "rto": result.kpis,
        "solver": result.solver,
        "scientific_status": "synthetic_educational_not_plant_validated",
    }
    if args.shadow:
        trace = simulate_shadow(result.schedule)
        trace.to_csv(args.output / "shadow_trace.csv", index=False, lineterminator="\n")
        summary["shadow"] = shadow_kpis(trace)
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
