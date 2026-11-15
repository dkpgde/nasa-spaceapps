"""Shared dashboard presentation for historical and projected weather."""

from base64 import b64encode
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from projection import GRID, MODELS, PATHWAYS, PROJECTION_LABEL, SOURCE, load_projections
from grid_weather import load_grid_weather
from weather import FORECAST_LABEL, FORECAST_SOURCE, FORECAST_START, POWER_LABEL, load_weather


ASSETS = Path(__file__).with_name("assets")
SPRING, SUMMER = "#2F7195", "#AC671E"


@st.cache_data
def cached_weather():
    return load_weather().assign(source=POWER_LABEL)


@st.cache_data(max_entries=64)
def cached_grid_weather(cell):
    return load_grid_weather(cell)


@st.cache_data
def cached_projections():
    return load_projections()


def choose_projection():
    model_column, pathway_column = st.columns(2)
    model = model_column.selectbox("Climate model", MODELS, key="weather-choice-model")
    pathway = pathway_column.selectbox("Emissions pathway", PATHWAYS, format_func=PATHWAYS.get,
                                       key="weather-choice-pathway")
    label = f"{PROJECTION_LABEL} · {model} / {PATHWAYS[pathway]}"
    return cached_projections()[model, pathway].assign(source=label)


def weather_sources_by_year(daily):
    return daily.groupby(daily.index.year)["source"].agg(lambda sources: " + ".join(sources.unique()))


def show_weather_sources(daily):
    sources = daily["source"]
    if sources.eq(POWER_LABEL).any():
        st.markdown("[NASA POWER daily data](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) · Local Solar Time")
    if sources.eq("GPM IMERG").any():
        st.markdown("[NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) via NASA POWER · 0.1° grid · UTC days")
    if sources.eq("PRISM").any():
        st.markdown("[PRISM Group, Oregon State University](https://prism.oregonstate.edu/), accessed November 15, 2026 "
                    "via Iowa Environmental Mesonet · days ending around 12 UTC")
    if sources.eq(FORECAST_LABEL).any():
        st.markdown(
            f"[ECMWF SEAS5 via Open-Meteo]({FORECAST_SOURCE}) · {FORECAST_START} through 2026-12-31. "
            "The control member provides one seasonal forecast sequence."
        )
    if sources.str.startswith(PROJECTION_LABEL).any():
        st.markdown(
            f"[NASA NEX-GDDP-CMIP6 v2.0]({SOURCE}) · 0.25° grid · UTC · {GRID[0]:.3f}°, {GRID[1]:.3f}°. "
            "Daily sequences are simulations for stress testing."
        )


def masthead():
    st.html(ASSETS / "dashboard.css")
    artwork = ASSETS / "iowa-orbit.webp"
    image = ""
    if artwork.exists():
        encoded = b64encode(artwork.read_bytes()).decode("ascii")
        image = f'<img class="hero-art" src="data:image/webp;base64,{encoded}" alt="">'
    with st.container(key="masthead"):
        st.html(f"""
            <div class="brand-bar">
                <span class="brand-name"><span class="orbit-mark" aria-hidden="true"></span>RotationLab</span>
                <a href="#choose-location">Choose a location <span aria-hidden="true">↓</span></a>
            </div>
            <div class="field-hero">
                {image}
                <div class="hero-copy">
                    <h1>Explore weather and crop rotations</h1>
                    <p>Explore NASA weather across the U.S. and compare rotations at research sites in Iowa and Nebraska.</p>
                </div>
            </div>
        """)


def chart_style(chart):
    return chart.configure_view(stroke=None).configure_axis(
        labelColor="#4E625B", titleColor="#162F28", gridColor="#DFE8E4",
        domain=False, ticks=False, labelPadding=6, titlePadding=10,
        labelFont="system-ui", titleFont="system-ui",
    ).configure_legend(labelColor="#162F28", labelFont="system-ui")


def seasonal_chart(totals: pd.DataFrame, selected_year: int):
    season = ["Mar–May", "Jun–Aug"]
    data = totals.rename(columns=dict(zip(("spring_mm", "summer_mm"), season))).reset_index()
    data = data.melt(id_vars="year", var_name="Season", value_name="Rainfall")
    chart = alt.Chart(data).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0, labelFontSize=12)),
        xOffset=alt.XOffset("Season:N", sort=season),
        y=alt.Y("Rainfall:Q", title="Rainfall (mm)", axis=alt.Axis(tickCount=4)),
        color=alt.Color(
            "Season:N", sort=season, scale=alt.Scale(domain=season, range=[SPRING, SUMMER]),
            legend=alt.Legend(orient="top", title=None, labelFontSize=12),
        ),
        opacity=alt.condition(alt.datum.year == selected_year, alt.value(1), alt.value(.55)),
        tooltip=[alt.Tooltip("year:O", title="Year"), "Season:N",
                 alt.Tooltip("Rainfall:Q", title="Rainfall (mm)", format=".2f")],
    ).properties(background="transparent")
    st.altair_chart(chart_style(chart), theme=None, width="stretch", height=194)


def monthly_chart(daily: pd.DataFrame, year: int):
    data = daily.loc[str(year)].resample("MS").agg(
        rain=("precipitation_mm", "sum"), temperature=("temperature_c", "mean"),
    ).reset_index()
    base = alt.Chart(data).encode(x=alt.X("date:T", title=None, axis=alt.Axis(format="%b", tickCount="month")))
    rain = base.mark_bar(color=SPRING, size=12).encode(
        y=alt.Y("rain:Q", title="Rainfall (mm)"),
        tooltip=[alt.Tooltip("date:T", format="%B", title="Month"),
                 alt.Tooltip("rain:Q", format=".1f", title="Rainfall (mm)")],
    )
    temp = base.mark_line(color=SUMMER, point=True).encode(
        y=alt.Y("temperature:Q", title="Mean temperature (°C)", axis=alt.Axis(orient="right")),
        tooltip=[alt.Tooltip("date:T", format="%B", title="Month"),
                 alt.Tooltip("temperature:Q", format=".1f", title="Mean temperature (°C)")],
    )
    chart = (rain + temp).resolve_scale(y="independent").properties(background="transparent")
    st.altair_chart(chart_style(chart), theme=None, width="stretch", height=200)
