from datetime import date
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from rainfall import analyze
from rotation import Calendar, CropYear, Dates, Event
from site_data import comparison_conditions, historical_conditions, load_site_weather
from weather import POWER_LABEL, load_weather, select_scenario


def test_alternative_rainfall_reaches_scenario_analysis():
    site = load_site_weather()
    power = load_weather().assign(source=POWER_LABEL)
    historical = historical_conditions(power, site, "GPM IMERG")
    assert historical.index.min() == pd.Timestamp("2001-01-01")
    assert historical["precipitation_mm"].eq(site.loc[historical.index, "imerg_mm"]).all()
    assert not historical["precipitation_mm"].eq(power.loc[historical.index, "precipitation_mm"]).all()

    scenario = select_scenario("Wet Spring", historical)
    assert scenario.reference_period == (2001, 2025)
    assert scenario.daily.index[-1].year - scenario.daily.index[0].year == 3
    assert scenario.daily["source"].eq("GPM IMERG").all()


def test_temperature_and_soil_moisture_use_crop_windows():
    day = date(2020, 1, 1)
    span = Dates(day, date(2020, 1, 4))
    planting = Event("Planting", "Planting", Dates(day, date(2020, 1, 2)))
    sensitive = Event("Sensitive", "Sensitive stage", Dates(date(2020, 1, 3), span.end))
    crop_year = CropYear(2020, "Test crop", (), planting, None, None, sensitive, ())
    calendar = Calendar(span, "Previous crop", (crop_year,), ())
    daily = pd.DataFrame({
        "precipitation_mm": [0, 0, 0, 0],
        "min_c": [-1, 0, -3, -1],
        "max_c": [39, 42, 35, 33],
        "root_zone_percentile": [6, 9, 19, 20],
    }, index=pd.date_range(span.start, span.end))
    result = analyze(calendar, daily)[2020]
    assert result.freeze_planting_days == 2
    assert result.hot_sensitive_days == 1
    assert result.low_moisture_sensitive_days == 1
    daily.loc["2020-01-04", "root_zone_percentile"] = float("nan")
    assert analyze(calendar, daily)[2020].low_moisture_sensitive_days is None

    daily = daily[["precipitation_mm"]].assign(source="NASA climate projection")
    projected = comparison_conditions(daily, load_site_weather(), "NASA POWER")
    assert projected[["min_c", "max_c", "root_zone_percentile"]].isna().all().all()


def test_prism_source_and_observation_panels_render():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    app.selectbox(key="rain-source").select("PRISM").run()
    assert not app.exception
    assert any("PRISM rainfall" in caption.value for caption in app.caption)
    assert any("Canisteo clay loam" in heading.value for heading in app.subheader)
    app.selectbox(key="impact-indicator").select("Hot days during sensitive growth").run()
    assert not app.exception


def test_location_changes_keep_boone_data_and_plan_selection_local():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    app.selectbox(key="rain-source").select("PRISM")
    app.checkbox(key="show-plan-0").uncheck().run()
    assert not app.exception
    assert all(heading.value != "Corn–soybean" for heading in app.subheader)

    next(button for button in app.button if button.label == "Mead ENREC, Nebraska").click().run()
    assert not app.exception and not app.error
    assert app.selectbox(key="weather-choice-mead").value == "Custom years"
    assert app.checkbox(key="show-plan-mead-0").value
    assert any(heading.value == "Sorghum–soybean" for heading in app.subheader)
    assert all(widget.key != "rain-source" for widget in app.selectbox)
    assert all(heading.value != "Boone County observations" for heading in app.header)

    # The map callback sets this same key when a county is picked.
    app.session_state["comparison-county"] = "06037"
    app.run()
    assert not app.exception and not app.error
    assert app.selectbox(key="weather-county-06037").value == 2026
    assert any(button.label == "Download daily weather (CSV)" for button in app.get("download_button"))
    assert all(heading.value != "Comparison settings" for heading in app.header)

    next(button for button in app.button if button.label == "Marsden Farm, Iowa").click().run()
    assert not app.exception
    assert app.selectbox(key="rain-source").value == "PRISM"
    assert not app.checkbox(key="show-plan-0").value
