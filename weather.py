"""Validated daily weather shared by the app and rotation analysis."""

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
import pandas as pd


CACHE = Path(__file__).with_name("data") / "boone-county-nasa-power.csv"
RECENT_CACHE = CACHE.with_name("boone-county-weather-2026.csv")
LOCATION = "Marsden Farm area, Boone County, Iowa"
LATITUDE, LONGITUDE = 42.013628, -93.784149
FIRST_YEAR, LAST_YEAR = 1991, 2025
BLOCK_YEARS = 4
DEFAULT_START_YEAR = 2010
CUSTOM_YEARS = "Custom years"
POWER_LABEL = "NASA POWER"
FORECAST_LABEL = "ECMWF SEAS5 forecast"
FORECAST_START = "2026-11-13"
FORECAST_SOURCE = "https://open-meteo.com/en/docs/seasonal-forecast-api"
TIME_STANDARD = "LST"
SOURCE_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
    f"?parameters=PRECTOTCORR,T2M&community=AG&longitude={LONGITUDE}"
    f"&latitude={LATITUDE}&start={FIRST_YEAR}0101&end={LAST_YEAR}1231"
    f"&time-standard={TIME_STANDARD}&format=CSV"
)

SCENARIOS = {
    CUSTOM_YEARS: (1, "Use four consecutive years beginning with the selected year."),
    "Average": (
        2,
        "Rank March–May and June–August rainfall separately across the reference "
        "period, averaging tied ranks. Choose the eligible year whose worse "
        "distance from the middle rank is smallest. Break ties by the smaller "
        "sum of both distances, then by the earlier year.",
    ),
    "Wet Spring": (
        2,
        "Choose the eligible year with the highest March–May rainfall. "
        "Break ties by the earlier year.",
    ),
    "Dry Summer": (
        3,
        "Choose the eligible year with the lowest June–August rainfall. "
        "Break ties by the earlier year.",
    ),
}


@dataclass(frozen=True)
class WeatherScenario:
    name: str
    reference_year: int
    reference_position: int
    rule: str
    source_url: str
    daily: pd.DataFrame
    seasonal_totals: pd.DataFrame
    historical_totals: pd.DataFrame
    location: str = LOCATION
    coordinates: tuple[float, float] = (LATITUDE, LONGITUDE)
    reference_period: tuple[int, int] = (FIRST_YEAR, LAST_YEAR)
    time_standard: str = TIME_STANDARD


def load_weather(path: Path = CACHE) -> pd.DataFrame:
    """Return one row per local solar date, with rain in mm and mean air temperature in °C."""
    with path.open(encoding="utf-8-sig") as source:
        for line in source:
            if line.strip() == "-END HEADER-":
                break
        else:
            raise ValueError("Missing NASA POWER CSV header.")
        rows = pd.read_csv(source)

    columns = ["YEAR", "DOY", "PRECTOTCORR", "T2M"]
    if rows.columns.tolist() != columns or not isinstance(rows.index, pd.RangeIndex):
        raise ValueError("Unexpected NASA POWER CSV columns.")

    dates = pd.date_range(f"{FIRST_YEAR}-01-01", f"{LAST_YEAR}-12-31", name="date")
    # Compare NASA's year/day-of-year pairs directly so invalid ordinals cannot roll over.
    if (
        len(rows) != len(dates)
        or not np.array_equal(rows["YEAR"], dates.year)
        or not np.array_equal(rows["DOY"], dates.day_of_year)
    ):
        raise ValueError("NASA POWER dates must cover every day in order, including February 29.")

    daily = rows[["PRECTOTCORR", "T2M"]].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(daily.to_numpy(dtype=float)).all() or daily.eq(-999).any().any():
        raise ValueError("NASA POWER precipitation or temperature contains missing values.")
    if daily["PRECTOTCORR"].lt(0).any():
        raise ValueError("NASA POWER precipitation must be nonnegative.")

    daily.index = dates
    return daily.rename(columns={"PRECTOTCORR": "precipitation_mm", "T2M": "temperature_c"})


