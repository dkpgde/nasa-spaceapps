"""Compare soil-cover and fieldwork indicators across the selected rotations."""

from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from dashboard import chart_style
from fieldwork import LOW_RAIN_DAYS, MAX_DAILY_RAIN_MM
from rainfall import DRY_MM, HEAVY_MM, HOT_C, LOW_MOISTURE_PERCENTILE


SOIL_HEALTH_SOURCE = "https://www.nrcs.usda.gov/conservation-basics/soil/soil-health/soil-health-management"
PLAN_COLORS = {1: "#277357", 2: "#286d91", 3: "#9b5b1f"}
INDICATORS = {
    "Days with living cover": (
        "Days in the year with a living cash crop, cover crop, or established forage, according to the crop calendar. "
        "A day with overlapping crops counts once."
    ),
    "Longest stretch without living cover": (
        "The longest run of days within the year without planned living plants. Crop residue can still protect the soil."
    ),
    "Heavy-rain days without living cover": (
        f"Days with at least {HEAVY_MM:g} mm of rain when the calendar shows no living plants. "
        "Compare exposure to heavy rain across rotations using the same weather."
    ),
    "Days passing planting checks": (
        f"Eligible dates after {LOW_RAIN_DAYS} consecutive days with at most {MAX_DAILY_RAIN_MM:g} mm of rain per day "
        "within the planting window. Any required gap after ending a cover crop also applies."
    ),
    "Longest dry spell (days)": (
        f"Consecutive days with less than {DRY_MM:g} mm of rain during each crop’s sensitive growth window. "
        "The crop determines which dates are checked."
    ),
    "Freezing days in planting window": (
        "Days with a minimum air temperature at or below 0 °C within the planned planting calendar. "
        "Uses PRISM minimum temperature when PRISM is selected and NASA POWER for the other historical settings."
    ),
    "Hot days during sensitive growth": (
        f"Days with a maximum air temperature of at least {HOT_C:g} °C during the crop’s sensitive growth window. "
        "This is a common comparison threshold across plans. It measures heat exposure."
    ),
    "Low root-zone moisture days during sensitive growth": (
        f"Days when the regional NASA SMAP root-zone moisture falls below its {LOW_MOISTURE_PERCENTILE:g}th percentile "
        "during the crop’s sensitive growth window. All plans share the same regional observations for those dates."
    ),
}


def show_impact_explorer(export: pd.DataFrame, selected_year: int):
    with st.container(border=True, key="impact_explorer"):
        st.html("""
            <div class="impact-heading">
                <h3>Rotation impacts</h3>
                <p>Compare soil cover, heavy rain, planting opportunities, and dry spells under the same weather.</p>
            </div>
        """)
        with st.container(key="impact_controls"):
            metric, period = st.columns([1.15, 1])
            indicator = metric.selectbox("Indicator", INDICATORS, key="impact-indicator")
            view = period.segmented_control("Years to chart", ("All four years", "Selected year"),
                                            default="All four years", key="impact-years")
        st.write(INDICATORS[indicator])

        focus = export.loc[export["Year"].eq(selected_year), ["Plan", "Name", indicator]]
        snapshots = []
        for slot, name, value in focus.itertuples(index=False, name=None):
            display = "Not needed" if value == "N/A" else str(value)
            unit = (" day" if value == 1 else " days") if isinstance(value, (int, float)) else ""
            snapshots.append(
                f'<div style="--series-color:{PLAN_COLORS[slot]}"><dt>{escape(name)}</dt>'
                f'<dd>{escape(display)}<span>{unit}</span></dd></div>'
            )
        st.html(f"""
            <div class="impact-snapshot">
                <p>{selected_year} · Selected year</p>
                <dl aria-label="{selected_year} {escape(indicator)}">{''.join(snapshots)}</dl>
            </div>
        """)

        frame = export[["Plan", "Name", "Year", "Crop", indicator]].rename(columns={indicator: "Result"})
        if view == "Selected year":
            frame = frame.loc[frame["Year"].eq(selected_year)].copy()
        frame["Days"] = pd.to_numeric(frame["Result"], errors="coerce")
        available = frame.dropna(subset=["Days"])[["Plan", "Name", "Year", "Crop", "Days"]]
        if not available.empty:
            slots = focus["Plan"].tolist()
            years = sorted(frame["Year"].unique().tolist())
            pinned_year = alt.selection_point(name="Highlight", fields=["Year"], on="click")
            hover_year = alt.selection_point(name="Inspect", fields=["Year"], on="pointerover", clear="pointerout")
            chart = alt.Chart(available).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X("Year:O", title=None, scale=alt.Scale(domain=years), axis=alt.Axis(labelAngle=0)),
                xOffset=alt.XOffset("Plan:N", scale=alt.Scale(domain=slots)),
                y=alt.Y("Days:Q", title="Days", axis=alt.Axis(tickCount=5, tickMinStep=1)),
                color=alt.Color("Plan:N", scale=alt.Scale(domain=slots, range=[PLAN_COLORS[slot] for slot in slots]),
                                legend=None),
                opacity=alt.condition(pinned_year & hover_year, alt.value(1), alt.value(.45)),
                tooltip=[alt.Tooltip("Name:N", title="Rotation"), "Year:O", "Crop:N", "Days:Q"],
            ).add_params(pinned_year, hover_year).properties(background="transparent")
            st.altair_chart(chart_style(chart), width="stretch", height=240, theme=None)
        else:
            st.info("This indicator is unavailable for the selected plans and years.")
        with st.expander("View exact values"):
            values = frame[["Name", "Year", "Crop", "Result"]].copy()
            values["Result"] = values["Result"].replace("N/A", "Not needed").astype(str)
            st.dataframe(
                values,
                column_config={"Name": "Rotation", "Result": indicator, "Year": st.column_config.NumberColumn(format="%d")},
                hide_index=True,
            )
        st.caption("Living cover and heavy-rain exposure are indicators of soil protection. Tracking changes in "
                   "organic matter, nutrients, or erosion requires field measurements. "
                   f"[USDA NRCS soil health principles]({SOIL_HEALTH_SOURCE})")
