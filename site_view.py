"""Boone County observations shown alongside the scenario results."""

import altair as alt
import pandas as pd
import streamlit as st

from dashboard import chart_style
from site_data import AGROCLIMATE, GAUGES, RAIN_SOURCES, WATER, load_site_land, load_vegetation
from weather import LATITUDE, LONGITUDE, POWER_LABEL, load_2026_weather, load_weather


def soil_and_terrain(land):
    soil, terrain = land["soil"], land["terrain"]
    st.subheader(soil["map_unit_name"])
    st.caption(f"USDA SSURGO map unit {soil['mukey']} · {soil['survey_area']} · {LATITUDE:.5f}°, {LONGITUDE:.5f}°")
    drainage, storage, elevation = st.columns(3)
    drainage.metric("Dominant drainage", soil["drainage"], border=True)
    storage.metric("Available water storage · upper 1 m", f"{soil['water_storage_mm_100cm']:g} mm", border=True)
    elevation.metric("SRTM elevation at point", f"{terrain['elevation_m']:g} m", border=True)
    st.write(f"Hydrologic soil group **{soil['hydrologic_group']}** · mapped slope **{soil['slope_low_pct']:g}–"
             f"{soil['slope_high_pct']:g}%** · five nearby SRTM samples span **{terrain['relief_m']:g} m** of elevation.")
    dominant = soil["dominant_component"]
    st.caption(f"These are mapped estimates for the dominant {dominant['name']} component "
               f"({dominant['share_pct']}% of the map unit). Soil properties can vary within the map unit.")
    with st.expander("Soil horizons and source records"):
        st.dataframe(pd.DataFrame(soil["horizons"]), hide_index=True)
        st.caption("[USDA NRCS Soil Data Access](https://sdmdataaccess.nrcs.usda.gov/) · "
                   "[Web Soil Survey](https://websoilsurvey.nrcs.usda.gov/app/) · "
                   "[SRTM v3 elevation service](https://www.opentopodata.org/datasets/srtm/)")


def series_chart(frame, field, unit, *, color, points=False):
    base = alt.Chart(frame.reset_index(drop=True)).encode(
        x=alt.X("date:T", title=None, axis=alt.Axis(format="%b", tickCount="month")),
        y=alt.Y(f"{field}:Q", title=unit, scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("date:T", title="Date", format="%b %d, %Y"),
                 alt.Tooltip(f"{field}:Q", title=unit, format=".3~f")],
    )
    chart = base.mark_point(color=color, filled=True, size=45) if points else base.mark_line(color=color)
    st.altair_chart(chart_style(chart.properties(background="transparent")), theme=None, height=218)


def vegetation_at_site(land, observation_year):
    crops = pd.DataFrame(land["cropland"])
    matches = crops.loc[crops["year"].eq(observation_year), "class_name"]
    if not matches.empty:
        st.metric("USDA Cropland Data Layer classification at this point", matches.iloc[0], border=True)
        st.caption("An annual pixel classification summarizes the land cover at the sampled point. "
                   "The nearby plots may have different crops and management.")
    else:
        st.caption(f"No Cropland Data Layer snapshot is bundled for {observation_year}.")
    vegetation = load_vegetation()
    rows = vegetation.loc[vegetation["date"].dt.year.eq(observation_year)]
    quality = rows.loc[rows["reliability"].eq(0)]
    st.markdown("**MODIS vegetation greenness (NDVI)**")
    if quality.empty:
        available = ", ".join(str(year) for year in sorted(vegetation.loc[vegetation["reliability"].eq(0), "date"].dt.year.unique()))
        st.info(f"No good-quality MODIS NDVI observations are bundled for {observation_year}. Available years include {available}.")
    else:
        series_chart(quality, "ndvi", "NDVI", color="#277357", points=True)
        st.caption("Good-quality Terra MODIS MOD13Q1 16-day composites for one ~250 m pixel. "
                   "Greenness reflects vegetation in that pixel and can mix several plots.")
    with st.expander("View annual crop classifications"):
        st.dataframe(crops.rename(columns={"year": "Year", "class_name": "CDL class", "class_code": "Class code"}),
                     hide_index=True)
    st.caption("[USDA Cropland Data Layer](https://www.nass.usda.gov/Research_and_Science/Cropland/Release/) · "
               "[NASA MOD13Q1](https://doi.org/10.5067/MODIS/MOD13Q1.061) · "
               "[ORNL DAAC point subsetting](https://modis.ornl.gov/rst/globalsubset_ui/)")


