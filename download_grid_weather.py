"""Download NASA POWER’s daily LST data for U.S. county and study-site points."""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
from threading import local
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import pandas as pd
import requests
from numcodecs import get_codec
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from grid_weather import ARCHIVE, PACKED_WEATHER, TILE_SIZE, cell_name, grid_cell, tile_for
from locations import county_features, coordinates


BUCKET = "https://nasa-power.s3.us-west-2.amazonaws.com"
ZARR = f"{BUCKET}/merra2/temporal/power_merra2_daily_temporal_lst.zarr"
PARAMETERS = {"PRECTOTCORR": "rain", "T2M": "temp"}
FIRST = "1981-01-01"
http = local()


def download(url):
    if not hasattr(http, "session"):
        http.session = requests.Session()
        http.session.mount("https://", HTTPAdapter(max_retries=Retry(
            total=4, backoff_factor=.5, status_forcelist=(429, 500, 502, 503, 504),
        )))
    with closing(http.session.get(url, timeout=45)) as response:
        response.raise_for_status()
        return response.content


def array(metadata, name, suffix):
    spec = metadata[f"{name}/.zarray"]
    raw = get_codec(spec["compressor"]).decode(download(f"{ZARR}/{name}/{suffix}"))
    data = np.frombuffer(raw, dtype=spec["dtype"])
    for transform in reversed(spec["filters"] or []):
        data = get_codec(transform).decode(data)
    return data.reshape(spec["chunks"])


def save_tile(task, metadata, first, end, staging):
    tile, cells = task
    path = staging / f"{cell_name(tile)}.zip"
    records = np.empty((end - first, len(cells)), dtype=PACKED_WEATHER)
    rows, cols = np.asarray(cells).T % TILE_SIZE
    for name, field in PARAMETERS.items():
        step = metadata[f"{name}/.zarray"]["chunks"][0]
        for block in range(first // step, (end - 1) // step + 1):
            block_start = block * step
            start, stop = max(first, block_start), min(end, block_start + step)
            data = array(metadata, name, f"{block}.{cell_name(tile)}")
            values = np.rint(data[start - block_start:stop - block_start, rows, cols] * 100)
            limits = np.iinfo(PACKED_WEATHER[field])
            if not np.isfinite(values).all() or values.min() < limits.min or values.max() > limits.max:
                raise ValueError(f"Invalid {name} in NASA POWER tile {tile}.")
            records[field][start - first:stop - first] = values
    with ZipFile(path, "w", ZIP_DEFLATED) as output:
        for cell, record in zip(cells, records.T, strict=True):
            output.writestr(cell_name(cell), record.tobytes())
    return len(cells)


def refresh():
    metadata = json.loads(download(f"{ZARR}/.zmetadata"))["metadata"]
    lat, lon = (array(metadata, name, "0") for name in ("lat", "lon"))
    time = array(metadata, "time", "0")
    if not (np.allclose(lat, np.linspace(-90, 90, 361), rtol=0, atol=1e-9)
            and np.allclose(lon, np.arange(-180, 180, .625), rtol=0, atol=1e-9)
            and np.array_equal(time, np.arange(len(time)))
            and metadata["time/.zattrs"]["units"].startswith("days since 1980-12-31")
            and all(metadata[f"{key}/.zarray"]["chunks"][1:] == [TILE_SIZE, TILE_SIZE] for key in PARAMETERS)):
        raise ValueError("Unexpected NASA POWER grid or date indexing.")
    availability = json.loads(download(f"{BUCKET}/last_available.json"))
    last = availability["merra2"]["temporal"]["daily"]["lst"]
    origin = pd.Timestamp("1980-12-31")
    first, end = (pd.Timestamp(FIRST) - origin).days, (pd.Timestamp(last) - origin).days + 1
    cells = sorted({grid_cell(*coordinates(county)) for county in county_features()})
    tiles = defaultdict(list)
    for cell in cells:
        tiles[tile_for(cell)].append(cell)

    ARCHIVE.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=ARCHIVE) as directory, ThreadPoolExecutor(max_workers=8) as workers:
        staging = Path(directory)
        for number, count in enumerate(workers.map(lambda tile: save_tile(tile, metadata, first, end, staging),
                                                   sorted(tiles.items())), 1):
            print(f"Tile {number}/{len(tiles)} · {count} grid points", flush=True)
        manifest = staging / "coverage.json"
        manifest.write_text(json.dumps({"first": FIRST, "last": last, "cells": list(map(cell_name, cells))}) + "\n",
                            encoding="utf-8")
        for result in (*staging.glob("*.zip"), manifest):
            # Moving directly out of the private staging directory can retain its Windows ACL.
            pending = ARCHIVE / f".{staging.name}.{result.name}"
            try:
                copyfile(result, pending)
                pending.replace(ARCHIVE / result.name)
            finally:
                pending.unlink(missing_ok=True)
    print(f"Saved {len(cells):,} NASA POWER points from {FIRST} through {last}.")


if __name__ == "__main__":
    refresh()
