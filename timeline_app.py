"""Run with: streamlit run app.py. Uses bundled NASA POWER weather."""
from datetime import date, timedelta
import altair as alt
import pandas as pd
import streamlit as st
from rotationlab.catalog import load_catalog, load_cover_recipes
from rotationlab.model import expand_rotation

from fieldwork import RAIN_RULE, calculate_fieldwork
from fieldwork_demo import corn_soybean_plans, timeline_operations
from fieldwork_view import show_fieldwork
from weather import SCENARIOS, load_weather, select_scenario
from dashboard import load_styles


@st.cache_data
def cached_weather() -> pd.DataFrame:
    return load_weather()


st.set_page_config(page_title="RotationLab · Crop timeline", page_icon="🌱", layout="wide")
load_styles()
data, calendars = load_catalog()
st.html('<div class="brand-eyebrow"><span class="brand-mark">↗</span> FIELD NOTES / IOWA <span class="source-badge">CROP CALENDAR</span></div>')
st.title("RotationLab")
st.caption("IOWA CROP PLANNING · SOURCED CALENDAR")
st.header("See the season before comparing the weather")
st.write("A four-year corn–soybean calendar with planned living cover and visible assumptions.")
with st.sidebar:
    st.header("Timeline settings")
    start_year = int(st.number_input("First year", min_value=1901, max_value=2096, value=2017, step=1))
    starting_crop = st.selectbox("Starting crop", ["Grain corn", "Soybean"])
    starting_phase = 0 if starting_crop == "Grain corn" else 1
    plans = corn_soybean_plans(starting_phase, load_cover_recipes(data))
    selected = st.selectbox("Rotation example", [plan.name for plan in plans])
    start = st.date_input("Coverage starts", date(start_year, 1, 1),
                          min_value=date(start_year, 1, 1), max_value=date(start_year + 3, 12, 31), key=f"start-{start_year}")
    end = st.date_input("Coverage ends", date(start_year + 3, 12, 31),
                        min_value=date(start_year, 1, 1), max_value=date(start_year + 3, 12, 31), key=f"end-{start_year}")
    st.caption("Dates are supplied independently of NASA weather retrieval. Partial coverage clips the calendar.")
if start > end or start.year != start_year:
    st.error("Coverage must start in the first year and end on or after its start.")
    st.stop()
plan = next(plan for plan in plans if plan.name == selected)
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
st.caption(f"Preceding phase: {calendars[timeline.years[0].preceding_crop_id].name}.")
if plan.cover_recipes:
    st.caption("Cereal rye applies to grain corn → soybean transitions, including the preceding phase when the rotation starts with soybean.")

labels = {"planting": "Planting window", "harvest": "Usual harvest window",
          "seeding": "Rye seeding window", "living_cover": "Planned living cover",
          "termination": "Rye termination window", "sensitive": "Sensitive growth window"}
crop_names = {crop_id: calendar.name for crop_id, calendar in calendars.items()}
crop_names.update({recipe.crop_id: recipe.name for recipe in plan.cover_recipes})
rows = [{"Crop year": f"{w.crop_year} · {crop_names[w.crop_id]}" + (" (carryover)" if w.carryover else ""),
         "Window": labels[w.kind], "Start": w.start.isoformat(), "End": w.end.isoformat(),
         "Plot end": (w.end + timedelta(days=1)).isoformat(),
         "Basis": w.assumption, "Sources": ", ".join(w.sources)}
        for w in sorted(timeline.windows, key=lambda window: window.crop_year) if w.kind in labels]
st.subheader("Calendar & planned living cover")
st.caption("Green indicates planned living cover. Other bars show operation ranges and a sensitive-stage date proxy. "
           "Rye bars represent a conditional plan based on timely seeding and establishment.")
