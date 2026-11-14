from dataclasses import replace
from datetime import date

from fieldwork import calculate_fieldwork
from fieldwork_demo import corn_soybean_plans, timeline_operations
from rotationlab.catalog import load_catalog, load_cover_recipes
from rotationlab.model import Availability, expand_rotation
from weather import load_weather, select_scenario


DATA, CALENDARS = load_catalog()
RECIPES = load_cover_recipes(DATA)
YEAR_START, YEAR_END = date(2017, 1, 1), date(2020, 12, 31)


def rye_timeline(phase=0, calendars=CALENDARS, coverage=None):
    _, plan = corn_soybean_plans(phase, RECIPES)
    return expand_rotation(plan, YEAR_START, YEAR_END, calendars, coverage)


def test_rye_uses_the_grain_corn_harvest_and_repeats_only_before_soybean():
    timeline = rye_timeline()
    assert [(t.harvest_year, t.planting_year) for t in timeline.cover_transitions] == [
        (2017, 2018), (2019, 2020),
    ]
    for transition in timeline.cover_transitions:
        fall, spring = transition.harvest_year, transition.planting_year
        for result, expected in (
            (transition.seeding, (date(fall, 9, 22), date(fall, 10, 27))),
            (transition.living_cover, (date(fall, 11, 3), date(spring, 3, 31))),
            (transition.termination, (date(spring, 4, 1), date(spring, 5, 9))),
        ):
            window, = result.intervals
            assert (window.start, window.end) == expected
            assert "mccc_rye_soybean" in window.sources
    assert not RECIPES[0].matches("soybean", "grain_corn")
    assert not RECIPES[0].matches("corn_silage", "soybean")


def test_rye_carryover_respects_supplied_coverage_and_rotation_end():
    timeline = rye_timeline(phase=1, coverage=(date(2017, 2, 1), YEAR_END))
    initial = timeline.cover_transitions[0]
    assert initial.harvest_year == 2016
    assert initial.seeding.intervals == ()
    cover, = initial.living_cover.intervals
    assert cover.carryover
    assert (cover.original_start, cover.start, cover.end) == (
        date(2016, 11, 3), date(2017, 2, 1), date(2017, 3, 31),
    )
    final = timeline.cover_transitions[-1]
    assert (final.harvest_year, final.planting_year) == (2020, 2021)
    assert final.living_cover.intervals[0].end == YEAR_END
    assert final.termination.intervals == ()


def test_missing_or_late_harvest_changes_rye_availability():
    corn = CALENDARS["grain_corn"]
    missing = replace(corn, unavailable_rules={"harvest": "No sourced harvest dates"})
    timeline = rye_timeline(phase=1, calendars={**CALENDARS, "grain_corn": missing})
    initial = timeline.cover_transitions[0]
    assert initial.living_cover.availability == Availability.UNAVAILABLE
    assert initial.seeding.availability == Availability.UNAVAILABLE
    assert initial.termination.availability == Availability.UNAVAILABLE
    assert initial.living_cover.intervals == ()
    late = replace(corn, rules=tuple(
        replace(rule, start="11-01") if rule.kind == "harvest" else rule for rule in corn.rules
    ))
    transition = rye_timeline(calendars={**CALENDARS, "grain_corn": late}).cover_transitions[0]
    assert transition.seeding.availability == Availability.AVAILABLE
    assert transition.seeding.reason and transition.seeding.intervals == ()
    assert transition.living_cover.intervals == ()
    assert transition.termination.intervals == ()


def test_missing_soybean_calendar_marks_termination_and_spacing_unavailable():
    soybean = replace(CALENDARS["soybean"], unavailable_rules={"planting": "Planting dates unavailable"})
    calendars = {**CALENDARS, "soybean": soybean}
    timeline = rye_timeline(calendars=calendars)
    assert timeline.cover_transitions[0].termination.availability == Availability.UNAVAILABLE
    operations = timeline_operations(timeline, calendars, DATA["sources"])
    scenario = select_scenario("Typical", load_weather())
    result = calculate_fieldwork(operations, scenario.daily["precipitation_mm"])
    assert len(result.rules) == 2
    assert all(rule.unavailable_reason for rule in result.rules)
