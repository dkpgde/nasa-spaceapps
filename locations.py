"""Study sites and Census county boundaries used by the location picker."""

from functools import lru_cache
import json
from pathlib import Path


BOONE_COUNTY, SAUNDERS_COUNTY = "19015", "31155"
BOUNDARIES = Path(__file__).with_name("data") / "us-counties.geojson"
BOUNDARY_SOURCE = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/55"
SITES = {
    BOONE_COUNTY: ("Marsden Farm, Iowa", 42.016667, -93.783333),
    SAUNDERS_COUNTY: ("Mead ENREC, Nebraska", 41.1797, -96.4397),
}


@lru_cache(maxsize=1)
def county_features():
    features = json.loads(BOUNDARIES.read_text(encoding="utf-8"))["features"]
    return {feature["properties"]["GEOID"]: feature for feature in features}


def coordinates(county):
    if county in SITES:
        return SITES[county][1:]
    props = county_features()[county]["properties"]
    return float(props["INTPTLAT"]), float(props["INTPTLON"])


def county_name(county):
    props = county_features()[county]["properties"]
    return f"{props['NAME']}, {props['STATE']}"
