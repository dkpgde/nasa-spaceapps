"""Streamlit editor, timeline and analysis for each comparison slot."""

from datetime import date
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from catalog import CROPS, RECIPES
from dashboard import chart_style
from fieldwork import LOW_RAIN_DAYS, MAX_DAILY_RAIN_MM
from rainfall import DRY_MM, HEAVY_MM, analyze
from rotation import DAY, DEFAULTS, EXAMPLES, Dates, Plan, expand


PLAN_TITLES = {
    "Marsden · Corn → soybean": "Corn–soybean",
    "Corn → soybean with cereal rye": "Corn–soybean + rye",
    "Marsden · Corn → soybean → oats with red clover": "Three-year with clover",
    "Marsden · Corn → soybean → oats with alfalfa → alfalfa hay": "Four-year with alfalfa",
}


def date_range(dates: Dates) -> str:
    return f"{dates.start:%b %d} – {dates.end:%b %d}"


def load_example(slot: int, prefix: str):
    example = st.session_state[f"{prefix}example"]
    st.session_state[f"plan-{slot}"] = example, EXAMPLES[example]
    # A browser rerun can still send the old widgets after the load callback.
    revision = f"{prefix}revision"
    st.session_state[revision] = st.session_state.get(revision, 0) + 1


def reset_plans():
    for slot, example in enumerate(DEFAULTS):
        prefix = f"slot-{slot}-"
        st.session_state[f"{prefix}example"] = example
        load_example(slot, prefix)


def edit_plan(slot: int) -> tuple[str, Plan]:
    prefix = f"slot-{slot}-"
    storage = f"plan-{slot}"
    example, plan = st.session_state.get(storage, (DEFAULTS[slot], EXAMPLES[DEFAULTS[slot]]))
    with st.popover("Edit plan", width="stretch", key=f"{prefix}editor"):
        st.session_state.setdefault(f"{prefix}example", example)
        st.selectbox("Start from an example", EXAMPLES, key=f"{prefix}example")
        st.button("Use this example", key=f"{prefix}load", on_click=load_example, args=(slot, prefix))
        st.divider()
        st.caption("Or change the crops below. Your edits apply immediately; the sequence repeats across four weather years.")
        revision = st.session_state.get(f"{prefix}revision", 0)
        prefix += f"edit-{revision}-"
        count = st.selectbox("Rotation length (years)", range(1, 5), index=len(plan.crops) - 1,
                             key=f"{prefix}count")
        crops = tuple(
            st.selectbox(
                f"Crop in year {phase + 1}", CROPS, format_func=lambda crop: CROPS[crop].name,
                index=list(CROPS).index(plan.crops[phase]) if phase < len(plan.crops) else 0,
                key=f"{prefix}crop-{phase}",
            )
            for phase in range(count)
        )
        start_key = f"{prefix}start"
        if st.session_state.get(start_key, 0) >= count:
            st.session_state[start_key] = 0
        start = st.selectbox(
            "First crop in the comparison", range(count), index=plan.start if plan.start < count else 0,
            format_func=lambda phase: f"{phase + 1} · {CROPS[crops[phase]].name}",
            key=start_key,
        )
        covers = []
        for phase, crop in enumerate(crops):
            following = crops[(phase + 1) % count]
            recipe = RECIPES.get((crop, following))
            key = f"{prefix}cover-{phase}-{crop}-{following}"
            selected = phase < len(plan.covers) and plan.covers[phase]
            old_recipe = None
            if selected:
                old_recipe = RECIPES.get((plan.crops[phase], plan.crops[(phase + 1) % len(plan.crops)]))
            if selected and recipe != old_recipe:
                st.warning(f"Removed the cover after phase {phase + 1} because the transition changed.")
                st.session_state.pop(key, None)
                selected = False
            covers.append(st.checkbox(
                f"{recipe.name} after year {phase + 1} → {CROPS[following].name}",
                value=selected, key=key,
            ) if recipe else False)
        for phase in range(count, len(plan.crops)):
            if plan.covers[phase]:
                st.warning(f"Removed the cover after phase {phase + 1} with that crop year.")
    edited = Plan(crops, tuple(covers), start)
    st.session_state[storage] = example, edited
    return (example if edited == EXAMPLES[example] else "Custom rotation"), edited


