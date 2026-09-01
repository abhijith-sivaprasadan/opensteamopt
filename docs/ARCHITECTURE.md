# Architecture

OpenSteamOpt separates planning, dynamic simulation and presentation so each layer can
be inspected and tested independently.

```text
Synthetic profiles ──► Pyomo MILP ──► HiGHS ──► verified hourly schedule
                           │                          │
                           │                          ├─► Streamlit advisory GUI
                           │                          ├─► Python shadow twin
                           │                          └─► FMI input trajectory
                           │                                      │
Declared plant config ─────┴────────► Modelica plant ─► FMU ──────┘
```

## Components

| Component | Responsibility | Explicit boundary |
|---|---|---|
| `config.py` | Immutable synthetic asset declaration and validation | No plant registry or hidden defaults |
| `profiles.py` | Deterministic 24-hour loads/prices | Not forecasts or observed market data |
| `rto.py` | MILP construction, solve, extraction and independent checks | Hourly steady-state balances, not dynamic MPC |
| `baseline.py` | Declared rule-based comparison | Not historical operator performance |
| `twin.py` | Fast first-order dynamic shadow simulation | Grey-box teaching model, not calibrated physics |
| `package.mo` | HP/MP dynamic Modelica plant and FMU interface | No steam-property library or safety system |
| `fmu.py` | OpenModelica build and FMPy simulation adapter | Local files only; no DCS or network interface |
| `app_streamlit.py` | Advisory inspection and downloads | No actuator writes or credential handling |

## RTO formulation

At each hour, the model balances boiler steam against HP process demand and transfers
to the MP header through a turbine or PRV. Turbine generation plus grid exchange meets
electrical demand. Binary boiler states enforce commitment and startup transitions;
ordered linear segments approximate load-dependent fuel consumption.

The cost function contains:

1. boiler fuel consumption × synthetic fuel price;
2. direct fuel emissions × synthetic carbon price;
3. boiler startup cost;
4. turbine variable operating cost;
5. grid imports less discounted exports; and
6. high penalties for unmet steam or power.

Every solution is rejected unless HiGHS reports optimal termination. Extracted values
are then used to reconstruct cost and all three balances outside the Pyomo objective.

## Trust boundaries

- No external service, credential, plant tag or network connection is required.
- GUI actions solve locally and produce advisory downloads only.
- FMU input names form a small, tested public contract.
- Run directories refuse overwrite to preserve evidence provenance.
- Committed binary FMUs are avoided; the build receipt carries hashes and versions.
