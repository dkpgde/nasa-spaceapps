"""Dated operation calendars and sequencing rules shared by plan consumers."""

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class OperationCalendar:
    """Inclusive date bounds from a documented calendar or recipe."""

    start: date
    end: date
    source_url: str
    note: str = ""

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("Operation calendar starts after its end.")


@dataclass(frozen=True)
class Operation:
    id: str
    label: str
    year: int
    kind: Literal["planting", "termination"]
    calendar: OperationCalendar | None


@dataclass(frozen=True)
class OperationRule:
    """The first operation must precede the second by at least the given number of days."""

    first_id: str
    second_id: str
    minimum_days: int = 1
    source_url: str | None = None

    def __post_init__(self) -> None:
        if self.first_id == self.second_id or self.minimum_days < 1:
            raise ValueError("An order rule needs distinct operations and a positive day gap.")


@dataclass(frozen=True)
class PlanOperations:
    name: str
    operations: tuple[Operation, ...]
    # An empty tuple means the plan has no sequencing requirements. None means rules are missing.
    rules: tuple[OperationRule, ...] | None = ()

    def __post_init__(self) -> None:
        operation_ids = {operation.id for operation in self.operations}
        if len(operation_ids) != len(self.operations):
            raise ValueError("Operation IDs must be unique within the plan.")
        for rule in self.rules or ():
            if not {rule.first_id, rule.second_id} <= operation_ids:
                raise ValueError("Operation rules must reference operations in the same plan.")
