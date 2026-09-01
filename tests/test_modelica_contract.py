from __future__ import annotations

from pathlib import Path


def test_modelica_fmu_interface_and_dynamic_states_are_authored() -> None:
    source = Path("modelica/OpenSteamOpt/package.mo").read_text(encoding="utf-8")
    for name in (
        "boiler1Setpoint",
        "boiler2Setpoint",
        "turbineSetpoint",
        "prvSetpoint",
        "hpDemand",
        "mpDemand",
        "hpPressure",
        "mpPressure",
    ):
        assert name in source
    assert "der(hpPressure)" in source
    assert "der(mpPressure)" in source
    assert "der(boiler1Flow)" in source
    assert "der(boiler2Flow)" in source


def test_build_script_requests_fmi2_cosimulation() -> None:
    script = Path("scripts/build_fmu.mos").read_text(encoding="utf-8")
    assert 'version="2.0"' in script
    assert 'fmuType="cs"' in script
    assert 'fileNamePrefix="OpenSteamOptPlant"' in script
