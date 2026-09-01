from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from opensteamopt.reporting import plot_reference, write_manifest


def test_manifest_hashes_every_existing_file(tmp_path: Path) -> None:
    payload = tmp_path / "result.csv"
    payload.write_text("x\n1\n", encoding="utf-8")
    record = write_manifest(tmp_path, {"kind": "test"})
    expected = hashlib.sha256(payload.read_bytes()).hexdigest()
    assert record["files"] == {"result.csv": expected}
    reread = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert reread == record


def test_reference_plots_render_with_headless_backend(tmp_path: Path) -> None:
    schedule = pd.DataFrame(
        {
            "hour": [0, 1],
            "hp_demand_tph": [40.0, 42.0],
            "mp_demand_tph": [20.0, 18.0],
            "b1_steam_tph": [50.0, 50.0],
            "b2_steam_tph": [10.0, 10.0],
            "electricity_price_eur_per_mwh": [50.0, 60.0],
            "turbine_power_mw": [2.0, 2.2],
            "grid_import_mw": [3.0, 2.8],
        }
    )
    trace = pd.DataFrame(
        {
            "time_seconds": [0.0, 60.0],
            "hp_pressure_bar": [50.0, 49.9],
            "mp_pressure_bar": [10.0, 10.1],
        }
    )
    paths = plot_reference(schedule, trace, tmp_path)
    assert len(paths) == 3
    assert all(path.stat().st_size > 0 for path in paths)