def render_timeline(calendar, selected_year):
    cash_crops = {crop.name for crop in CROPS.values()}
    rows = [
        {"Crop or operation": event.label, "Calendar": event.kind,
         "Start": event.dates.start, "End": event.dates.end,
         "Lane": ("Cash crop" if event.label in cash_crops else "Cover / forage")
         if event.kind == "Living cover" else event.kind,
         "Plot end": event.dates.end + DAY}
        for event in calendar.timeline()
    ]
    frame = pd.DataFrame(rows)
    kinds = ["Living cover", "Planting", "Harvest", "Seeding", "Termination", "Winterkill", "Sensitive stage"]
    lanes = [lane for lane in ("Cash crop", "Cover / forage", *kinds[1:]) if lane in frame["Lane"].values]
    palette = ["#317657", "#577da2", "#9b7451", "#7a75a5", "#a85446", "#586777", "#b1782f"]
    start, end = calendar.span.start, calendar.span.end + DAY
    axis = alt.Axis(format="%Y", values=[date(y, 1, 1).isoformat() for y in range(start.year, end.year)],
                    title=None, grid=True, ticks=False, domain=False)
    x = alt.X("Start:T", scale=alt.Scale(domain=[start.isoformat(), end.isoformat()]), axis=axis)
    active = pd.DataFrame([{"Start": date(selected_year, 1, 1), "Plot end": date(selected_year + 1, 1, 1)}])
    band = alt.Chart(active).mark_rect(color="#dae9d6", opacity=.45).encode(x=x, x2="Plot end:T")
    bars = alt.Chart(frame).mark_bar(size=10, cornerRadius=2).encode(
        x=x,
        x2="Plot end:T",
        y=alt.Y("Lane:N", scale=alt.Scale(domain=lanes), title=None,
                axis=alt.Axis(ticks=False, domain=False, labelOverlap=False)),
        color=alt.Color("Calendar:N", scale=alt.Scale(domain=kinds, range=palette), legend=None),
        tooltip=["Crop or operation:N", alt.Tooltip("Start:T", format="%Y-%m-%d"),
                 alt.Tooltip("End:T", format="%Y-%m-%d")],
    )
    chart = chart_style((band + bars).properties(background="transparent"))
    st.altair_chart(chart, theme=None, width="stretch", height=max(120, 24 * len(lanes)))
    st.dataframe(frame.drop(columns=["Lane", "Plot end"]), hide_index=True, height=220)
    st.markdown(" · ".join(f"[{label}]({url})" for label, url in calendar.sources))


def show_outcome(year, result):
    st.markdown("**Heavy rain without living cover**")
    st.caption(f"Count days with at least {HEAVY_MM:g} mm of rain when no living plants are planned. Crop residue does not count as living cover.")
    if result.uncovered is None:
        st.write("Uncovered heavy-rain count unavailable. Required living cover or rainfall data are missing.")
    else:
        st.write(f"{len(result.uncovered)} heavy-rain days outside planned living cover.")
        if result.uncovered:
            st.caption(" · ".join(f"{day:%b %d} ({rain:g} mm)" for day, rain in result.uncovered))

    st.markdown("**Planting and cover-crop removal**")
    st.caption(f"A date passes the rain check after {LOW_RAIN_DAYS} days in a row with no more than {MAX_DAILY_RAIN_MM:g} mm each day. "
               "All three days must fall inside the operation's calendar. Overlapping windows can produce consecutive eligible dates.")
    if year.planting is None:
        st.caption("Planting does not apply to an established hay year.")
    for check in result.fieldwork.operations:
        operation = check.operation
        st.write(f"{operation.label} · {date_range(operation.calendar)}")
        if check.unavailable_reason:
            st.caption(check.unavailable_reason)
        elif not check.windows:
            st.caption("No qualifying windows.")
        else:
            st.caption(" · ".join(date_range(Dates(window.start, window.operation_date)) for window in check.windows))
    for check in result.fieldwork.rules:
        st.write(f"End the cover crop at least {check.rule.minimum_days} days before planting the next crop.")
        if check.unavailable_reason:
            st.caption(check.unavailable_reason)
        elif check.feasible_dates:
            first, second = check.feasible_dates[0]
            count = len({later for _, later in check.feasible_dates})
            st.caption(f"{count} planting dates meet both checks. Example: end the cover crop on "
                       f"{first:%b %d}, then plant on {second:%b %d} ({(second - first).days} days later).")
        else:
            st.caption("No feasible pairs meet the required spacing.")

    st.markdown("**Longest dry spell**")
    st.caption(f"Count consecutive days with less than {DRY_MM:g} mm of rain during the crop's sensitive growth window. "
               "Different crops have different windows; this measures exposure to little rain, not actual crop stress.")
    dry = result.dry_spell
    if dry is None:
        st.caption("Unavailable · no fixed sensitive window sourced for this crop.")
    else:
        st.write(f"{year.sensitive.label} · {date_range(year.sensitive.dates)}")
        if not dry.complete:
            st.caption("Full-window result unavailable · incomplete weather coverage.")
        if spell := dry.longest:
            days = (spell.end - spell.start).days + 1
            prefix = "" if dry.complete else "Longest observed stretch · "
            st.caption(f"{prefix}{days} days · {date_range(spell)}")
        elif dry.complete:
            st.caption("0 qualifying days.")


