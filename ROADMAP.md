# Roadmap

The roadmap separates implemented evidence from planned work. Items are not delivery
promises and will be accepted only with tests and documentation.

## v0.1 — complete

- two non-identical boilers, HP/MP headers, turbine, PRV and grid topology;
- carbon-aware hourly MILP with commitment, startup, piecewise fuel and ramps;
- transparent rule baseline and three synthetic sensitivity cases;
- dynamic Python shadow twin and Modelica FMI 2.0 Co-Simulation export;
- advisory Streamlit GUI, evidence pack and open-source governance.

## v0.2 — model fidelity

- LP/condensate network and recoverable heat streams;
- replace fixed steam energy with an open thermophysical-property package;
- warm/cold startup states and minimum up/down times;
- richer turbine extraction/efficiency maps; and
- infeasibility explanations and configurable scenario files.

## v0.3 — control study

- explicit PID benchmark;
- constrained multivariable MPC in shadow simulation;
- disturbance tests and matched PID-vs-MPC metrics; and
- controller model/version receipts.

## v0.4 — data and deployment research

- measurement reconciliation and uncertainty bands;
- forecast adapters with provenance and backtests;
- historian replay and read-only OPC UA adapter; and
- threat model, safety review and human approval workflow.

No live actuator-write capability is planned without independent industrial safety and
cybersecurity review.
