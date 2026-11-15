from dataclasses import replace

import pandas as pd
import streamlit as st

from catalog import SOIL
from comparison import CATALOGS, reset_plans, show_plan
from dashboard import (
    cached_grid_weather, cached_weather, choose_projection, masthead, monthly_chart, seasonal_chart, show_weather_sources,
    weather_sources_by_year,
)
from grid_weather import SOURCE as GRID_SOURCE, cell_name, coverage, grid_cell, grid_coordinates
from location_picker import show_location_picker
from locations import BOONE_COUNTY, SITES, coordinates, county_name
from mead_catalog import SOIL_STUDY, STUDY
from projection import CUSTOM_START_YEARS, FIRST_YEAR, PROJECTION_START_YEARS, custom_weather
from rainfall import RULES
from rotation import Dates
from weather import (
    BLOCK_YEARS, CUSTOM_YEARS, DEFAULT_START_YEAR, FIRST_YEAR as POWER_FIRST_YEAR, FORECAST_LABEL, FORECAST_START, LATITUDE,
    LONGITUDE, POWER_LABEL, SCENARIOS, seasonal_totals, select_scenario,
)


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
            reference = f"Rainfall baseline {first}–{last}."
            if historical.name != CUSTOM_YEARS:
                reference += (
                    f" The reference year, {historical.reference_year}, "
                    f"is year {historical.reference_position} of the four-year block."
                )
            st.caption(reference)
            medians = historical.historical_totals.median()
            st.caption(f"Historical median rainfall · {medians['spring_mm']:.2f} mm in March–May "
                       f"and {medians['summer_mm']:.2f} mm in June–August.")
        show_weather_sources(daily)
        st.dataframe(
            daily.loc[str(year)].reset_index(),
            hide_index=True,
            column_config={
                "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                "precipitation_mm": st.column_config.NumberColumn("Precipitation (mm)", format="%.2f"),
                "temperature_c": st.column_config.NumberColumn("Mean air temperature (°C)", format="%.2f"),
                "source": "Weather source",
            },
        )


def show_assumptions(iowa):
    with st.expander("Rainfall rules, crop calendars, and soils"):
        for rule in RULES:
            st.markdown(rule)
        st.markdown(
            "Operation calendars use published extension guidance, field trials and usual USDA NASS dates. "
            "Living cover starts seven days after midpoint planting, midpoint postharvest rye seeding, "
            "or the start of fall oat overseeding. Cash crop cover ends at a fixed maturity proxy. "
            "Cover intervals include surviving dormant plants and are clipped to the weather block."
        )
        st.markdown(
            "Fall-planted grain crops are listed in their harvest year. Planting starts after the midpoint "
            "harvest of the preceding crop, within the fall planting window. Dates for maturity and "
            "sensitive stages are fixed calendar proxies. Some crops have no sourced sensitive window."
        )
        if not iowa:
            st.markdown(
                "**Mead, Nebraska.** The site uses Nebraska operation dates, including statewide windows "
                "for crops such as dry beans and sugarbeets. The study site includes Yutan–Tomek soils. "
                f"[{STUDY[0]}]({STUDY[1]}) · [{SOIL_STUDY[0]}]({SOIL_STUDY[1]})."
            )
            return
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


def show_grid_source(cell):
    lat, lon = grid_coordinates(cell)
    st.caption(f"NASA POWER · MERRA-2 grid point {lat:.3f}°, {lon:.3f}° · Local Solar Time. "
               f"[Data source]({GRID_SOURCE})")


def explore_weather(county, cell, weather):
    st.header(county_name(county), anchor=False)
    if weather is None:
        st.info("Weather data is unavailable for this county.")
        return
    show_grid_source(cell)
    st.caption("Weather represents the grid point nearest the county’s Census reference point. "
               "Crop calendars are available at the two study sites.")
    st.caption(f"Daily coverage · {weather.index[0]:%Y-%m-%d} to {weather.index[-1]:%Y-%m-%d}")
    # Seasonal totals require the full March–August period.
    totals = seasonal_totals(weather)
    if weather.index[-1] < pd.Timestamp(weather.index[-1].year, 8, 31):
        totals = totals.iloc[:-1]
    year = st.selectbox("Weather year", totals.index[::-1], key=f"weather-county-{county}")
    show_weather_details(weather, totals, year, None)
    daily = weather.to_csv().encode("utf-8")
    st.download_button("Download daily weather (CSV)", daily, f"nasa-power-{county}.csv", "text/csv")


st.set_page_config(page_title="RotationLab", layout="wide")
masthead()
county = show_location_picker()
iowa = county == BOONE_COUNTY
cell = grid_cell(*coordinates(county))
try:
    grid = cached_grid_weather(cell) if cell_name(cell) in coverage()["cells"] else None
    if iowa:
        local_weather = cached_weather()
except (OSError, ValueError, KeyError) as error:
    st.error(f"The NASA POWER archive could not be loaded. {error}")
    st.stop()
catalog = CATALOGS.get(county)
if catalog is None or not iowa and grid is None:
    explore_weather(county, cell, grid)
    # Keep comparison settings while browsing a weather-only county.
    for key in st.session_state:
        if key == "plan-count" or key.startswith(("weather-choice-", "start-", "year-")):
            st.session_state[key] = st.session_state[key]
    st.stop()

st.markdown(f"**{SITES[county][0]}** · {len(catalog.crops)} crop calendars")
show_grid_source(cell)
if iowa:
    if grid is not None:
        local_weather = pd.concat([grid.loc[:"1990-12-31"], local_weather])
    reference = (POWER_FIRST_YEAR, local_weather.index[-1].year)
