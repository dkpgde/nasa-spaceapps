"""Compare rotations against a farmer-selected priority."""

from dataclasses import dataclass
from html import escape
from numbers import Real
from statistics import mean

import streamlit as st


@dataclass(frozen=True)
class Measure:
    column: str
    label: str
    explanation: str
    next_step: str
    higher_is_better: bool = False
    aggregate: str = "sum"


GOALS = {
    "Keep soil covered": Measure(
        "Days with living cover", "Days with living cover",
        "More days with living crops or cover crops means more time with roots and cover in the field.",
        "Open the crop calendar to check when cover starts and ends. Check whether seeding and termination fit your operation.",
        True,
    ),
    "Reduce heavy rain on uncovered soil": Measure(
        "Heavy-rain days without living cover", "Heavy-rain days without cover",
        "Fewer heavy-rain days without a living crop or cover crop means less exposure to heavy rain.",
        "Check the heavy-rain dates against your cover-crop calendar and the fields that tend to wash or pond.",
    ),
    "Get more planting opportunities": Measure(
        "Days passing planting checks", "Planting opportunities",
        "More dates pass the rainfall and cover-crop timing checks. The four-year view averages dates per year that needs planting.",
        "Check the earliest eligible dates and field conditions before planning equipment and labor.",
        True, "average",
    ),
    "Avoid long dry spells": Measure(
        "Longest dry spell (days)", "Longest dry spell",
        "Fewer days in the worst dry spell during sensitive crop growth means shorter exposure to little rain.",
        "Open the crop calendar to see which crop and growth stage face the dry spell.",
        False, "maximum",
    ),
    "Avoid heat during sensitive growth": Measure(
        "Hot days during sensitive growth", "Hot days during sensitive growth",
        "Fewer days at or above 35 °C during sensitive growth means less exposure to heat.",
        "Check which crop and stage overlap the hottest days before choosing a planting window.",
    ),
    "Avoid low soil moisture during sensitive growth": Measure(
        "Low root-zone moisture days during sensitive growth", "Low soil moisture days",
        "Fewer days with low regional root-zone moisture during sensitive growth means less exposure to dry soil conditions.",
        "Compare these dates with moisture in your own field, especially where soil texture and drainage vary.",
    ),
    "Avoid freezing weather at planting": Measure(
        "Freezing days in planting window", "Freezing days at planting",
        "Fewer days at or below 0 °C during the planting window means less exposure to freezing air temperatures.",
        "Check local frost conditions and soil temperature before deciding when to plant.",
    ),
}
CORE_GOALS = tuple(GOALS)[:4]
SOIL_GUIDE = "https://www.nrcs.usda.gov/conservation-basics/soil/soil-health/soil-health-management"


@dataclass(frozen=True)
class Standing:
    values: dict[int, float | str]
    leaders: tuple[int, ...]

    @property
    def rated(self):
        return sum(isinstance(value, Real) for value in self.values.values())


def summarize(values, measure: Measure):
    # An established hay year can legitimately have no planting operation.
    applicable = [value for value in values if value != "N/A"]
    if not applicable:
        return "Not needed"
    if any(not isinstance(value, Real) for value in applicable):
        return "Unavailable"
    if measure.aggregate == "average":
        return mean(applicable)
    if measure.aggregate == "maximum":
        return max(applicable)
    return sum(applicable)


def rank_measures(rows, selected_year=None):
    plans = {}
    for row in rows:
        plans.setdefault(row["Plan"], []).append(row)
    standings = {}
    for goal, measure in GOALS.items():
        values = {
            plan: summarize([row[measure.column] for row in years
                             if selected_year is None or row["Year"] == selected_year], measure)
            for plan, years in plans.items()
        }
        comparable = [value for value in values.values() if isinstance(value, Real)]
        leaders = ()
        if len(comparable) > 1:
            best = (max if measure.higher_is_better else min)(comparable)
            leaders = tuple(plan for plan, value in values.items() if value == best)
        standings[goal] = Standing(values, leaders)
    return standings


def format_value(value, measure: Measure, full_rotation: bool):
    if isinstance(value, str):
        return value
    if measure.aggregate == "average" and full_rotation:
        return f"{value:.1f}".rstrip("0").rstrip(".") + " days per planting year"
    unit = "day" if value == 1 else "days"
    return f"{value:g} {unit}"


def leader_text(standing: Standing, names):
    if standing.leaders:
        return " and ".join(names[slot] for slot in standing.leaders)
    if len(standing.values) == 1:
        return "One plan selected"
    return "Too little comparable data"


