"""Expand cyclic plans into a shared, dated calendar."""

from dataclasses import dataclass
from datetime import date, timedelta

from catalog import CROPS, RECIPES, RYE_SPRING, Recipe, Season


DAY = timedelta(days=1)


@dataclass(frozen=True)
class Dates:
    start: date
    end: date

    def overlap(self, other: "Dates") -> "Dates | None":
        start, end = max(self.start, other.start), min(self.end, other.end)
        return Dates(start, end) if start <= end else None

    def midpoint(self) -> date:
        return self.start + DAY * ((self.end - self.start).days // 2)


def dated(season: Season, year: int) -> Dates:
    start, end = season
    return Dates(date(year, *start), date(year, *end))


@dataclass(frozen=True)
class Plan:
    crops: tuple[str, ...]
    covers: tuple[bool, ...]
    start: int = 0

    def crop_at(self, offset: int) -> str:
        return self.crops[(self.start + offset) % len(self.crops)]

    def recipe_at(self, offset: int) -> Recipe | None:
        phase = (self.start + offset) % len(self.crops)
        if self.covers[phase]:
            return RECIPES.get((self.crop_at(offset), self.crop_at(offset + 1)))
        return None


EXAMPLES = {
    "Marsden · Corn → soybean": Plan(("corn", "soy"), (False, False)),
    "Corn → soybean with cereal rye": Plan(("corn", "soy"), (True, False)),
    "Marsden · Corn → soybean → oats with red clover": Plan(
        ("corn", "soy", "clover"), (False, False, False),
    ),
    "Marsden · Corn → soybean → oats with alfalfa → alfalfa hay": Plan(
        ("corn", "soy", "oat_alfalfa", "hay"), (False, False, False, False),
    ),
}
DEFAULTS = tuple(EXAMPLES)[:3]


@dataclass(frozen=True)
class Event:
    label: str
    kind: str
    dates: Dates


@dataclass(frozen=True)
class CropYear:
    year: int
    crop: str
    events: tuple[Event, ...]
    planting: Event | None
    termination: Event | None
    minimum_gap: int | None
    sensitive: Event | None
    notes: tuple[str, ...]
    cover_unknown: bool = False


@dataclass(frozen=True)
class Calendar:
    span: Dates
    previous_crop: str
    years: tuple[CropYear, ...]
    sources: tuple[tuple[str, str], ...]

    def timeline(self):
        for year in self.years:
            for event in year.events:
                if dates := event.dates.overlap(self.span):
                    yield Event(event.label, event.kind, dates)


def termination_window(year: int, planting: Dates, gap: int) -> Dates:
    # The recipe specifies a growth stage and spacing. March 15 is a demo
    # proxy for spring green-up, and the latest planting bounds this window.
    return Dates(date(year, 3, 15), planting.end - DAY * gap)


def expand(plan: Plan, span: Dates, history: Dates | None = None) -> Calendar:
    """Include the prior phase for carryover and clip displayed events to span."""
    history = span if history is None else history
    sources = set()
    years = []
    for offset, year in enumerate(range(span.start.year, span.end.year + 1)):
        key = plan.crop_at(offset)
        previous, following = plan.crop_at(offset - 1), plan.crop_at(offset + 1)
        crop = CROPS[key]
        sources.update(crop.sources)
        events, notes = [], []
        planting = termination = sensitive = None
        gap = None
        cover_unknown = False
        harvest = dated(crop.harvest, year)

        if crop.planting:
            planting = Event(f"{crop.name} planting", "Planting", dated(crop.planting, year))
            events.append(planting)
            emergence = planting.dates.midpoint() + 7 * DAY
            label = CROPS["oats"].name if crop.undersown else crop.name
            events.append(Event(label, "Living cover", Dates(emergence, date(year, *crop.living_end))))
        if crop.sensitive:
            sensitive = Event(crop.stage, "Sensitive stage", dated(crop.sensitive, year))
            events.append(sensitive)
        events.append(Event(f"{crop.name} harvest", "Harvest", harvest))

        if crop.undersown:
            events.append(Event(crop.undersown, "Planting", planting.dates))
            events.append(Event(crop.undersown, "Living cover", Dates(emergence, date(year, 12, 31))))
            if key == "oat_alfalfa" and following != "hay":
                notes.append("Alfalfa carryover requires an established hay phase. Its exit timing for this transition is unavailable.")

        if previous == "clover":
            sources.update(CROPS[previous].sources)
            if history.start > date(year - 1, *CROPS[previous].planting[0]):
                cover_unknown = True
                notes.append("Initial red clover carryover unavailable without the preceding establishment season.")
            elif planting:
                gap = 1  # Demo spring-incorporation plan before the next planting.
                dates = termination_window(year, planting.dates, gap)
                termination = Event("Red clover incorporation", "Termination", dates)
                planned_end = min(date(year, 4, 15), planting.dates.midpoint() - DAY)
                events.append(Event("Red clover carryover", "Living cover",
                                    Dates(date(year, 1, 1), planned_end - DAY)))
            else:
                cover_unknown = True
                notes.append("Red clover termination is unavailable for this transition.")

        if previous == "oat_alfalfa" and key != "hay":
            cover_unknown = True
            notes.append("Incoming alfalfa carryover and termination are unavailable for this transition.")

        if key == "hay":
            # Consecutive hay years share the same stand when an establishment phase precedes them.
            preceding_hay_years = 0
            while preceding_hay_years < len(plan.crops) and plan.crop_at(offset - 1 - preceding_hay_years) == "hay":
                preceding_hay_years += 1
            established = plan.crop_at(offset - 1 - preceding_hay_years) == "oat_alfalfa"
            established_year = year - 1 - preceding_hay_years
            if established and history.start <= date(established_year, *CROPS["oats"].planting[0]):
                end = date(year, 12, 31)
                if following != "hay":
                    dates = dated(((11, 25), (12, 5)), year)
                    termination = Event("Alfalfa sod incorporation", "Termination", dates)
                    end = dates.midpoint() - DAY
                events.append(Event("Established alfalfa carryover", "Living cover",
                                    Dates(date(year, 1, 1), end)))
            else:
                cover_unknown = True
                notes.append("Established hay cover unavailable without a supported oats-with-alfalfa establishment phase.")

        if recipe := plan.recipe_at(offset - 1):
            if recipe.minimum_gap is not None:
                sources.update((recipe.source, RYE_SPRING))
                prior_harvest = dated(CROPS[previous].harvest, year - 1)
                seed = prior_harvest.midpoint() + DAY
                if history.start > seed or seed > date(year - 1, *recipe.seed_by):
                    cover_unknown = True
                    notes.append("Incoming rye cover and termination unavailable without a supported preceding seeding date.")
                else:
                    gap = recipe.minimum_gap
                    dates = termination_window(year, planting.dates, gap)
                    termination = Event("Cereal rye termination", "Termination", dates)
                    end = min(date(year, 4, 15), planting.dates.midpoint() - DAY * gap)
                    events.append(Event("Cereal rye carryover", "Living cover",
                                        Dates(date(year, 1, 1), end - DAY)))

        if recipe := plan.recipe_at(offset):
            sources.add(recipe.source)
            deadline = date(year, *recipe.seed_by)
            after_harvest = harvest.start + DAY
            if recipe.overseeding_from:
                seed = date(year, *recipe.overseeding_from)
                kill = date(year, *recipe.winterkill)
                events.append(Event("Fall oats overseeding into soybean", "Seeding", Dates(seed, deadline)))
                events.append(Event("Fall oats", "Living cover", Dates(seed + 7 * DAY, kill - DAY)))
                events.append(Event("Fall oats winterkill (modeled)", "Winterkill", Dates(kill, kill)))
                notes.append("Fall oats winterkill before spring. No termination or planting gap applies.")
                if after_harvest > deadline:
                    notes.append(f"Postharvest oat seeding has no overlap with the recipe deadline ({deadline:%b %d}). The plan uses overseeding.")
            elif after_harvest <= deadline:
                events.append(Event("Cereal rye seeding after harvest", "Seeding", Dates(after_harvest, deadline)))
                seed = harvest.midpoint() + DAY
                if seed <= deadline:
                    events.append(Event("Cereal rye", "Living cover",
                                        Dates(seed + 7 * DAY, date(year, 12, 31))))
                else:
                    cover_unknown = True
                    notes.append("Rye establishment unavailable at the modeled harvest date.")
                if harvest.end >= deadline:
                    notes.append(f"Rye needs a harvest before {deadline:%b %d}. Later dates in the harvest window miss the seeding deadline.")
            else:
                notes.append("Cereal rye has no postharvest seeding dates before the recipe deadline.")

        if termination:
            events.append(termination)
        years.append(CropYear(
            year, crop.name, tuple(events), planting, termination, gap, sensitive,
            tuple(notes), cover_unknown,
        ))
    return Calendar(span, CROPS[plan.crop_at(-1)].name, tuple(years), tuple(sorted(sources)))
