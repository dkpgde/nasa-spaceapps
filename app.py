import streamlit as st

from catalog import SOIL
from comparison import show_plan
from dashboard import masthead, monthly_chart, seasonal_chart
from projection import FIRST_YEAR, GRID, LAST_YEAR, MODELS, PATHWAYS, SOURCE, load_projections
from rainfall import RULES
from rotation import Dates
from weather import LATITUDE, LONGITUDE, SCENARIOS, load_weather, seasonal_totals, select_scenario


@st.cache_data
def cached_weather():
    return load_weather()


@st.cache_data
def cached_projections():
    return load_projections()


def show_weather_details(daily, totals, year, historical):
    charts, data = st.tabs(("Charts", "Data and sources"))
    with charts:
        st.markdown("**Seasonal rainfall**")
        st.caption(f"Highlighted bars show {year}.")
        seasonal_chart(totals, year)
        st.markdown(f"**Monthly weather in {year}**")
        monthly_chart(daily, year)
    with data:
        st.dataframe(
            totals.reset_index(),
            hide_index=True,
            column_config={
                "year": "Year",
                "spring_mm": st.column_config.NumberColumn("March–May (mm)", format="%.2f"),
                "summer_mm": st.column_config.NumberColumn("June–August (mm)", format="%.2f"),
            },
        )
        if historical:
            first, last = historical.reference_period
            st.write(historical.rule)
            st.caption(
                f"Reference period {first}–{last}. The reference year, {historical.reference_year}, "
                f"is year {historical.reference_position} of the four-year block."
            )
            medians = historical.historical_totals.median()
            st.caption(f"Historical median rainfall · {medians['spring_mm']:.2f} mm in March–May "
                       f"and {medians['summer_mm']:.2f} mm in June–August.")
            st.markdown(f"[NASA POWER daily data]({historical.source_url}) · MERRA-2 · Local Solar Time")
        else:
            st.markdown(
                f"[NASA NEX-GDDP-CMIP6 v2.0]({SOURCE}) · 0.25° grid · UTC. Weather grid cell "
                f"{GRID[0]:.3f}°, {GRID[1]:.3f}°. The preceding year supplies rotation carryover context."
            )
        st.dataframe(
            daily.loc[str(year)].reset_index(),
            hide_index=True,
            column_config={
                "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                "precipitation_mm": st.column_config.NumberColumn("Precipitation (mm)", format="%.2f"),
                "temperature_c": st.column_config.NumberColumn("Mean air temperature (°C)", format="%.2f"),
            },
        )


def show_assumptions():
    with st.expander("Rainfall rules, crop calendars, and soils"):
        for rule in RULES:
            st.markdown(rule)
        st.markdown(
            "Operation calendars use Iowa State planting guidance and usual USDA NASS harvest dates. "
            "Living cover starts seven days after midpoint planting, midpoint postharvest rye seeding, "
            "or the start of fall oat overseeding. Cash crop cover ends at a fixed maturity proxy. "
            "Cover intervals include surviving dormant plants and are clipped to the weather block."
        )
        st.markdown(
            "The rye calendar screens spring dates from March 15 and applies the selected starter "
            "recipe's minimum planting gap. Planned cover uses April 15 or the latest date that fits "
            "the gap before midpoint planting, whichever is earlier. Check rye height and growth in "
            "the field. Fall oats use November 30 as a winterkill proxy."
        )
        st.markdown(
            "Sensitive stages use fixed seasonal date proxies. Red clover is carried to spring "
            "incorporation in this demo, an Iowa State option alongside the study's fall incorporation. "
            "The final alfalfa hay year uses the study's late-November to early-December incorporation window."
        )
        soil_label, soil_url = SOIL
        st.markdown("**Boone County soils**")
        st.write(f"Representative farm location · {LATITUDE:.4f}°, {LONGITUDE:.4f}°")
        st.write("Marsden Farm soils are predominantly Clarion and Nicollet loams and Webster silty clay loam.")
        st.markdown(f"[{soil_label}]({soil_url}) · [USDA Web Soil Survey](https://websoilsurvey.nrcs.usda.gov/app/)")


st.set_page_config(page_title="RotationLab", layout="wide")
masthead()

historical = None
projection = "Future projections"
with st.container(border=True, key="comparison_controls"):
    weather_control, year_control, plan_control = st.columns([2, 1, 1])
    scenario = weather_control.selectbox("Weather scenario", (*SCENARIOS, projection))
    projected = scenario == projection
    try:
        if projected:
            model_control, pathway_control = st.columns(2)
            model = model_control.selectbox("Climate model", MODELS)
            pathway = pathway_control.selectbox("Emissions pathway", PATHWAYS, format_func=PATHWAYS.get)
            weather = cached_projections()[model, pathway]
            daily = weather.loc[str(FIRST_YEAR):str(LAST_YEAR)]
            totals = seasonal_totals(daily)
            default_year = 0
        else:
            weather = cached_weather()
            historical = select_scenario(scenario, weather)
            daily, totals = historical.daily, historical.seasonal_totals
            default_year = historical.reference_position - 1
    except (OSError, ValueError) as error:
        st.error(f"The bundled weather could not be loaded. {error}")
        st.stop()

    year = year_control.selectbox("Compare year", totals.index.tolist(), index=default_year, key=f"year-{scenario}")
    slot_count = plan_control.selectbox("Plans to compare", (1, 2, 3), index=2)
    spring, summer = totals.loc[year, ["spring_mm", "summer_mm"]]
    st.caption(f"{year} rainfall · {spring:,.0f} mm in spring · {summer:,.0f} mm in summer")
    if projected:
        st.caption(f"Simulated weather for {FIRST_YEAR}–{LAST_YEAR}. Exact dates are uncertain.")

with st.container(key="comparison_heading"):
    st.header(f"Rotation comparison for {year}", anchor=False)

span = Dates(daily.index[0].date(), daily.index[-1].date())
history = Dates(weather.index[0].date(), weather.index[-1].date())
with st.container(key="rotation_grid"):
    for slot, column in enumerate(st.columns(slot_count, gap="medium")):
        with column:
            show_plan(slot, daily, span, history, year)

with st.expander("Weather charts and data", key="weather-details", on_change="rerun") as details:
    if details.open:
        show_weather_details(daily, totals, year, historical)
show_assumptions()
