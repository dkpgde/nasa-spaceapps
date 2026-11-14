"""Weather-independent rotation expansion. All date intervals are inclusive."""
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional, Tuple, Mapping


class Availability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class WindowRule:
    kind: str
    label: str
    start: str  # MM-DD, relative to the crop year
    end: str
    sources: Tuple[str, ...]
    assumption: str = ""
    start_year_offset: int = 0
    end_year_offset: int = 0

    def __post_init__(self):
        if not self.sources:
            raise ValueError("Every rule needs a source reference")
        if self.bounds(2000)[0] > self.bounds(2000)[1]:
            raise ValueError("Rule start must precede end")

    def bounds(self, year):
        return (date.fromisoformat(f"{year + self.start_year_offset:04d}-{self.start}"),
                date.fromisoformat(f"{year + self.end_year_offset:04d}-{self.end}"))


@dataclass(frozen=True)
class CropCalendar:
    crop_id: str
    name: str
    # None means unavailable; () means known, valid, and empty.
    rules: Optional[Tuple[WindowRule, ...]]
    unavailable_reason: str = ""
    unavailable_rules: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RotationPlan:
    name: str
    crop_years: Tuple[str, ...]
    starting_phase: int = 0  # zero-based phase in the first supplied calendar year
    sources: Tuple[str, ...] = ()
    custom: bool = False

    def __post_init__(self):
        if not 1 <= len(self.crop_years) <= 4:
            raise ValueError("A rotation must contain one to four ordered crop years")
        if not 0 <= self.starting_phase < len(self.crop_years):
            raise ValueError("Starting phase is outside the rotation")


@dataclass(frozen=True)
class DatedWindow:
    crop_id: str
    crop_year: int
    kind: str
    label: str
    start: date
    end: date
    sources: Tuple[str, ...]
    assumption: str
    original_start: date
    original_end: date
    carryover: bool


@dataclass(frozen=True)
class CropYear:
    year: int
    phase: int
    crop_id: str
    preceding_crop_id: str


@dataclass(frozen=True)
class WindowResult:
    availability: Availability
    intervals: Tuple[DatedWindow, ...]
    reason: str = ""


@dataclass(frozen=True)
class ExpandedTimeline:
    plan: RotationPlan
    start: date
    end: date
    years: Tuple[CropYear, ...]
    windows: Tuple[DatedWindow, ...]
    availability: Mapping[Tuple[int, str, str], WindowResult]

    def query(self, year, crop_id, kind):
        """Fail closed for an unknown year, crop, or rule category."""
        return self.availability.get((year, crop_id, kind), WindowResult(
            Availability.UNAVAILABLE, (), "No calendar/rule for this crop, year, and category"))


KINDS = ("crop", "planting", "harvest", "living_cover", "sensitive", "termination")


def expand_rotation(plan, start, end, calendars, coverage=None):
    """Anchor phase to start.year; clip to supplied dates AND available coverage.

    coverage is an inclusive pair, e.g. complete weather coverage supplied by #2.
    Prior-year cover is generated only from explicit rules, never from residue.
    """
    if start > end:
        raise ValueError("Start date must not be after end date")
    if end.year - start.year > 3:
        raise ValueError("Supply at most four calendar years")
    lo, hi = start, end
    if coverage is not None:
        if coverage[0] > coverage[1]:
            raise ValueError("Coverage start must not be after coverage end")
        lo, hi = max(lo, coverage[0]), min(hi, coverage[1])
    years, windows, availability = [], [], {}
    # Include the preceding phase so explicitly sourced carryover can be clipped.
    for year in range(start.year - 1, end.year + 1):
        phase = (plan.starting_phase + year - start.year) % len(plan.crop_years)
        crop_id = plan.crop_years[phase]
        if year >= start.year:
            years.append(CropYear(year, phase, crop_id, plan.crop_years[(phase - 1) % len(plan.crop_years)]))
        calendar = calendars.get(crop_id)
        for kind in KINDS:
            if calendar is None or calendar.rules is None or kind in calendar.unavailable_rules:
                reason = (calendar.unavailable_rules.get(kind, calendar.unavailable_reason)
                          if calendar else f"No sourced calendar for {crop_id}")
                availability[(year, crop_id, kind)] = WindowResult(Availability.UNAVAILABLE, (), reason)
                continue
            matches = []
            for rule in calendar.rules:
                if rule.kind != kind:
                    continue
                a, b = rule.bounds(year)
                left, right = max(a, lo), min(b, hi)
                if left > right or (year < start.year and kind != "living_cover"):
                    continue
                interval = DatedWindow(crop_id, year, kind, rule.label, left, right,
                                       rule.sources, rule.assumption, a, b, year < start.year)
                matches.append(interval)
                windows.append(interval)
            availability[(year, crop_id, kind)] = WindowResult(Availability.AVAILABLE, tuple(matches))
    return ExpandedTimeline(plan, start, end, tuple(years), tuple(windows), availability)
