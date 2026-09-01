"""Local advisory/shadow workbench for OpenSteamOpt."""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go  # type: ignore[import-untyped]
import streamlit as st

from opensteamopt.baseline import rule_based_baseline
from opensteamopt.fmu import find_omc
from opensteamopt.profiles import SCENARIOS, synthetic_day
from opensteamopt.rto import solve_rto
from opensteamopt.twin import shadow_kpis, simulate_shadow

st.set_page_config(page_title="OpenSteamOpt", page_icon="♨️", layout="wide")
st.markdown(
    """
    <style>
    :root { color-scheme: light; }
    .stApp { background: #f7f8fa; color: #17212b; }
    [data-testid="stSidebar"] { background: #e9eef4; }
    h1, h2, h3, p, label, [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
      color: #17212b !important;
    }
    .scope-note { border-left: 5px solid #0b5fa5; padding: .8rem 1rem; background: #eaf3fb;
      color: #17324d; border-radius: .25rem; }
    .status-good { border-left: 5px solid #087f5b; padding: .7rem 1rem; background: #e9f7f1;
      color: #123d30; }
    code { color: #16263b !important; background: #e7edf4 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def run_case(
    scenario: str,
) -> tuple[
    pd.DataFrame,
    dict[str, float | int | str],
    pd.DataFrame,
    dict[str, float | int | str],
]:
    profiles = synthetic_day(scenario)
    optimized = solve_rto(profiles)
    baseline = rule_based_baseline(profiles)
    return optimized.schedule, optimized.kpis, baseline.schedule, baseline.kpis


def dispatch_figure(schedule: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    figure.add_scatter(x=schedule.hour, y=schedule.b1_steam_tph, name="Boiler 1", mode="lines")
    figure.add_scatter(x=schedule.hour, y=schedule.b2_steam_tph, name="Boiler 2", mode="lines")
    figure.add_scatter(
        x=schedule.hour,
        y=schedule.hp_demand_tph + schedule.mp_demand_tph,
        name="Total demand",
        mode="lines",
        line={"dash": "dash", "color": "#17212b"},
    )
    figure.update_layout(
        title="Steam dispatch",
        xaxis_title="Hour",
        yaxis_title="Steam flow (t/h)",
        template="plotly_white",
        legend={"orientation": "h"},
    )
    return figure


def power_figure(schedule: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    figure.add_scatter(x=schedule.hour, y=schedule.turbine_power_mw, name="Turbine power")
    figure.add_scatter(x=schedule.hour, y=schedule.grid_import_mw, name="Grid import")
    figure.add_scatter(x=schedule.hour, y=schedule.grid_export_mw, name="Grid export")
    figure.update_layout(
        title="Power dispatch",
        xaxis_title="Hour",
        yaxis_title="Power (MW)",
        template="plotly_white",
        legend={"orientation": "h"},
    )
    return figure


st.title("OpenSteamOpt")
st.subheader("Industrial steam & power digital-twin + RTO demonstrator")
st.markdown(
    '<div class="scope-note"><strong>Independent educational implementation.</strong> '
    "Inspired by publicly described industrial energy-management architecture; not an ABB product, "
    "OPTIMAX clone, commissioned plant model, or operational control system.</div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Advisory case")
    scenario = st.selectbox(
        "Synthetic scenario",
        SCENARIOS,
        format_func=lambda value: value.replace("_", " ").title(),
    )
    run = st.button("Solve 24-hour schedule", type="primary", width="stretch")
    st.caption("All prices and loads are synthetic v0.1 fixtures. No plant credentials are used.")

if run or "result" not in st.session_state:
    with st.spinner("Solving and independently checking balances/accounting…"):
        st.session_state.result = run_case(scenario)
        st.session_state.scenario = scenario

schedule, kpis, baseline_schedule, baseline_kpis = st.session_state.result
tabs = st.tabs(["Plant", "RTO schedule", "Shadow twin", "Verification & scope"])

with tabs[0]:
    st.header("Declared v0.1 plant")
    st.markdown(
        """
        ```text
        Natural-gas boiler ─┐
                            ├─ HP header ─┬─ HP process
        Biofuel boiler ─────┘             ├─ back-pressure turbine ─┬─ MP header ─ process
                                          └─ pressure-reducing valve┘
                                                    │
                                                 generator ↔ grid
        ```
        """
    )
    st.write(
        "The boilers have different capacities, efficiencies, fuels, emissions, ramp limits and "
        "time constants. The Modelica model carries HP/MP pressure states; the RTO uses a "
        "steady-state hourly balance and sends setpoints only to the shadow twin."
    )
    st.dataframe(
        pd.DataFrame(
            [
                {"asset": "B1", "fuel": "natural gas", "min–max": "20–80 t/h", "ramp": "28 t/h/h"},
                {"asset": "B2", "fuel": "biofuel", "min–max": "15–60 t/h", "ramp": "18 t/h/h"},
                {"asset": "Turbine", "fuel": "HP steam", "min–max": "0–55 t/h", "ramp": "30 t/h/h"},
                {"asset": "PRV", "fuel": "n/a", "min–max": "0–70 t/h", "ramp": "fast actuator"},
            ]
        ),
        hide_index=True,
        width="stretch",
    )

with tabs[1]:
    st.header(f"Advisory schedule · {st.session_state.scenario.replace('_', ' ')}")
    columns = st.columns(4)
    columns[0].metric("Optimized cost", f"€{float(kpis['total_cost_eur']):,.0f}")
    columns[1].metric("Rule baseline", f"€{float(baseline_kpis['total_cost_eur']):,.0f}")
    columns[2].metric("Direct CO₂", f"{float(kpis['emissions_tco2']):,.1f} t")
    columns[3].metric("Max balance residual", f"{float(kpis['max_balance_residual']):.1e}")
    st.plotly_chart(dispatch_figure(schedule), width="stretch")
    st.plotly_chart(power_figure(schedule), width="stretch")
    st.dataframe(schedule.round(4), hide_index=True, width="stretch")
    st.download_button(
        "Download verified schedule CSV",
        schedule.to_csv(index=False).encode(),
        file_name=f"opensteamopt-{st.session_state.scenario}-schedule.csv",
        mime="text/csv",
    )

with tabs[2]:
    st.header("Shadow-mode dynamic check")
    st.write(
        "RTO setpoints are applied only to a local grey-box twin. A proportional HP-pressure trim "
        "represents a lower-level stabilising loop; it is not MPC."
    )
    trace = simulate_shadow(schedule)
    shadow = shadow_kpis(trace)
    pressure = go.Figure()
    pressure.add_scatter(x=trace.time_seconds / 3600, y=trace.hp_pressure_bar, name="HP pressure")
    pressure.add_scatter(x=trace.time_seconds / 3600, y=trace.mp_pressure_bar, name="MP pressure")
    pressure.update_layout(
        template="plotly_white",
        xaxis_title="Time (h)",
        yaxis_title="Pressure (bar)",
        legend={"orientation": "h"},
    )
    st.plotly_chart(pressure, width="stretch")
    st.json(shadow)
    st.caption("A separately exported OpenModelica FMI 2.0 Co-Simulation FMU is verified locally.")

with tabs[3]:
    st.header("Evidence and boundaries")
    omc = find_omc()
    st.markdown(
        '<div class="status-good"><strong>RTO accepted:</strong> HiGHS returned optimal; the '
        "objective was reconstructed independently and HP, MP and electrical balances pass.</div>",
        unsafe_allow_html=True,
    )
    st.write(
        {"OpenModelica detected": str(omc) if omc else "No", "mode": "advisory + local shadow"}
    )
    st.markdown(
        """
        **Implemented in v0.1:** synthetic day-ahead schedule, load-dependent boiler fuel curves,
        on/off/startup/ramp limits, turbine/PRV/grid dispatch, carbon cost, pressure-state twin,
        FMU export adapter, GUI and tests.

        **Not yet implemented:** multivariable MPC, PID-vs-MPC study, measurement reconciliation,
        OPC UA, data historian, forecast learning, startup thermodynamics, steam-property library,
        safety interlocks or live DCS connection.
        """
    )
    st.download_button(
        "Download run summary JSON",
        json.dumps(
            {
                "scenario": st.session_state.scenario,
                "rto": kpis,
                "baseline": baseline_kpis,
                "scientific_status": "synthetic_educational_not_plant_validated",
            },
            indent=2,
        ),
        file_name="opensteamopt-summary.json",
        mime="application/json",
    )
