from datetime import date
import pytest
from rotationlab.catalog import load_catalog
from rotationlab.model import (Availability, CropCalendar, RotationPlan, WindowRule,
                               expand_rotation)

DATA, CALENDARS = load_catalog()
PLAN = RotationPlan('Corn–soybean', ('grain_corn', 'soybean'))


def test_four_year_sequence_and_preceding_phase():
    result = expand_rotation(PLAN, date(2017, 1, 1), date(2020, 12, 31), CALENDARS)
    assert [y.crop_id for y in result.years] == ['grain_corn', 'soybean'] * 2
    assert result.years[0].preceding_crop_id == 'soybean'
    assert len(result.windows) == 20
    assert not any(w.carryover for w in result.windows)
    swapped = expand_rotation(RotationPlan('Swapped', PLAN.crop_years, 1),
                              result.start, result.end, CALENDARS)
    assert [y.crop_id for y in swapped.years] == ['soybean', 'grain_corn'] * 2
    assert swapped.years[0].preceding_crop_id == 'grain_corn'


def test_dates_match_sourced_catalog_and_no_winter_cover():
    result = expand_rotation(PLAN, date(2017, 1, 1), date(2020, 12, 31), CALENDARS)
    # ISU 2021 planting guidance; USDA NASS 2010 p.39 usual harvest.
    assert [(w.start, w.end) for w in result.query(2017, 'grain_corn', 'planting').intervals] == [(date(2017, 4, 11), date(2017, 5, 18))]
    assert result.query(2018, 'soybean', 'planting').intervals[0].end == date(2018, 5, 20)
    assert result.query(2017, 'grain_corn', 'harvest').intervals[0].end == date(2017, 11, 21)
    assert result.query(2018, 'soybean', 'harvest').intervals[0].end == date(2018, 10, 31)
    assert result.query(2020, 'soybean', 'living_cover').intervals[0].end == date(2020, 9, 15)
    assert all(result.start <= w.start <= w.end <= result.end for w in result.windows)
    assert all(w.assumption and set(w.sources) <= DATA['sources'].keys() for w in result.windows)


def test_partial_coverage_and_empty_differ_from_missing():
    result = expand_rotation(PLAN, date(2017, 1, 1), date(2020, 12, 31), CALENDARS,
                             coverage=(date(2017, 7, 15), date(2019, 8, 1)))
    assert result.query(2017, 'grain_corn', 'living_cover').intervals[0].start == date(2017, 7, 15)
    assert result.query(2019, 'grain_corn', 'sensitive').intervals[0].end == date(2019, 8, 1)
    empty = result.query(2020, 'soybean', 'living_cover')
    assert empty.availability == Availability.AVAILABLE and empty.intervals == ()
    assert result.query(2017, 'grain_corn', 'termination').intervals == ()
    assert result.query(2017, 'grain_corn', 'termination').availability == Availability.AVAILABLE
    missing = expand_rotation(RotationPlan('Custom', ('unknown',)), result.start, result.end, CALENDARS)
    assert missing.query(2017, 'unknown', 'living_cover').availability == Availability.UNAVAILABLE
    assert missing.query(2017, 'unknown', 'living_cover').reason
    assert result.query(2017, 'grain_corn', 'unknown_rule').availability == Availability.UNAVAILABLE


def test_explicit_carryover_is_clipped_to_available_dates():
    rule = WindowRule('living_cover', 'Synthetic overwinter fixture', '10-01', '04-10',
                      ('test_fixture',), end_year_offset=1)
    calendars = {'winter': CropCalendar('winter', 'Fixture only', (rule,))}
    plan = RotationPlan('Fixture', ('winter',))
    result = expand_rotation(plan, date(2017, 1, 1), date(2020, 12, 31), calendars,
                             coverage=(date(2017, 2, 1), date(2020, 11, 1)))
    carry = [w for w in result.windows if w.carryover]
    assert len(carry) == 1
    assert (carry[0].start, carry[0].end) == (date(2017, 2, 1), date(2017, 4, 10))
    assert carry[0].crop_year == 2016
    assert max(w.end for w in result.windows) == date(2020, 11, 1)


def test_missing_individual_rule_is_exposed():
    calendars = {'partial': CropCalendar('partial', 'Partial', (), unavailable_rules={'sensitive':'No documented stage rule'})}
    result = expand_rotation(RotationPlan('Partial', ('partial',)), date(2020, 1, 1), date(2023, 12, 31), calendars)
    assert result.query(2020, 'partial', 'sensitive').availability == Availability.UNAVAILABLE
    assert result.query(2020, 'partial', 'termination').availability == Availability.AVAILABLE


@pytest.mark.parametrize('start,end', [(date(2020, 1, 2), date(2020, 1, 1)), (date(2020, 1, 1), date(2024, 1, 1))])
def test_invalid_boundaries(start, end):
    with pytest.raises(ValueError):
        expand_rotation(PLAN, start, end, CALENDARS)


def test_invalid_phase():
    with pytest.raises(ValueError):
        RotationPlan('Invalid', PLAN.crop_years, 2)


def test_leap_day_is_not_dropped_from_cover():
    rule = WindowRule('living_cover', 'Fixture', '01-01', '03-01', ('fixture',))
    result = expand_rotation(RotationPlan('Fixture', ('fixture',)), date(2020, 2, 29), date(2020, 2, 29),
                             {'fixture': CropCalendar('fixture', 'Fixture', (rule,))})
    assert result.windows[0].start == result.windows[0].end == date(2020, 2, 29)
