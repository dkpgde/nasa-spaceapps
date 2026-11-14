import csv
from datetime import date, timedelta
from itertools import product
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from fieldwork import FieldworkWindow, calculate_fieldwork
from fieldwork_demo import demo_plans
from plan import Operation, OperationCalendar, OperationRule, PlanOperations
from weather import CACHE, load_weather, select_scenario


def test_inclusive_bounds_and_rain_threshold():
    start = date(2020, 2, 28)
    end = date(2020, 3, 4)
    operation = Operation("plant", "Plant", 2020, "planting", OperationCalendar(start, end, "source"))
    rain = pd.Series([0, 1, 1, 0, 1.01, 0, 0], index=pd.date_range("2020-02-27", end))
    result = calculate_fieldwork(PlanOperations("Demo", (operation,)), rain)
    assert result.operations[0].windows == (FieldworkWindow(start, date(2020, 3, 1)),)


def test_missing_data_and_empty_windows_have_distinct_results():
    day = date(2020, 4, 5)
    calendar = OperationCalendar(day, day + timedelta(days=2), "source")
    operations = (
        Operation("term", "Terminate", 2020, "termination", None),
        Operation("plant", "Plant", 2020, "planting", calendar),
    )
    plan = PlanOperations("Demo", operations, (OperationRule("term", "plant"),))
    dates = pd.date_range(calendar.start, calendar.end)
    rain = pd.Series([2, 2, 2], index=dates)

    complete = calculate_fieldwork(plan, rain)
    termination, planting = complete.operations
    assert termination.unavailable_reason
    assert not planting.unavailable_reason and planting.windows == ()
    assert complete.rules[0].unavailable_reason

    missing = calculate_fieldwork(plan, rain.drop(dates[1]))
    assert missing.operations[1].unavailable_reason
    no_rules = calculate_fieldwork(PlanOperations("Demo", operations, None), rain)
    assert no_rules.rules is None


def test_order_and_spacing_allow_exact_minimum():
    day = date(2020, 4, 1)
    calendar = OperationCalendar(day, day + timedelta(days=3), "source")
    operations = (
        Operation("term", "Terminate", 2020, "termination", calendar),
        Operation("plant", "Plant", 2020, "planting", calendar),
    )
    rain = pd.Series(0, index=pd.date_range(calendar.start, calendar.end))
    for gap in (1, 2):
        plan = PlanOperations("Demo", operations, (OperationRule("term", "plant", gap),))
        result = calculate_fieldwork(plan, rain).rules[0]
        expected = ((day + timedelta(days=2), day + timedelta(days=3)),) if gap == 1 else ()
        assert result.feasible_dates == expected
        assert not result.unavailable_reason


def test_wet_spring_dates_and_pairs_against_raw_cached_rainfall():
    raw_rain = {}
    with CACHE.open() as source:
        for line in source:
            if line.strip() == "-END HEADER-":
                break
        for row in csv.DictReader(source):
            day = date(int(row["YEAR"]), 1, 1) + timedelta(days=int(row["DOY"]) - 1)
            raw_rain[day] = float(row["PRECTOTCORR"])

    def expected_dates(start, end):
        return tuple(
            start + timedelta(days=offset)
            for offset in range(2, (end - start).days + 1)
            if max(raw_rain[start + timedelta(days=offset - back)] for back in range(3)) <= 1
        )

    scenario = select_scenario("Wet Spring", load_weather())
    assert scenario.reference_year == 2013
    rye = demo_plans(tuple(map(int, scenario.seasonal_totals.index)))[1]
    result = calculate_fieldwork(rye, scenario.daily["precipitation_mm"])

    termination = expected_dates(date(2013, 4, 1), date(2013, 5, 9))
    soybean = expected_dates(date(2013, 4, 12), date(2013, 5, 20))
    actual = {check.operation.id: check.windows for check in result.operations}
    assert termination and soybean
    assert tuple(window.operation_date for window in actual["2013-rye"]) == termination
    assert tuple(window.operation_date for window in actual["2013-soybean"]) == soybean
    pairs = tuple((t, s) for t, s in product(termination, soybean) if (s - t).days > 10)
    assert pairs and len(pairs) < len(termination) * len(soybean)
    rule = result.rules[0]
    assert rule.feasible_dates == pairs
    assert any((s - t).days == 11 for t, s in pairs)


def test_streamlit_recalculates_fieldwork_when_scenario_changes():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception
    assert app.tabs[1].label == "Corn → soybean with cereal rye"

    app.radio[0].set_value("Wet Spring").run()
    assert not app.exception
    assert any("2013 · Terminate cereal rye" in expander.label for expander in app.expander)
    assert any("11 calendar days" in item.value for item in app.markdown)
    assert any("2013-04-25" in table.value.to_string() for table in app.table)
    assert any("feasible date pairs" in item.value for item in app.markdown)

    app.radio[0].set_value("Dry Summer").run()
    assert not app.exception
    assert all("2013 · Terminate cereal rye" not in expander.label for expander in app.expander)
