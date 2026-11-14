"""Adapt shared rotation timelines to the dated fieldwork interface."""

from datetime import date

from plan import Operation, OperationCalendar, OperationRule, PlanOperations
from rotationlab.catalog import load_catalog, load_cover_recipes
from rotationlab.model import RotationPlan, expand_rotation


CORN_SOYBEAN = "Corn → soybean"
CORN_SOYBEAN_RYE = "Corn → soybean with cereal rye"


def corn_soybean_plans(starting_phase, recipes):
    crops = ("grain_corn", "soybean")
    matching = tuple(recipe for recipe in recipes if recipe.matches(*crops))
    return (
        RotationPlan(CORN_SOYBEAN, crops, starting_phase, ("marsden",)),
        RotationPlan(CORN_SOYBEAN_RYE, crops, starting_phase,
                     tuple(recipe.source for recipe in matching), cover_recipes=matching),
    )


def _operation_calendar(result, sources):
    if len(result.intervals) != 1:
        return None
    window = result.intervals[0]
    # Fieldwork checks the full sourced window and reports incomplete rainfall where appropriate.
    return OperationCalendar(window.original_start, window.original_end,
                             sources[window.sources[0]]["url"], window.assumption)


def timeline_operations(timeline, calendars, sources):
    """Use the same calendar dates and recipe as the visible timeline."""
    operations, rules = [], []
    transitions = {transition.planting_year: transition for transition in timeline.cover_transitions}
    for year in timeline.years:
        planting_id = f"{year.year}-{year.crop_id}-planting"
        transition = transitions.get(year.year)
        if transition:
            recipe = transition.recipe
            termination_id = f"{year.year}-{recipe.crop_id}-termination"
            operations.append(Operation(
                termination_id, f"Terminate {recipe.name.lower()}", year.year, "termination",
                _operation_calendar(transition.termination, sources),
            ))
            rules.append(OperationRule(termination_id, planting_id,
                                       recipe.minimum_days_before_planting,
                                       sources[recipe.source]["url"]))

        calendar = calendars.get(year.crop_id)
        crop_name = calendar.name.lower() if calendar else year.crop_id
        operations.append(Operation(
            planting_id, f"Plant {crop_name}", year.year, "planting",
            _operation_calendar(timeline.query(year.year, year.crop_id, "planting"), sources),
        ))
    return PlanOperations(timeline.plan.name, tuple(operations), tuple(rules))


def demo_plans(years: tuple[int, ...], starting_phase: int = 0) -> tuple[PlanOperations, ...]:
    """Build fieldwork plans for the selected cached weather block."""
    data, calendars = load_catalog()
    start, end = date(years[0], 1, 1), date(years[-1], 12, 31)
    return tuple(
        timeline_operations(expand_rotation(plan, start, end, calendars), calendars, data["sources"])
        for plan in corn_soybean_plans(starting_phase, load_cover_recipes(data))
    )
