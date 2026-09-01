from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app_streamlit.py"


def test_gui_runs_real_rto_and_discloses_scope() -> None:
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    text = " ".join(item.value for item in app.markdown)
    assert "Independent educational implementation" in text
    assert "RTO accepted" in text
    assert any("Optimized cost" in metric.label for metric in app.metric)
    source = APP.read_text(encoding="utf-8")
    assert source.count("st.download_button(") == 2


def test_gui_switches_scenario_and_resolves_again() -> None:
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.selectbox[0].select("high_carbon")
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state["scenario"] == "high_carbon"
