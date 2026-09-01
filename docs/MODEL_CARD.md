# Model card

## Summary

OpenSteamOpt v0.1 is a synthetic educational model of a small industrial steam-and-
power system. It is intended to demonstrate transparent optimisation and digital-twin
software patterns, not to recommend settings for a physical plant.

## Intended uses

- learning how boiler commitment, steam transfers and grid exchange interact;
- testing open-source RTO/FM​​U integration patterns;
- reviewing optimisation formulation and evidence-generation practices; and
- providing a reproducible portfolio example for software and energy engineering.

## Prohibited or unsupported uses

Do not use v0.1 for live control, safety decisions, investment decisions, emissions
reporting, contractual guarantees, operator assessment, or plant economic claims.

## Inputs and outputs

Inputs are 24 consecutive hourly records of HP demand, MP demand, electrical demand,
electricity/fuel prices and carbon price. Outputs are asset commitments and flows,
grid exchange, cost/emissions accounting, slack values and balance residuals.

## Assumptions

- fixed steam energy content (`0.75 MWh/t`);
- two ordered linear fuel segments per boiler;
- direct combustion factors only; no lifecycle emissions;
- deterministic perfect-foresight profiles;
- hourly steady-state RTO with simplified ramping;
- linear turbine power conversion and no steam-property states in the RTO;
- simplified first-order dynamic responses and pressure accumulation; and
- no heat losses, condensate return, water chemistry, trips or interlocks.

## Validation status

The repository verifies mathematical/software consistency: solver termination, objective
reconstruction, mass/power balances, scenario sensitivity, finite dynamic trajectories,
FMU export and FMU simulation. It has not been calibrated or validated against plant
measurements. See [Verification](VERIFICATION.md).

## Risks and safeguards

The most important risk is confusing a deterministic demonstration with an operational
digital twin. The GUI and artifacts carry explicit scientific-status labels, the tools
have no control-system connector, and the documentation avoids real-plant performance
claims. A future live-data interface would require a separate hazard, security, data-
quality and deployment review.