else:
    latest = grid.index[-1]
    last_complete_year = latest.year if (latest.month, latest.day) == (12, 31) else latest.year - 1
    local_weather = grid.loc[:str(last_complete_year)]
    reference = (local_weather.index[0].year, last_complete_year)

historical = None
projection = "Future projections"
with st.container(border=True, key="comparison_controls"):
    weather_control, year_control, plan_control = st.columns([2, 1, 1])
    choices = (*SCENARIOS, projection) if iowa else tuple(SCENARIOS)
    scenario = weather_control.selectbox("Weather to compare", choices,
        key="weather-choice-scenario" if iowa else "weather-choice-mead",
        help="Presets use complete historical years. Iowa also has a seasonal forecast and future climate projections.")
    projection_only = scenario == projection
    start_year = None
    if scenario in (CUSTOM_YEARS, projection):
        if projection_only:
            years = PROJECTION_START_YEARS
        else:
            stop = CUSTOM_START_YEARS.stop if iowa else reference[1] - BLOCK_YEARS + 2
            years = range(local_weather.index[0].year, stop)
        start_year = weather_control.selectbox(
            "Starting year", years, index=0 if projection_only else years.index(DEFAULT_START_YEAR),
            key=f"start-{catalog.prefix}{scenario}",
            help="This year and the next three years are used for every plan.",
        )
        end_year = start_year + BLOCK_YEARS - 1
    try:
        projected = choose_projection() if iowa and start_year is not None and end_year >= FIRST_YEAR else None
        if projection_only:
            weather = projected
            daily = weather.loc[str(start_year):str(end_year)]
            totals = seasonal_totals(daily)
            default_year = 0
        else:
            weather = local_weather
            if iowa and scenario == CUSTOM_YEARS:
                weather = custom_weather(weather, start_year, projected)
            historical = select_scenario(scenario, weather, start_year=start_year, reference_period=reference)
            if not iowa:
                historical = replace(historical, location=SITES[county][0], coordinates=coordinates(county),
                                     source_url=GRID_SOURCE)
            daily, totals = historical.daily, historical.seasonal_totals
            default_year = historical.reference_position - 1
    except (OSError, ValueError) as error:
        st.error(f"The bundled weather could not be loaded. {error}")
        st.stop()

    year = year_control.selectbox("Year to inspect", totals.index.tolist(), index=default_year,
        key=f"year-{catalog.prefix}{scenario}-{totals.index[0]}", format_func=lambda y: f"Year {y - totals.index[0] + 1} · {y}",
        help="Results below are for this one year. Crop sequences show the full four-year comparison.")
    slot_count = plan_control.selectbox("Plans to compare", (1, 2, 3), index=2, key="plan-count")
    spring, summer = totals.loc[year, ["spring_mm", "summer_mm"]]
    st.caption(f"{year} rainfall · {spring:,.0f} mm in March–May · {summer:,.0f} mm in June–August")
    sources_by_year = weather_sources_by_year(daily)
    if sources_by_year.loc[year] != POWER_LABEL:
        st.caption(f"{year} weather · {sources_by_year.loc[year]}")
    if daily["source"].eq(FORECAST_LABEL).any():
        st.caption(f"2026 includes a seasonal forecast from {FORECAST_START} through December 31.")
    if projected is not None:
        st.caption("NASA climate projections use simulated daily weather. Exact future weather is uncertain.")
    if scenario not in (CUSTOM_YEARS, projection):
        st.caption({
            "Average": "Explore a recorded year with spring and summer rainfall near the historical median.",
            "Wet Spring": "Explore how a very wet spring affects planting and the timing of cover-crop removal.",
            "Dry Summer": "Explore how a very dry summer overlaps with each crop's sensitive growth stages.",
        }[scenario])
        if year != historical.reference_year:
            st.caption(f"The scenario's example year is {historical.reference_year}; you are viewing another year in the same weather block.")

with st.container(key="comparison_heading"):
    st.header(f"Compare results for {year}", anchor=False)
    st.caption(f"All plans use the same {daily.index[0].year}–{daily.index[-1].year} weather. "
               "The highlighted crop is the one being compared. Shorter rotations repeat to fill four years.")

span = Dates(daily.index[0].date(), daily.index[-1].date())
history = Dates(weather.index[0].date(), weather.index[-1].date())
comparison_rows = []
with st.container(key="rotation_grid"):
    for slot, column in enumerate(st.columns(slot_count, gap="medium")):
        with column:
            comparison_rows.extend(show_plan(slot, daily, span, history, year, catalog, weather))

with st.container(key="comparison_actions"):
    download, reset = st.columns([2, 1])
    export = pd.DataFrame(comparison_rows)
    export.insert(0, "Weather scenario", scenario)
    export.insert(1, "Weather source", export["Year"].map(sources_by_year))
    export.insert(2, "Location", SITES[county][0])
    location_slug = "" if iowa else "mead-"
    download.download_button(
        "Download all four years (CSV)", export.to_csv(index=False).encode("utf-8-sig"),
        f"rotationlab-{location_slug}{scenario.lower().replace(' ', '-')}-{span.start.year}-{span.end.year}.csv",
        "text/csv", width="stretch",
    )
    reset.button("Restore starting plans", on_click=reset_plans, args=(catalog,), width="stretch")
    st.caption("These are rainfall-based comparisons. Actual field access and crop stress also depend on soil and field conditions.")

with st.expander("Weather charts and data", key="weather-details", on_change="rerun") as details:
    if details.open:
        show_weather_details(daily, totals, year, historical)
show_assumptions(iowa)
