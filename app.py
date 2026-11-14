"""Run with: streamlit run app.py. This slice needs no weather/network access."""
from datetime import date, timedelta
import altair as alt
import pandas as pd
import streamlit as st
from rotationlab.catalog import load_catalog
from rotationlab.model import RotationPlan, expand_rotation

from fieldwork import RAIN_RULE, calculate_fieldwork
from fieldwork_demo import demo_plans
from fieldwork_view import show_fieldwork
from weather import SCENARIOS, load_weather, select_scenario


@st.cache_data
def cached_weather() -> pd.DataFrame:
    return load_weather()


st.set_page_config(page_title="RotationLab")
st.title("RotationLab")
st.caption("IOWA CROP PLANNING · SOURCED CALENDAR")
st.header("See the season before comparing the weather")
st.write("A four-year corn–soybean calendar with planned living cover and visible assumptions.")
with st.sidebar:
    st.header("Timeline settings")
    start_year = int(st.number_input("First year", min_value=1901, max_value=2096, value=2017, step=1))
    starting_crop = st.selectbox("Starting crop", ["Grain corn", "Soybean"])
    start = st.date_input("Coverage starts", date(start_year, 1, 1),
                          min_value=date(start_year, 1, 1), max_value=date(start_year + 3, 12, 31), key=f"start-{start_year}")
    end = st.date_input("Coverage ends", date(start_year + 3, 12, 31),
                        min_value=date(start_year, 1, 1), max_value=date(start_year + 3, 12, 31), key=f"end-{start_year}")
    st.caption("Dates are supplied independently of NASA weather retrieval. Partial coverage clips the calendar.")
if start > end or start.year != start_year:
    st.error("Coverage must start in the first year and end on or after its start.")
    st.stop()
plan = RotationPlan("Corn → soybean", ("grain_corn", "soybean"),
                    0 if starting_crop == "Grain corn" else 1, ("marsden",))
timeline = expand_rotation(plan, start, end, calendars)
location, soil = data["location"], data["soil"]
a, b, c = st.columns(3)
a.metric("Representative location", "Boone County, IA")
a.caption(f"Marsden study area · {location['latitude']:.4f}, {location['longitude']:.4f}")
b.metric("Surface texture", soil["texture"])
b.caption(soil["name"])
c.metric("Available calendar coverage", f"{start.year}–{end.year}")
c.caption(f"{start.isoformat()} → {end.isoformat()} · inclusive")
st.subheader("Crop sequence")
st.write(" → ".join(f"{y.year} {calendars[y.crop_id].name}" for y in timeline.years))
st.caption(f"Preceding phase: {calendars[timeline.years[0].preceding_crop_id].name}. "
           "This annual rotation has no overwinter living cover; preceding crop residue is not counted.")

latitude, longitude = scenario.coordinates
st.caption(f"{scenario.location} · {latitude:.4f}°, {longitude:.4f}°")
totals = scenario.seasonal_totals
st.subheader(f"Weather block · {totals.index[0]}–{totals.index[-1]}")
st.write(f"**{scenario.reference_year}** is the reference year at position **{scenario.reference_position}**.")

season_columns = {
    "year": "Calendar year",
    "spring_mm": st.column_config.NumberColumn("March–May (mm)", format="%.2f"),
    "summer_mm": st.column_config.NumberColumn("June–August (mm)", format="%.2f"),
}
block = totals.reset_index()
block.insert(0, "Rotation year", range(1, len(block) + 1))
st.dataframe(block, hide_index=True, column_config=season_columns)

first, last = scenario.reference_period
st.subheader("Selection evidence")
st.write(scenario.rule)
st.caption(
    f"Historical reference period {first}–{last}. An eligible year must fit "
    f"at position {scenario.reference_position} in a complete four-year block."
)
medians = scenario.historical_totals.median()
st.write(
    f"Historical medians are **{medians['spring_mm']:.2f} mm** for March–May "
    f"and **{medians['summer_mm']:.2f} mm** for June–August."
)
with st.expander("Historical seasonal totals"):
    st.dataframe(
        scenario.historical_totals.reset_index(), hide_index=True, column_config=season_columns
    )

with st.expander("Daily weather records"):
    st.dataframe(
        scenario.daily.reset_index(),
        hide_index=True,
        column_config={
            "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "precipitation_mm": st.column_config.NumberColumn("Precipitation (mm)", format="%.2f"),
            "temperature_c": st.column_config.NumberColumn("Mean air temperature (°C)", format="%.2f"),
        },
    )

st.caption(f"[NASA POWER daily data]({scenario.source_url}) · MERRA-2 · Local Solar Time")

st.subheader("Rainfall-based fieldwork windows")
st.caption(RAIN_RULE)
st.caption(
    "This demo uses rainfall as a screening rule. Field access also depends on soil, "
    "drainage, and management."
)
plans = demo_plans(tuple(int(year) for year in totals.index))
for tab, plan in zip(st.tabs([plan.name for plan in plans]), plans):
    with tab:
        show_fieldwork(calculate_fieldwork(plan, scenario.daily["precipitation_mm"]))