def load_2026_weather(path: Path = RECENT_CACHE) -> pd.DataFrame:
    daily = pd.read_csv(path, index_col="date", parse_dates=["date"])
    dates = pd.date_range("2026-01-01", "2026-12-31", name="date")
    if list(daily.columns) != ["precipitation_mm", "temperature_c", "source"] or not daily.index.equals(dates):
        raise ValueError("The 2026 weather cache must cover every date in order.")
    values = daily[["precipitation_mm", "temperature_c"]].to_numpy(dtype=float)
    expected_sources = np.where(dates < pd.Timestamp(FORECAST_START), POWER_LABEL, FORECAST_LABEL)
    if (
        not np.isfinite(values).all()
        or (values == -999).any()
        or daily["precipitation_mm"].lt(0).any()
        or not np.array_equal(daily["source"], expected_sources)
    ):
        raise ValueError("The 2026 weather cache contains invalid values or sources.")
    return daily


def seasonal_totals(daily: pd.DataFrame) -> pd.DataFrame:
    rain = daily["precipitation_mm"]
    months = rain.index.month
    # Match the source precision so equal rainfall sums are ranked as ties.
    seasonal_rain = {}
    for season, month_range in {"spring_mm": range(3, 6), "summer_mm": range(6, 9)}.items():
        values = rain[months.isin(month_range)]
        seasonal_rain[season] = values.groupby(values.index.year).sum().round(2)
    return pd.DataFrame(seasonal_rain).rename_axis("year")


def select_scenario(name: str, daily: pd.DataFrame, *, start_year: int | None = None,
                    reference_period: tuple[int, int] = (FIRST_YEAR, LAST_YEAR)) -> WeatherScenario:
    """Select a four-year block from validated daily weather."""
    if name == "Typical":
        name = "Average"  # Accept the old name from existing callers.
    position, rule = SCENARIOS[name]
    totals = seasonal_totals(daily)
    # Presets and rainfall medians use complete historical years only.
    reference_first, reference_last = reference_period
    reference_totals = totals.loc[reference_first:reference_last]
    eligible = reference_totals.loc[
        reference_first + position - 1 : reference_last - (BLOCK_YEARS - position)
    ]
    if name == CUSTOM_YEARS:
        earliest = daily.index[0].year
        latest = daily.index[-1].year - BLOCK_YEARS + 1
        if start_year is None or start_year not in range(earliest, latest + 1):
            raise ValueError(f"Starting year must be between {earliest} and {latest}.")
        year = start_year
    elif name == "Average":
        middle_rank = (len(reference_totals) + 1) / 2
        distances = (reference_totals.rank() - middle_rank).abs().loc[eligible.index]
        year = min(eligible.index, key=lambda y: (distances.loc[y].max(), distances.loc[y].sum(), y))
    elif name == "Wet Spring":
        year = eligible["spring_mm"].idxmax()
    else:
        year = eligible["summer_mm"].idxmin()

    first = int(year) - position + 1
    last = first + BLOCK_YEARS - 1
    return WeatherScenario(
        name=name,
        reference_year=int(year),
        reference_position=position,
        rule=rule,
        source_url=SOURCE_URL,
        daily=daily.loc[f"{first}-01-01":f"{last}-12-31"].copy(),
        seasonal_totals=totals.loc[first:last].copy(),
        historical_totals=reference_totals,
        reference_period=reference_period,
    )


def refresh_cache() -> None:
    """Download and validate a replacement before overwriting the offline snapshot."""
    import requests

    response = requests.get(SOURCE_URL, timeout=60)
    response.raise_for_status()
    CACHE.parent.mkdir(exist_ok=True)
    with NamedTemporaryFile(dir=CACHE.parent, delete=False) as temporary:
        path = Path(temporary.name)
    try:
        path.write_bytes(response.content)
        load_weather(path)
        path.replace(CACHE)
    finally:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    refresh_cache()
