"""Shared dashboard presentation for historical and projected weather."""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


ASSETS = Path(__file__).with_name("assets")
SPRING, SUMMER = "#456E8E", "#A26A2C"


def masthead():
    css = (ASSETS / "dashboard.css").read_text(encoding="utf-8")
    st.html(f"<style>{css}</style>")
    with st.container(key="masthead"):
        st.title("RotationLab", anchor=False)
        st.write("Compare crop rotations using NASA weather for Boone County, Iowa.")


def chart_style(chart):
    return chart.configure_view(stroke=None).configure_axis(
        labelColor="#43584F", titleColor="#23382F", gridColor="#DDE6DC",
        domain=False, ticks=False, labelPadding=6, titlePadding=10,
        labelFont="Segoe UI, sans-serif", titleFont="Segoe UI, sans-serif",
    ).configure_legend(labelColor="#23382F", labelFont="Segoe UI, sans-serif")


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
