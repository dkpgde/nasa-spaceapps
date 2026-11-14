"""Streamlit display shared by the weather demo and a plan comparison."""

import streamlit as st

from fieldwork import FieldworkResult


def show_fieldwork(result: FieldworkResult) -> None:
    operations = {}
    for check in result.operations:
        operation = check.operation
        operations[operation.id] = operation
        with st.expander(f"{operation.year} · {operation.label}"):
            if operation.calendar is not None:
                calendar = operation.calendar
                st.caption(
                    f"Operation calendar {calendar.start:%b %d}–{calendar.end:%b %d, %Y} "
                    f"· [Calendar source]({calendar.source_url})"
                )
                if calendar.note:
                    st.caption(calendar.note)
            if check.unavailable_reason:
                st.write(f"Unavailable · {check.unavailable_reason}")
            elif not check.windows:
                st.write("No qualifying rainfall windows.")
            else:
                st.table([
                    {"Window start": window.start.isoformat(),
                     "Operation date (window end)": window.operation_date.isoformat()}
                    for window in check.windows
                ])

    if result.rules is None:
        st.write("Operation order and spacing rules are unavailable.")
        return

    for check in result.rules:
        rule = check.rule
        first, second = operations[rule.first_id], operations[rule.second_id]
        st.write(
            f"**{first.label} ({first.year}) → {second.label} ({second.year})** · "
            f"Minimum gap of {rule.minimum_days} calendar days."
        )
        if rule.source_url:
            st.caption(f"[Recipe rule]({rule.source_url})")
        if check.unavailable_reason:
            st.write(f"Unavailable · {check.unavailable_reason}")
        elif not check.feasible_dates:
            st.write("No qualifying date pairs meet the order and minimum gap.")
        else:
            earlier, later = min(check.feasible_dates, key=lambda pair: pair[1] - pair[0])
            st.write(
                f"{len(check.feasible_dates)} feasible date pairs. "
                f"Example · {earlier:%b %d, %Y} → {later:%b %d, %Y} "
                f"({(later - earlier).days} days apart)."
            )
