"""Rainfall-only fieldwork checks for dated plan operations."""

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from plan import Operation, OperationRule, PlanOperations


MAX_DAILY_RAIN_MM = 1.0
LOW_RAIN_DAYS = 3
RAIN_RULE = (
    f"A qualifying window is {LOW_RAIN_DAYS} consecutive days with daily rainfall "
    f"of {MAX_DAILY_RAIN_MM:g} mm or less on every day. The operation date is the last day. "
    "The full window must fit within the operation calendar, including its start and end dates. "
    "Dates use the NASA POWER local solar day."
)


@dataclass(frozen=True)
class FieldworkWindow:
    start: date
    operation_date: date


@dataclass(frozen=True)
class OperationResult:
    operation: Operation
    windows: tuple[FieldworkWindow, ...]
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class RuleResult:
    rule: OperationRule
    feasible_dates: tuple[tuple[date, date], ...]
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class FieldworkResult:
    operations: tuple[OperationResult, ...]
    # None means rule data is unavailable. An empty tuple means no rules apply.
    rules: tuple[RuleResult, ...] | None


def _operation_windows(operation: Operation, rain_mm: pd.Series) -> OperationResult:
    calendar = operation.calendar
    if calendar is None:
        return OperationResult(operation, (), "Operation calendar unavailable.")

    dates = pd.date_range(calendar.start, calendar.end, freq="D")
    values = rain_mm.reindex(dates).to_numpy(dtype=float, na_value=np.nan)
    if not (np.isfinite(values) & (values >= 0)).all():
        return OperationResult(operation, (), "Daily rainfall is incomplete for this calendar.")

    windows = []
    dry_days = 0
    lookback = timedelta(days=LOW_RAIN_DAYS - 1)
    for day, rainfall in zip(dates.date, values):
        dry_days = dry_days + 1 if rainfall <= MAX_DAILY_RAIN_MM else 0
        if dry_days >= LOW_RAIN_DAYS:
            windows.append(FieldworkWindow(day - lookback, day))
    return OperationResult(operation, tuple(windows))


def _check_rule(rule: OperationRule, first: OperationResult, second: OperationResult) -> RuleResult:
    if first.unavailable_reason or second.unavailable_reason:
        return RuleResult(rule, (), "One or both operations lack complete source data.")

    gap = timedelta(days=rule.minimum_days)
    pairs = tuple(
        (earlier.operation_date, later.operation_date)
        for earlier in first.windows
        for later in second.windows
        if later.operation_date - earlier.operation_date >= gap
    )
    return RuleResult(rule, pairs)


def calculate_fieldwork(plan: PlanOperations, rain_mm: pd.Series) -> FieldworkResult:
    """Use one shared dated precipitation series in mm to check a plan's operations."""
    operations = tuple(_operation_windows(operation, rain_mm) for operation in plan.operations)
    if plan.rules is None:
        return FieldworkResult(operations, None)

    by_id = {result.operation.id: result for result in operations}
    rules = tuple(
        _check_rule(rule, by_id[rule.first_id], by_id[rule.second_id]) for rule in plan.rules
    )
    return FieldworkResult(operations, rules)