def summary_metrics(year, result):
    """Keep displayed and exported values consistent, including missing results."""
    dry = result.dry_spell
    dry_days = "Unavailable"
    if dry and dry.complete:
        dry_days = (dry.longest.end - dry.longest.start).days + 1 if dry.longest else 0
    planting = next((check for check in result.fieldwork.operations if check.operation.kind == "planting"), None)
    rules = result.fieldwork.rules
    paired_dates = "N/A"
    if (planting and year.cover_unknown) or rules is None or any(check.unavailable_reason for check in rules):
        paired_dates = "Unavailable"
    elif rules:
        # A planting date can pair with several termination dates; count it once.
        eligible = [{later for _, later in check.feasible_dates} for check in rules]
        paired_dates = len(set.intersection(*eligible))
    windows = "N/A" if planting is None else "Unavailable" if planting.unavailable_reason else len(planting.windows)
    return {
        "Heavy-rain days without living cover": "Unavailable" if result.uncovered is None else len(result.uncovered),
        "Days passing planting checks": windows if paired_dates == "N/A" else paired_dates,
        f"{LOW_RAIN_DAYS}-day planting windows": windows,
        "Planting dates meeting termination gap": paired_dates,
        "Longest dry spell (days)": dry_days,
    }


def show_plan(slot, daily, span, history, selected_year):
    with st.container(border=True, key=f"plan_card_{slot}"):
        # Leave space above the editor so the summary reflects edits from this rerun.
        summary = st.container()
        label, plan = edit_plan(slot)
        calendar = expand(plan, span, history)
        results = analyze(calendar, daily)
        year = calendar.years[selected_year - span.start.year]
        result = results[selected_year]
        title = PLAN_TITLES.get(label, f"Custom plan {slot + 1}")
        values = summary_metrics(year, result)
        planting_days = values["Days passing planting checks"]
        planting_hint = "More dates give you more planting options."
        if year.minimum_gap:
            planting_hint = f"Includes the {year.minimum_gap}-day wait after ending the cover crop."
        if year.planting is None:
            planting_days, planting_hint = "Not needed", "The established hay crop does not need planting this year."
        elif planting_days == "Unavailable":
            planting_hint = "A required crop calendar, carryover rule, or weather record is missing."
        metrics = (
            ("Heavy rain without living cover", values["Heavy-rain days without living cover"],
             "Counts heavy rain while no living plants are planned."),
            ("Days passing planting checks", planting_days, planting_hint),
            ("Longest dry spell", values["Longest dry spell (days)"],
             "Days in a row with little rain during this crop's sensitive growth stage."),
        )
        with summary:
            with st.container(key=f"plan_title_{slot}"):
                st.subheader(title, anchor=False)
                st.caption(f"Growing in {selected_year}: {year.crop}")
            sequence = "".join(
                f'<li class="{"selected" if item.year == selected_year else ""}">'
                f'<span>Year {offset + 1} · {item.year}{" · selected" if item.year == selected_year else ""}</span>'
                f'<strong>{escape(item.crop)}</strong></li>'
                for offset, item in enumerate(calendar.years)
            )
            st.html(f'<ol class="crop-sequence" aria-label="Four-year crop sequence">{sequence}</ol>')
            markup = "".join(
                f'<div><dt>{name}<small>{hint}</small></dt><dd class="{"status" if isinstance(value, str) else ""}">'
                f'{value}{("<small>day</small>" if value == 1 else "<small>days</small>") if isinstance(value, int) else ""}</dd></div>'
                for name, value, hint in metrics
            )
            st.html(f'<dl class="plan-results">{markup}</dl>')
            if year.cover_unknown:
                st.caption(" · ".join(year.notes))
            if year.sensitive is None:
                st.caption("Dry-spell exposure is unavailable: no sensitive growth window is defined for this crop.")
        with st.expander("See dates, rules and sources", key=f"plan-details-{slot}", on_change="rerun") as details:
            if details.open:
                checks_tab, calendar_tab = st.tabs(("How these results are calculated", "Crop calendar and sources"))
                with checks_tab:
                    show_outcome(year, result)
                    for note in year.notes:
                        st.caption(note)
                with calendar_tab:
                    st.write(" → ".join(CROPS[plan.crop_at(offset)].name for offset in range(len(plan.crops))))
                    counts = [outcome.uncovered for outcome in results.values()]
                    total = "unavailable" if any(days is None for days in counts) else sum(len(days) for days in counts)
                    st.caption(f"Four-year uncovered heavy-rain days · {total}. Preceding crop · {calendar.previous_crop}.")
                    render_timeline(calendar, selected_year)
    rotation = " → ".join(CROPS[plan.crop_at(offset)].name for offset in range(len(plan.crops)))
    covers = "; ".join(
        f"{recipe.name} after {CROPS[plan.crop_at(offset)].name} (rotation year {offset + 1})"
        for offset in range(len(plan.crops)) if (recipe := plan.recipe_at(offset))
    )
    return [
        {"Plan": slot + 1, "Name": title, "Rotation": rotation, "Cover crops": covers or "None",
         "Year": item.year, "Crop": item.crop, **summary_metrics(item, results[item.year]),
         "Calendar notes": " ".join(item.notes)}
        for item in calendar.years
    ]
