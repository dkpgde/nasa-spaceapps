"""Offline observations for the representative Boone County comparison point."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st


DATA = Path(__file__).with_name("data")

RAIN_SOURCES = {
    "NASA POWER": ("precipitation_mm", "Local solar day"),
    "GPM IMERG": ("imerg_mm", "UTC day"),
    "PRISM": ("prism_mm", "Day ending around 12 UTC"),
}
TEMPERATURE = {
    "NASA POWER": ("air_min_c", "air_max_c"),
    "PRISM": ("prism_min_c", "prism_max_c"),
}
AGROCLIMATE = {
    "Daily minimum air temperature": ("air_min_c", "°C"),
    "Daily maximum air temperature": ("air_max_c", "°C"),
    "Relative humidity at 2 m": ("relative_humidity_pct", "%"),
    "Surface shortwave radiation": ("solar_mj_m2_day", "MJ/m²/day"),
}
GAUGES = {
    "CoCoRaHS IA-SR-29": "cocorahs_ia_sr_29_mm",
    "CoCoRaHS IA-BN-13": "cocorahs_ia_bn_13_mm",
}
WATER = {
    "Surface soil moisture": ("surface_moisture", "m³/m³"),
    "Root-zone soil moisture": ("root_zone_moisture", "m³/m³"),
    "Root-zone soil moisture percentile": ("root_zone_percentile", "%"),
}


@st.cache_data
def load_site_weather():
    frame = pd.read_csv(DATA / "boone-county-site-weather.csv", index_col="date", parse_dates=["date"])
    if not frame.index.is_unique or not frame.index.is_monotonic_increasing:
        raise ValueError("The site weather cache must have sorted, unique daily dates.")
    return frame


@st.cache_data
def load_site_land():
    with (DATA / "boone-county-site-land.json").open(encoding="utf-8") as source:
        return json.load(source)


@st.cache_data
def load_vegetation():
    return pd.read_csv(DATA / "boone-county-modis-ndvi.csv", parse_dates=["date"])


def historical_conditions(history: pd.DataFrame, site: pd.DataFrame, source: str) -> pd.DataFrame:
    """Use a single complete precipitation product for the whole historical block."""
    if source == "NASA POWER":
        return history
    rain = site[RAIN_SOURCES[source][0]].dropna()
    retained = history.loc[rain.index.min():rain.index.max()].copy()
    retained["precipitation_mm"] = rain.reindex(retained.index)
    if retained["precipitation_mm"].isna().any() or retained.empty:
        raise ValueError(f"The bundled {source} rainfall series is incomplete.")
    retained["source"] = source
    return retained


def comparison_conditions(daily: pd.DataFrame, site: pd.DataFrame, source: str) -> pd.DataFrame:
    """Attach thermal and soil-moisture observations only on recorded comparison dates."""
    minimum, maximum = TEMPERATURE.get(source, TEMPERATURE["NASA POWER"])
    conditions = site[[minimum, maximum, "root_zone_percentile"]].rename(
        columns={minimum: "min_c", maximum: "max_c"},
    )
    result = daily.join(conditions)
    recorded = daily["source"].isin(RAIN_SOURCES)
    result.loc[~recorded, ["min_c", "max_c", "root_zone_percentile"]] = float("nan")
    return result
