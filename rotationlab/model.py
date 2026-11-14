"""Weather-independent rotation expansion. All date intervals are inclusive."""
from dataclasses import dataclass, field
from datetime import date, timedelta
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
class CoverRecipe:
    crop_id: str
    name: str
    preceding_crop_id: str
    following_crop_id: str
    source: str
    seed_before: str  # exclusive MM-DD in the preceding crop year
    termination_from: str  # illustrative MM-DD in the following crop year
    minimum_days_before_planting: int
    establishment_days: int  # illustrative lag between seeding and living cover
    termination_guidance: str

    def matches(self, preceding_crop_id, following_crop_id):
        return (preceding_crop_id, following_crop_id) == (
            self.preceding_crop_id, self.following_crop_id
        )


@dataclass(frozen=True)
class RotationPlan:
    name: str
    crop_years: Tuple[str, ...]
    starting_phase: int = 0  # zero-based phase in the first supplied calendar year
    sources: Tuple[str, ...] = ()
    custom: bool = False
    cover_recipes: Tuple[CoverRecipe, ...] = ()

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
class CoverTransition:
    recipe: CoverRecipe
    harvest_year: int
    planting_year: int
    seeding: WindowResult
    living_cover: WindowResult
    termination: WindowResult


@dataclass(frozen=True)
class ExpandedTimeline:
    plan: RotationPlan
    start: date
    end: date
    years: Tuple[CropYear, ...]
    windows: Tuple[DatedWindow, ...]
    availability: Mapping[Tuple[int, str, str], WindowResult]

    cover_transitions: Tuple[CoverTransition, ...] = ()

    def query(self, year, crop_id, kind):
        """Fail closed for an unknown year, crop, or rule category."""
        return self.availability.get((year, crop_id, kind), WindowResult(
            Availability.UNAVAILABLE, (), "No calendar/rule for this crop, year, and category"))


def _recipe_window(recipe, year, kind, label, a, b, lo, hi, assumption, sources,
                   carryover=False):
    left, right = max(a, lo), min(b, hi)
    if left > right:
        return WindowResult(Availability.AVAILABLE, ())
    return WindowResult(Availability.AVAILABLE, (
        DatedWindow(recipe.crop_id, year, kind, label, left, right,
                    sources, assumption, a, b, carryover),
    ))


def _rules_for(calendar, kind):
    if calendar is None or calendar.rules is None or kind in calendar.unavailable_rules:
        return ()
    return tuple(rule for rule in calendar.rules if rule.kind == kind)


def _cover_transition(recipe, harvest_year, start, lo, hi, calendars):
    planting_year = harvest_year + 1
    planting = _rules_for(calendars.get(recipe.following_crop_id), "planting")
    harvest = _rules_for(calendars.get(recipe.preceding_crop_id), "harvest")
    cutoff = date.fromisoformat(f"{harvest_year}-{recipe.seed_before}")
    last_seed = cutoff - timedelta(days=1)

    if not harvest:
        seeding = WindowResult(Availability.UNAVAILABLE, (), "No sourced preceding harvest calendar.")
    else:
        harvest_start = min(rule.bounds(harvest_year)[0] for rule in harvest)
        harvest_end = max(rule.bounds(harvest_year)[1] for rule in harvest)
        first_seed = harvest_start + timedelta(days=1)
        latest_harvest = last_seed - timedelta(days=1)
        seeding = _recipe_window(
            recipe, harvest_year, "seeding", f"Seed {recipe.name}", first_seed, last_seed,
            lo, hi,
            f"Seed as soon as possible after harvest and before {cutoff:%B %d}. "
            "The demo allows seeding from the next calendar day after harvest. "
            f"Usual harvest runs {harvest_start:%b %d}–{harvest_end:%b %d}; "
            f"the latest compatible harvest date is {latest_harvest:%b %d}.",
            (recipe.source, *dict.fromkeys(source for rule in harvest for source in rule.sources)),
        )

        if first_seed > last_seed:
            seeding = WindowResult(Availability.AVAILABLE, (), "Harvest starts after the last compatible harvest date.")

    if seeding.availability == Availability.UNAVAILABLE:
        termination = WindowResult(Availability.UNAVAILABLE, (), seeding.reason)
    elif seeding.reason:
        termination = WindowResult(Availability.AVAILABLE, (), seeding.reason)
    elif not planting:
        termination = WindowResult(Availability.UNAVAILABLE, (), "No sourced following planting calendar.")
    else:
        first_termination = date.fromisoformat(f"{planting_year}-{recipe.termination_from}")
        last_planting = max(rule.bounds(planting_year)[1] for rule in planting)
        last_termination = last_planting - timedelta(days=recipe.minimum_days_before_planting)
        termination = _recipe_window(
            recipe, planting_year, "termination", f"Terminate {recipe.name}",
            first_termination, last_termination, lo, hi,
            f"The demo starts checking on {first_termination:%B %d}. "
            f"Allow at least {recipe.minimum_days_before_planting} calendar days before planting. "
            f"{recipe.termination_guidance}",
            (recipe.source, *dict.fromkeys(source for rule in planting for source in rule.sources)),
        )

        if first_termination > last_termination:
            termination = WindowResult(Availability.AVAILABLE, (), "The planting calendar leaves no eligible termination date.")

    if termination.reason:
        cover = WindowResult(termination.availability, (), termination.reason)
    else:
        cover = _recipe_window(
            recipe, harvest_year, "living_cover", f"{recipe.name} · planned living cover",
            last_seed + timedelta(days=recipe.establishment_days),
            first_termination - timedelta(days=1), lo, hi,
            f"The demo assumes establishment {recipe.establishment_days} days after the last "
            "eligible seeding date and ends planned cover before the earliest spring termination. "
            "Cover is conditional on timely seeding and establishment.",
            (recipe.source,), carryover=harvest_year < start.year,
        )
    return CoverTransition(recipe, harvest_year, planting_year, seeding, cover, termination)


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
    transitions = []
    for year in range(start.year - 1, end.year + 1):
        phase = (plan.starting_phase + year - start.year) % len(plan.crop_years)
        preceding = plan.crop_years[phase]
        following = plan.crop_years[(phase + 1) % len(plan.crop_years)]
        for recipe in plan.cover_recipes:
            if not recipe.matches(preceding, following):
                continue
            transition = _cover_transition(recipe, year, start, lo, hi, calendars)
            transitions.append(transition)
            for crop_year, kind, result in (
                (year, "seeding", transition.seeding),
                (year, "living_cover", transition.living_cover),
                (year + 1, "termination", transition.termination),
            ):
                availability[(crop_year, recipe.crop_id, kind)] = result
                windows.extend(result.intervals)
    return ExpandedTimeline(plan, start, end, tuple(years), tuple(windows), availability,
                            tuple(transitions))