@st.cache_data
def monthly_rainfall(site):
    recent = load_2026_weather()
    power = pd.concat([load_weather(), recent.loc[recent["source"].eq(POWER_LABEL)]])
    rain = site[[RAIN_SOURCES["GPM IMERG"][0], RAIN_SOURCES["PRISM"][0], *GAUGES.values()]].join(
        power[["precipitation_mm"]],
    )
    totals = rain.resample("MS").sum(min_count=1)
    observed = rain.resample("MS").count()
    totals = totals.where(observed.eq(totals.index.days_in_month, axis=0))
    names = {column: label for label, (column, _) in RAIN_SOURCES.items()}
    names.update({column: name for name, column in GAUGES.items()})
    return totals.rename(columns=names)


def water_and_weather(site, observation_year):
    rows = site.loc[str(observation_year)].reset_index()
    choices = ("Monthly rainfall across sources", *WATER, *AGROCLIMATE)
    label = st.selectbox("Observation to chart", choices, key="site-variable")
    if label == choices[0]:
        totals = monthly_rainfall(site).loc[str(observation_year)].reset_index()
        plot = totals.melt(id_vars="date", var_name="Source", value_name="Rainfall").dropna()
        chart = alt.Chart(plot).mark_line(point=True).encode(
            x=alt.X("date:T", title=None, axis=alt.Axis(format="%b", tickCount="month")),
            y=alt.Y("Rainfall:Q", title="Rainfall (mm)"),
            color=alt.Color("Source:N", legend=alt.Legend(orient="bottom", title=None)),
            tooltip=[alt.Tooltip("date:T", title="Month", format="%B"), "Source",
                     alt.Tooltip("Rainfall:Q", title="Rainfall (mm)", format=".1f")],
        )
        st.altair_chart(chart_style(chart.properties(background="transparent")), theme=None, height=218)
        st.caption("Only complete months are plotted. The products use different grids and daily time boundaries. "
                   "CoCoRaHS gauges are approximately 9–10 km away and provide a ground comparison.")
    else:
        field, unit = (WATER | AGROCLIMATE)[label]
        valid = rows.dropna(subset=[field])
        if valid.empty:
            st.info(f"{label} is unavailable for {observation_year}.")
        else:
            series_chart(valid, field, unit, color="#286d91")
        if label in WATER:
            st.caption("NASA SMAP Level 4, daily UTC, approximately 9 km. Surface moisture represents the upper 5 cm. "
                       "Root-zone moisture represents the upper 100 cm. Bundled coverage is March 2015 through December 2025.")
        else:
            st.caption("NASA POWER daily agroclimate observations on the local solar day.")
    st.caption("[NASA POWER](https://power.larc.nasa.gov/docs/) · [GPM IMERG](https://gpm.nasa.gov/data/imerg) · "
               "[PRISM Group, Oregon State University](https://prism.oregonstate.edu/), accessed November 15, 2026 · "
               "[CoCoRaHS](https://www.cocorahs.org/) · "
               "[NASA POWER SMAP processing](https://power.larc.nasa.gov/docs/methodology/data/sources_hydrology/)")


def show_site_observations(site, comparison_year):
    with st.container(border=True, key="site_observations"):
        st.header("Boone County observations", anchor="site-observations")
        st.write("Explore the mapped soils, observed vegetation, and regional weather around the comparison point.")
        years = range(site.index[0].year, site.index[-1].year + 1)
        starting_year = comparison_year if comparison_year in years else years[-1]
        observation_year = st.selectbox("Observation year", years, index=years.index(starting_year),
                                        key=f"observation-year-{comparison_year}")
        soil_tab, plants_tab, weather_tab = st.tabs(("Soils & terrain", "Crops & greenness", "Weather & moisture"))
        land = load_site_land()
        with soil_tab:
            soil_and_terrain(land)
        with plants_tab:
            vegetation_at_site(land, observation_year)
        with weather_tab:
            water_and_weather(site, observation_year)
