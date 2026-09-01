# Verification and reproducibility

## Automated checks

The test suite covers configuration validation, scenario contracts, boiler fuel curves,
commitment/ramping behaviour, balance and objective reconstruction, scenario response,
shadow dynamics, FMU input names, artifact hashing, Modelica interface declarations and
the Streamlit application. CI runs tests, Ruff and mypy on supported Python versions.

Local v0.1 acceptance result:

```text
28 passed
Ruff: all checks passed
mypy: no findings
```

## Reference scenarios

`scripts/run_reference.py` solves three deterministic cases and evaluates the same cases
with a declared rule-based comparator. The committed `scenario-kpis.csv` is the source
for the README table. Optimised cases have no unmet steam or power, and their maximum
reconstructed balance residual is `7.105427357601002e-15`.

The comparison is a software regression fixture, not a backtest. The baseline was
authored for this repository and is not evidence of operator or product performance.

`manifest.json` records:

- the scientific-status label;
- all declared plant parameters;
- scenario names and solver family; and
- a SHA-256 digest for each output file.

To create a non-destructive replay:

```bash
python scripts/run_reference.py --output runs/reference-replay
```

## FMU integration check

`scripts/verify_fmu.py` builds `OpenSteamOpt.TwoBoilerSteamPlant` with OpenModelica as an
FMI 2.0 Co-Simulation FMU, applies the base RTO trajectory with FMPy, rejects non-finite
outputs and writes a metadata receipt.

The committed receipt records OpenModelica 1.27.0, 1,441 samples over 86,400 seconds,
HP pressure `49.3477–50.5661 bar` and MP pressure `10.0000–11.4911 bar`. These ranges are
integration evidence under one synthetic input, not validation limits or guarantees.

Binary FMUs are compiler/platform artifacts and are ignored by Git. Rebuild locally to
verify a toolchain; the receipt stores source and FMU SHA-256 hashes.

## Remaining verification debt

- cross-tool FMU testing beyond OpenModelica/FMPy;
- property-based and longer-horizon scenario testing;
- comparison with a thermodynamic steam-property model;
- measured-data calibration and out-of-sample validation;
- infeasibility diagnostics for user-supplied cases; and
- security/safety validation for any future external connector.
