"""Rainfall screens for dated RotationLab calendars."""

from dataclasses import dataclass
from datetime import date
from itertools import groupby

import numpy as np
import pandas as pd

from fieldwork import LOW_RAIN_DAYS, MAX_DAILY_RAIN_MM, FieldworkResult, calculate_fieldwork
from plan import Operation, OperationCalendar, OperationRule, PlanOperations
from rotation import Calendar, CropYear, Dates


HEAVY_MM = 25.0
DRY_MM = 1.0

RULES = (
    f"**Heavy rain.** At least {HEAVY_MM:g} mm on a calendar day. Count a date once if it falls "
    "outside the union of all planned living cover, including any cover crop still alive. "
    "Residue after harvest, termination or winterkill is outside this measure.",
    f"**Fieldwork.** At least {LOW_RAIN_DAYS} consecutive days with at most {MAX_DAILY_RAIN_MM:g} mm "
    "each, entirely within the operation calendar. The last day of each qualifying "
    "window is an eligible operation date. Spacing compares those dates in calendar days.",
    f"**Dry spell.** Consecutive days with less than {DRY_MM:g} mm inside the crop's sensitive "
    "calendar. Exactly 1 mm breaks a run. The earliest start wins ties.",
    "All date ranges include both endpoints. Results requiring missing rain or calendar "
    "information are unavailable. Soil texture is context. Actual field access, erosion and crop "
    "water stress depend on field conditions and management.",
)


@dataclass(frozen=True)
class DrySpell:
    observed: Dates | None
    complete: bool
    longest: Dates | None


@dataclass(frozen=True)
class YearResults:
    uncovered: tuple[tuple[date, float], ...] | None
    fieldwork: FieldworkResult
    dry_spell: DrySpell | None


def rain_for(rain: pd.Series, dates: Dates) -> pd.Series:
    return rain.reindex(pd.date_range(dates.start, dates.end))


def complete(rain: pd.Series) -> bool:
    values = rain.to_numpy(dtype=float)
    return bool(len(values) and np.isfinite(values).all() and (values >= 0).all())


def runs(mask: pd.Series):
    for qualifies, group in groupby(zip(mask.index.date, mask), key=lambda item: item[1]):
        if qualifies:
            dates = [day for day, _ in group]
            yield Dates(dates[0], dates[-1])


def fieldwork(year: CropYear, rain: pd.Series) -> FieldworkResult:
    # The crop calendar provides the dates and displays its source citations.
    operations = tuple(
        Operation(kind, event.label, year.year, kind,
                  OperationCalendar(event.dates.start, event.dates.end, "")
                  if kind != "planting" or year.planting_available else None)
        for kind, event in (("termination", year.termination), ("planting", year.planting))
        if event is not None
    )
    rules = () if year.minimum_gap is None else (OperationRule("termination", "planting", year.minimum_gap),)
    return calculate_fieldwork(PlanOperations(year.crop, operations, rules), rain)


def dry_spell(window: Dates, rain: pd.Series, span: Dates) -> DrySpell:
    observed = span.overlap(window)
    if observed is None:
        return DrySpell(None, False, None)
    period = rain_for(rain, observed)
    valid = pd.Series(np.isfinite(period) & period.ge(0), index=period.index)
    # Missing days break a run. A partial result can be shown with its coverage warning.
    longest = max(runs(valid & period.lt(DRY_MM)), key=lambda run: run.end - run.start, default=None)
    return DrySpell(observed, observed == window and complete(period), longest)


def analyze(calendar: Calendar, daily: pd.DataFrame, *, operation_weather=None) -> dict[int, YearResults]:
    rain = rain_for(daily["precipitation_mm"], calendar.span)
    cover = [event.dates for event in calendar.timeline() if event.kind == "Living cover"]
    results = {}
    for year in calendar.years:
        year_span = calendar.span.overlap(Dates(date(year.year, 1, 1), date(year.year, 12, 31)))
        period = rain_for(rain, year_span)
        uncovered = None
        if not year.cover_unknown and complete(period):
            outside = period.ge(HEAVY_MM)
            for dates in cover:
                if dates.overlap(year_span):
                    outside.loc[pd.Timestamp(dates.start):pd.Timestamp(dates.end)] = False
            uncovered = tuple((day.date(), float(value)) for day, value in period[outside].items())
        exposure = dry_spell(year.sensitive.dates, rain, calendar.span) if year.sensitive else None
        operations_rain = rain
        if operation_weather is not None and year.planting and year.planting.dates.start < calendar.span.start:
            operations_rain = operation_weather["precipitation_mm"]
        results[year.year] = YearResults(uncovered, fieldwork(year, operations_rain), exposure)
    return results