frame = pd.DataFrame(rows)
if rows:
    chart = alt.Chart(frame).mark_bar(cornerRadius=3, height=11).encode(
        x=alt.X("Start:T", title=None, scale=alt.Scale(domain=[start.isoformat(), (end + timedelta(days=1)).isoformat()]), axis=alt.Axis(format="%b %Y", labelAngle=-35)),
        x2="Plot end:T", y=alt.Y("Crop year:N", sort=None, title=None),
        yOffset=alt.YOffset("Window:N", sort=list(labels.values())),
        color=alt.Color("Window:N", scale=alt.Scale(domain=list(labels.values()), range=["#d6a33d", "#a77950", "#6184ac", "#39865a", "#ad6656", "#7867ad"]), legend=alt.Legend(orient="bottom", title=None, columns=2, labelLimit=0, columnPadding=14)),
        tooltip=["Crop year:N", "Window:N", "Start:N", "End:N", "Basis:N", "Sources:N"]
    ).properties(height=max(170, 60 * frame["Crop year"].nunique()))
    st.altair_chart(chart)
else:
    st.info("The supplied coverage contains no calendar intervals. The rules are available; the clipped result is empty.")
st.info("Living-cover and sensitive-window dates are fixed demo assumptions, not measured crop stages. "
        "This timeline does not estimate yield, soil moisture, erosion or actual field access.")
with st.expander("Inspect exact dates and assumptions", expanded=False):
    st.dataframe(frame.drop(columns=["Plot end"]) if rows else frame, hide_index=True)
    st.download_button("Download interval dates (CSV)", frame.drop(columns=["Plot end"]).to_csv(index=False) if rows else "", "rotationlab-timeline.csv", "text/csv")
if timeline.cover_transitions:
    with st.expander("Cereal rye transitions & availability", expanded=True):
        transitions = []
        for transition in timeline.cover_transitions:
            row = {"Transition": f"{transition.harvest_year} corn → {transition.planting_year} soybean"}
            for heading, result in (("Seeding", transition.seeding), ("Living cover", transition.living_cover),
                                    ("Termination", transition.termination)):
                if result.intervals:
                    window = result.intervals[0]
                    row[heading] = f"{window.start} → {window.end}"
                elif result.reason:
                    row[heading] = f"{result.availability.value.capitalize()} · {result.reason}"
                else:
                    row[heading] = "Outside supplied date coverage"
            transitions.append(row)
        st.dataframe(pd.DataFrame(transitions), hide_index=True)

with st.expander("Soil context & profile"):
    st.write(soil["drainage"])
    st.write(soil["note"])
    st.dataframe(pd.DataFrame(soil["horizons"]), hide_index=True)
with st.expander("Calendar rules, availability & sources", expanded=True):
    for assumption in data["assumptions"]:
        st.write(f"• {assumption}")
    st.caption("Availability is exposed per crop year and rule category: unavailable differs from available with no intervals.")
    st.dataframe(pd.DataFrame([{"Year": y.year, "Crop": calendars[y.crop_id].name,
        "Termination": timeline.query(y.year, y.crop_id, "termination").availability.value,
        "Termination intervals": len(timeline.query(y.year, y.crop_id, "termination").intervals)} for y in timeline.years]), hide_index=True)
    for key, source in data["sources"].items():
        st.markdown(f"**[{source['title']}]({source['url']})** · `{key}`")
        st.caption(source["basis"])


st.subheader("Historical weather")
name = st.radio("Weather scenario", SCENARIOS.keys(), horizontal=True)
try:
    scenario = select_scenario(name, cached_weather())
except (OSError, ValueError) as error:
    st.error(f"The bundled weather could not be loaded. {error}")
    st.stop()

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
st.caption("Fieldwork uses the selected cached weather block and the starting crop from Timeline settings. The calendar above has its own date range.")
weather_start, weather_end = scenario.daily.index[[0, -1]].date
for tab, example in zip(st.tabs([example.name for example in plans]), plans):
    with tab:
        weather_timeline = expand_rotation(example, weather_start, weather_end, calendars)
        operations = timeline_operations(weather_timeline, calendars, data["sources"])
        show_fieldwork(calculate_fieldwork(operations, scenario.daily["precipitation_mm"]))
