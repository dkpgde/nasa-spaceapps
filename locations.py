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


@lru_cache(maxsize=1)
def county_polygons():
    indexed = []
    for county, feature in county_features().items():
        geometry = feature["geometry"]
        polygons = geometry["coordinates"]
        if geometry["type"] == "Polygon":
            polygons = [polygons]
        for polygon in polygons:
            outer = polygon[0]
            xs, ys = zip(*outer)
            crosses_dateline = max(xs) - min(xs) > 180
            if crosses_dateline:
                polygon = [[(x % 360, y) for x, y in ring] for ring in polygon]
                xs, ys = zip(*polygon[0])
            indexed.append((county, (min(xs), min(ys), max(xs), max(ys)), polygon, crosses_dateline))
    return indexed


def ring_contains(ring, longitude, latitude):
    inside = False
    previous_x, previous_y = ring[-1]
    for x, y in ring:
        if (y > latitude) != (previous_y > latitude):
            edge_x = x + (previous_x - x) * (latitude - y) / (previous_y - y)
            if longitude < edge_x:
                inside = not inside
        previous_x, previous_y = x, y
    return inside


def county_at(latitude, longitude):
    for county, (west, south, east, north), rings, crosses_dateline in county_polygons():
        x = longitude % 360 if crosses_dateline else longitude
        if west <= x <= east and south <= latitude <= north:
            outer, *holes = rings
            if ring_contains(outer, x, latitude) and not any(ring_contains(hole, x, latitude) for hole in holes):
                return county
    return None
