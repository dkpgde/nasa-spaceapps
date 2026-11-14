import pandas as pd
import streamlit as st

from fieldwork import RAIN_RULE, calculate_fieldwork
from fieldwork_demo import demo_plans
from fieldwork_view import show_fieldwork
from weather import SCENARIOS, load_weather, select_scenario


@st.cache_data
def cached_weather() -> pd.DataFrame:
    return load_weather()


st.set_page_config(page_title="RotationLab")
st.title("RotationLab")
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
plans = demo_plans(tuple(int(year) for year in totals.index))
for tab, plan in zip(st.tabs([plan.name for plan in plans]), plans):
    with tab:
        show_fieldwork(calculate_fieldwork(plan, scenario.daily["precipitation_mm"]))
