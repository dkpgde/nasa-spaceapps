"""Bundled daily NASA NEX-GDDP-CMIP6 simulations for Boone County."""

from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
import pandas as pd
import requests

from weather import (
    BLOCK_YEARS, FIRST_YEAR as HISTORICAL_FIRST_YEAR, LAST_YEAR as HISTORICAL_LAST_YEAR,
    LATITUDE, LONGITUDE, load_2026_weather,
)


SOURCE = "https://www.nccs.nasa.gov/data-collections/nex-gddp-cmip6/"
ARCHIVE = "https://ds.nccs.nasa.gov/thredds/ncss/grid/AMES/NEX/GDDP-CMIP6"
CACHE = Path(__file__).with_name("data") / "boone-county-nasa-projections.csv"
FIRST_YEAR, LAST_YEAR = 2027, 2031
PROJECTION_LABEL = "NASA climate projection"
CUSTOM_START_YEARS = range(HISTORICAL_FIRST_YEAR, LAST_YEAR - BLOCK_YEARS + 2)
PROJECTION_START_YEARS = range(FIRST_YEAR, LAST_YEAR - BLOCK_YEARS + 2)
GRID = (42.125, -93.875)
MODELS = {"ACCESS-CM2": "gn", "MPI-ESM1-2-LR": "gn"}
PATHWAYS = {"ssp245": "SSP2-4.5", "ssp370": "SSP3-7.0"}
VARIABLES = {
    "pr": ('pr[unit="kg m-2 s-1"]', "precipitation_mm", 86400, 0),
    "tas": ('tas[unit="K"]', "temperature_c", 1, -273.15),
}
DATES = pd.date_range(f"{FIRST_YEAR - 1}-01-01", f"{LAST_YEAR}-12-31", name="date")


def custom_weather(historical: pd.DataFrame, start_year: int, projected: pd.DataFrame | None) -> pd.DataFrame:
    if start_year + BLOCK_YEARS - 1 <= HISTORICAL_LAST_YEAR:
        return historical
    frames = [historical, load_2026_weather()]
    if projected is not None:
        # Skip the simulated 2026 carryover because this mode has a 2026 weather snapshot.
        frames.append(projected.loc[str(FIRST_YEAR):])
    return pd.concat(frames)


def load_projections(path: Path = CACHE) -> dict[tuple[str, str], pd.DataFrame]:
    columns = ["precipitation_mm", "temperature_c"]
    rows = pd.read_csv(path, parse_dates=["date"])
    if rows.columns.tolist() != ["model", "pathway", "date", *columns]:
        raise ValueError("Unexpected NASA projection columns.")
    runs = {}
    for key, run in rows.groupby(["model", "pathway"], dropna=False):
        daily = run.set_index("date")[columns]
        values = daily.to_numpy(dtype=float)
        if (
            not daily.index.equals(DATES)
            or not np.isfinite(values).all()
            or (values == -999).any()
            or daily["precipitation_mm"].lt(0).any()
        ):
            raise ValueError(f"NASA projection {key} has incomplete or invalid daily data.")
        runs[key] = daily
    if set(runs) != {(model, pathway) for model in MODELS for pathway in PATHWAYS}:
        raise ValueError("The NASA projection cache is missing a supported model or pathway.")
    return runs


def download_variable(model: str, pathway: str, year: int, variable: str) -> pd.Series:
    member = "r1i1p1f1"
    filename = f"{variable}_day_{model}_{pathway}_{member}_{MODELS[model]}_{year}_v2.0.nc"
    response = requests.get(
        f"{ARCHIVE}/{model}/{pathway}/{member}/{variable}/{filename}",
        params={
            "var": variable, "latitude": LATITUDE, "longitude": LONGITUDE,
            "time_start": f"{year}-01-01T00:00:00Z",
            "time_end": f"{year}-12-31T23:59:59Z", "accept": "csv",
        },
        timeout=45,
    )
    response.raise_for_status()
    rows = pd.read_csv(StringIO(response.text))
    column, output, scale, offset = VARIABLES[variable]
    if (
        not rows['latitude[unit="degrees_north"]'].eq(GRID[0]).all()
        or not rows['longitude[unit="degrees_east"]'].eq(GRID[1]).all()
        or not np.isfinite(rows[column]).all()
        or rows[column].lt(0).any()
    ):
        raise ValueError(f"Unexpected grid or source values in {filename}.")
    dates = pd.DatetimeIndex(pd.to_datetime(rows["time"], utc=True)).tz_localize(None).normalize()
    return pd.Series(rows[column].to_numpy() * scale + offset, index=dates, name=output)


def refresh_cache():
    # Annual point requests avoid downloading entire global NetCDF files.
    jobs = [
        (model, pathway, year, variable)
        for model in MODELS
        for pathway in PATHWAYS
        for year in range(FIRST_YEAR - 1, LAST_YEAR + 1)
        for variable in VARIABLES
    ]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {job: pool.submit(download_variable, *job) for job in jobs}
        frames = []
        for model in MODELS:
            for pathway in PATHWAYS:
                for year in range(FIRST_YEAR - 1, LAST_YEAR + 1):
                    series = [futures[model, pathway, year, var].result() for var in VARIABLES]
                    if not series[0].index.equals(series[1].index):
                        raise ValueError(f"Weather variables have different date coverage for {model} {pathway} {year}.")
                    frame = pd.concat(series, axis=1).rename_axis("date").reset_index()
                    frames.append(frame.assign(model=model, pathway=pathway))
    with NamedTemporaryFile(dir=CACHE.parent, delete=False) as temporary:
        path = Path(temporary.name)
    try:
        columns = ["model", "pathway", "date", "precipitation_mm", "temperature_c"]
        pd.concat(frames)[columns].to_csv(path, index=False, float_format="%.8f")
        load_projections(path)
        path.replace(CACHE)
    finally:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    refresh_cache()