def show_plan_decisions(rows, slots, year, *, iowa):
    names = {row["Plan"]: row["Name"] for row in rows}
    names = {slot: f"{name} (plan {slot})" if list(names.values()).count(name) > 1 else name
             for slot, name in names.items()}
    with st.container(border=True, key="rotation_decision"):
        st.header("Which rotation fits your goal?", anchor="choose-a-plan")
        goal_widget, period_widget = st.columns([1.2, 1])
        goal = goal_widget.selectbox("What matters most to you?", GOALS, key="rotation-goal")
        period = period_widget.radio("Years to compare", ("All four years", "Selected year"), horizontal=True,
                                    key="rotation-decision-period",
                                    format_func=lambda value: f"Only {year}" if value == "Selected year" else value)
        full_rotation = period == "All four years"
        standings = rank_measures(rows, None if full_rotation else year)
        standing, measure = standings[goal], GOALS[goal]
        st.caption(measure.explanation)
        if standing.leaders:
            headline = "Tied for the lead" if len(standing.leaders) > 1 else "Best match for this goal"
            if standing.rated < len(names):
                headline += f" · {standing.rated} of {len(names)} plans comparable"
            value = format_value(standing.values[standing.leaders[0]], measure, full_rotation)
            leaders = leader_text(standing, names)
            st.html(f'<div class="decision-answer"><p>{escape(headline)}</p><strong>{escape(leaders)}</strong>'
                    f'<span>{escape(value)} · {escape(measure.label)}</span></div>')
            st.write(f"**Before you decide** · {measure.next_step}")
        elif len(names) == 1:
            st.info("Select one more rotation above to see which plan leads.")
        else:
            st.info("This goal needs comparable results for at least two plans. Try a different goal or compare a year with data.")
        if iowa:
            st.caption("The mapped soil at Marsden Farm is poorly drained Canisteo clay loam. "
                       "Check your field’s drainage and trafficability before scheduling fieldwork. "
                       "[See the mapped soil profile](#site-observations)")
        else:
            st.caption("The Mead research site includes Yutan–Tomek soils. Check your field’s drainage "
                       "and trafficability before scheduling fieldwork.")
        st.caption(f"Living cover and rain exposure help compare soil protection. "
                   f"Use field tests to check organic matter and nutrients. [USDA NRCS soil health guidance]({SOIL_GUIDE})")
        with st.expander("See the leader for each goal"):
            st.table([{"Goal": label, "Plan with the best available result": leader_text(result, names),
                       "Plans compared": f"{result.rated} of {len(names)}"}
                      for label, result in standings.items()])

    for slot, container in slots.items():
        with container:
            show_card_summary(slot, goal, standings, full_rotation)


def show_card_summary(slot, goal, standings, full_rotation):
    standing = standings[goal]
    measure = GOALS[goal]
    target = standing.values[slot]
    if slot in standing.leaders:
        status = "Tied for the lead" if len(standing.leaders) > 1 else "Leads on your goal"
    elif not isinstance(target, Real):
        status = "Your goal · " + target
    elif standing.leaders:
        difference = abs(target - standing.values[standing.leaders[0]])
        direction = "fewer" if measure.higher_is_better else "more"
        display_difference = f"{difference:.1f}".rstrip("0").rstrip(".")
        status = f"{display_difference} {direction} {'day' if difference == 1 else 'days'} than the leader"
        if full_rotation and measure.aggregate == "average":
            status += " per planting year"
    else:
        status = "Your goal"
    goals = list(dict.fromkeys((goal, *CORE_GOALS)))
    rows = "".join(
        f"<div><dt>{escape(GOALS[label].label)}</dt>"
        f"<dd>{escape(format_value(standings[label].values[slot], GOALS[label], full_rotation))}</dd></div>"
        for label in goals
    )
    other_leads = [label for label in CORE_GOALS if label != goal and standings[label].leaders == (slot,)]
    note = f"<p>Also leads on {escape(GOALS[other_leads[0]].label.lower())}.</p>" if other_leads else ""
    tradeoffs = [label for label in CORE_GOALS if label != goal and standings[label].leaders
                 and slot not in standings[label].leaders and isinstance(standings[label].values[slot], Real)]
    if tradeoffs and slot in standing.leaders:
        note += f"<p><strong>Trade-off</strong> · Another plan does better on {escape(GOALS[tradeoffs[0]].label.lower())}.</p>"
    st.html(f'<section class="plan-decision{" plan-decision-lead" if slot in standing.leaders else ""}">'
            f'<h4>Decision summary</h4><p class="decision-status">{escape(status)}</p>'
            f'<dl>{rows}</dl>{note}</section>')
