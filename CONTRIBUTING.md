# Contributing

Thanks for improving OpenSteamOpt. Contributions should preserve the project's central
distinction: reproducible educational evidence is welcome; operational plant claims are
not accepted without independently reviewable data and validation.

## Development setup

1. Fork and clone the repository.
2. Create a Python 3.10–3.13 virtual environment.
3. Install `python -m pip install -e ".[gui,fmu,dev]"`.
4. Run `pytest`, `ruff check .`, `ruff format --check .`, and `mypy`.
5. Add or update tests, README scope, model card and changelog where relevant.

OpenModelica is only required for the local FMU integration check. CI verifies the
Modelica interface statically so contributors can work without that optional toolchain.

## Pull requests

Keep changes focused and explain the physical assumption, units and verification route.
Never include credentials, confidential plant data, proprietary models, generated FMU
binaries or claims that cannot be reproduced. New dependencies must be open-source and
justified.

By participating, you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
