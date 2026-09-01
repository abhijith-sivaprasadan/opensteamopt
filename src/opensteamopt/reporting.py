"""Deterministic plots and integrity receipts for reference evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def plot_reference(schedule: pd.DataFrame, trace: pd.DataFrame, output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    # Evidence generation must also work on headless CI/Windows installations without Tcl/Tk.
    plt.switch_backend("Agg")
    plt.style.use("seaborn-v0_8-whitegrid")
    figures: list[Path] = []

    fig, ax = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
    ax.step(
        schedule.hour,
        schedule.hp_demand_tph + schedule.mp_demand_tph,
        where="mid",
        label="Total steam demand",
        linewidth=2.5,
    )
    ax.step(schedule.hour, schedule.b1_steam_tph, where="mid", label="Boiler 1", linewidth=2)
    ax.step(schedule.hour, schedule.b2_steam_tph, where="mid", label="Boiler 2", linewidth=2)
    ax.set(
        xlabel="Hour",
        ylabel="Steam flow (t/h)",
        title="Demand and optimized boiler loading",
    )
    ax.legend(ncol=3)
    path = output / "steam_dispatch.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path)

    fig, ax1 = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
    ax1.step(
        schedule.hour,
        schedule.electricity_price_eur_per_mwh,
        where="mid",
        color="#8b1e3f",
        linewidth=2.4,
        label="Electricity price",
    )
    ax1.set(xlabel="Hour", ylabel="Electricity price (EUR/MWh)")
    ax2 = ax1.twinx()
    ax2.step(
        schedule.hour,
        schedule.turbine_power_mw,
        where="mid",
        color="#0057a8",
        linewidth=2.2,
        label="Turbine power",
    )
    ax2.step(
        schedule.hour,
        schedule.grid_import_mw,
        where="mid",
        color="#147d64",
        linewidth=2.0,
        label="Grid import",
    )
    ax2.set_ylabel("Power (MW)")
    ax1.set_title("Price-responsive turbine and grid dispatch")
    lines = ax1.get_lines() + ax2.get_lines()
    ax1.legend(lines, [str(line.get_label()) for line in lines], ncol=3, loc="upper left")
    path = output / "power_price_dispatch.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path)

    fig, ax = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
    hours = trace.time_seconds / 3600.0
    ax.plot(hours, trace.hp_pressure_bar, label="HP header", linewidth=1.8)
    ax.plot(hours, trace.mp_pressure_bar, label="MP header", linewidth=1.8)
    ax.set(
        xlabel="Time (h)",
        ylabel="Pressure (bar)",
        title="Shadow-mode header-pressure response",
    )
    ax.legend()
    path = output / "shadow_pressures.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(path)
    return figures


def write_manifest(root: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    files = {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    record = {"schema_version": 1, **metadata, "files": files}
    (root / "manifest.json").write_text(
        json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return record
