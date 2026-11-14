from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / 'timeline_app.py')


def test_app_opens_offline_and_phase_control_changes_sequence():
    app = AppTest.from_file(APP).run(timeout=20)
    assert not app.exception
    assert any('2017 Grain corn → 2018 Soybean' in m.value for m in app.markdown)
    assert len(app.get('vega_lite_chart') + app.get('arrow_vega_lite_chart')) == 1
    app.selectbox[0].select('Soybean').run()
    assert not app.exception
    assert any('2017 Soybean → 2018 Grain corn' in m.value for m in app.markdown)
    app.number_input[0].set_value(2020).run()
    assert not app.exception
    assert any('2023 Grain corn' in m.value for m in app.markdown)


def test_app_handles_empty_and_invalid_coverage():
    app = AppTest.from_file(APP).run(timeout=20)
    from datetime import date
    app.date_input[1].set_value(date(2017, 2, 1)).run()
    assert not app.exception
    assert any('contains no calendar intervals' in m.value for m in app.info)
    app.date_input[0].set_value(date(2017, 3, 1)).run()
    assert not app.exception
    assert len(app.error) == 1


def test_rye_example_shows_carryover_and_uses_the_same_phase_for_fieldwork():
    app = AppTest.from_file(APP).run(timeout=20)
    app.selectbox[0].select("Soybean")
    app.selectbox[1].select("Corn → soybean with cereal rye")
    app.run(timeout=20)
    assert not app.exception
    assert any("2016 corn → 2017 soybean" in frame.value.to_string() for frame in app.dataframe)
    assert any("2017-01-01 → 2017-03-31" in frame.value.to_string() for frame in app.dataframe)
    assert any("MCCC-103" in line.value for line in app.markdown)
    assert any("2010 · Terminate cereal rye" == expander.label for expander in app.expander)
