"""Read daily NASA POWER meteorology saved at native MERRA-2 grid points."""

from functools import lru_cache
import json
from math import floor
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from weather import POWER_LABEL


ARCHIVE = Path(__file__).with_name("data") / "nasa-power-us"
SOURCE = "https://power.larc.nasa.gov/docs/services/aws/"
PACKED_WEATHER = np.dtype([("rain", "<u2"), ("temp", "<i2")])
TILE_SIZE = 15


def grid_cell(latitude, longitude):
    return floor((latitude + 90) * 2 + .5), floor((longitude + 180) / .625 + .5) % 576


def grid_coordinates(cell):
    row, column = cell
    return row * .5 - 90, column * .625 - 180


def tile_for(cell):
    return tuple(index // TILE_SIZE for index in cell)


def cell_name(cell):
    return ".".join(map(str, cell))


@lru_cache(maxsize=1)
def coverage():
    path = ARCHIVE / "coverage.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"cells": []}


def load_grid_weather(cell):
    archive = ARCHIVE / f"{cell_name(tile_for(cell))}.zip"
    with ZipFile(archive) as data:
        values = np.frombuffer(data.read(cell_name(cell)), dtype=PACKED_WEATHER)
    dates = pd.date_range(coverage()["first"], coverage()["last"], name="date")
    if len(values) != len(dates):
        raise ValueError(f"Incomplete NASA POWER weather at grid cell {cell}.")
    return pd.DataFrame({
        "precipitation_mm": values["rain"] / 100,
        "temperature_c": values["temp"] / 100,
        "source": POWER_LABEL,
    }, index=dates)
