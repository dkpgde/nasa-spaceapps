"""Operation-only examples for the weather screen and fieldwork acceptance check."""

from datetime import date, timedelta

from plan import Operation, OperationCalendar, OperationRule, PlanOperations


PLANTING_SOURCE = (
    "https://crops.extension.iastate.edu/post/corn-and-soybean-planting-date-considerations"
)
RYE_SOURCE = "https://store.extension.iastate.edu/product/15548.pdf"
# The starter recipe says more than 10 days. The first valid whole-day gap is 11.
RYE_MINIMUM_DAYS = 11


def demo_plans(years: tuple[int, ...]) -> tuple[PlanOperations, PlanOperations]:
    """Expand corn–soybean and its rye variant across the selected weather block."""
    planting = []
    termination = []
    rules = []
    for position, year in enumerate(years):
        if position % 2 == 0:
            planting.append(
                Operation(
                    f"{year}-corn", "Plant grain corn", year, "planting",
                    OperationCalendar(date(year, 4, 11), date(year, 5, 18), PLANTING_SOURCE),
                )
            )
            continue

        soybean = OperationCalendar(
            date(year, 4, 12), date(year, 5, 20), PLANTING_SOURCE,
            "The demo uses the day after April 11 through the May 20 planting target.",
        )
        planting.append(Operation(f"{year}-soybean", "Plant soybean", year, "planting", soybean))
        termination.append(
            Operation(
                f"{year}-rye", "Terminate cereal rye", year, "termination",
                OperationCalendar(
                    date(year, 4, 1), soybean.end - timedelta(days=RYE_MINIMUM_DAYS), RYE_SOURCE,
                    "The demo starts the search on April 1 and ends it 11 days before the "
                    "last soybean planting date. The recipe also calls for scouting rye height "
                    "and active growth, which this date check does not evaluate.",
                ),
            )
        )
        rules.append(
            OperationRule(f"{year}-rye", f"{year}-soybean", RYE_MINIMUM_DAYS, RYE_SOURCE)
        )

    rye_operations = sorted(
        planting + termination, key=lambda operation: (operation.year, operation.kind != "termination")
    )
    return (
        PlanOperations("Corn → soybean", tuple(planting)),
        PlanOperations("Corn → soybean with cereal rye", tuple(rye_operations), tuple(rules)),
    )
