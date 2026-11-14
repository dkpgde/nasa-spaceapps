"""Rainfall screens for dated RotationLab calendars."""

from bisect import bisect_left
from dataclasses import dataclass
from datetime import date
from itertools import groupby

import numpy as np
import pandas as pd

from rotation import DAY, Calendar, CropYear, Dates, Event


HEAVY_MM = 25.0
FIELDWORK_MM = 2.5
FIELDWORK_DAYS = 2
DRY_MM = 1.0

RULES = (
    f"**Heavy rain.** At least {HEAVY_MM:g} mm on a calendar day. Count a date once if it falls "
    "outside the union of all planned living cover, including any cover crop still alive. "
    "Residue after harvest, termination or winterkill is outside this measure.",
    f"**Fieldwork.** At least {FIELDWORK_DAYS} consecutive days with at most {FIELDWORK_MM:g} mm "
    "each, entirely within the operation calendar. The last day of each qualifying two-day "
    "window is an eligible operation date. Spacing compares those dates in calendar days.",
    f"**Dry spell.** Consecutive days with less than {DRY_MM:g} mm inside the crop's sensitive "
    "calendar. Exactly 1 mm breaks a run. The earliest start wins ties.",
    "All date ranges include both endpoints. Results requiring missing rain or calendar "
    "information are unavailable. Soil texture is context. Actual field access, erosion and crop "
    "water stress depend on field conditions and management.",
)


@dataclass(frozen=True)
class Operation:
    event: Event
    windows: tuple[Dates, ...] | None


@dataclass(frozen=True)
class Fieldwork:
    operations: tuple[Operation, ...]
    pair_count: int | None
    example_pair: tuple[date, date] | None


@dataclass(frozen=True)
class DrySpell:
    observed: Dates | None
    complete: bool
    longest: Dates | None


@dataclass(frozen=True)
class YearResults:
    uncovered: tuple[tuple[date, float], ...] | None
    fieldwork: Fieldwork
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


def operation_windows(event: Event, rain: pd.Series) -> Operation:
    period = rain_for(rain, event.dates)
    if not complete(period):
        return Operation(event, None)
    windows = tuple(
        Dates(end.date() - DAY * (FIELDWORK_DAYS - 1), end.date())
        for end in period.index[
            period.le(FIELDWORK_MM).rolling(FIELDWORK_DAYS).sum().eq(FIELDWORK_DAYS)
        ]
    )
    return Operation(event, windows)


def fieldwork(year: CropYear, rain: pd.Series) -> Fieldwork:
    events = (year.termination, year.planting)
    operations = tuple(operation_windows(event, rain) for event in events if event)
    pair_count = example = None
    if year.minimum_gap is not None and all(op.windows is not None for op in operations):
        termination, planting = operations
        planting_days = [window.end for window in planting.windows]
        pair_count = 0
        for window in termination.windows:
            index = bisect_left(planting_days, window.end + DAY * year.minimum_gap)
            pair_count += len(planting_days) - index
            if example is None and index < len(planting_days):
                example = (window.end, planting_days[index])
    return Fieldwork(operations, pair_count, example)


def dry_spell(window: Dates, rain: pd.Series, span: Dates) -> DrySpell:
    observed = span.overlap(window)
    if observed is None:
        return DrySpell(None, False, None)
    period = rain_for(rain, observed)
    valid = pd.Series(np.isfinite(period) & period.ge(0), index=period.index)
    # Missing days break a run. A partial result can be shown with its coverage warning.
    longest = max(runs(valid & period.lt(DRY_MM)), key=lambda run: run.end - run.start, default=None)
    return DrySpell(observed, observed == window and complete(period), longest)


def analyze(calendar: Calendar, daily: pd.DataFrame) -> dict[int, YearResults]:
    rain = daily.loc[calendar.span.start:calendar.span.end, "precipitation_mm"]
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
                    outside.loc[dates.start:dates.end] = False
            uncovered = tuple((day.date(), float(value)) for day, value in period[outside].items())
        exposure = dry_spell(year.sensitive.dates, rain, calendar.span) if year.sensitive else None
        results[year.year] = YearResults(uncovered, fieldwork(year, rain), exposure)
    return results
