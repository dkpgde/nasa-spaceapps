"""Show a world overview and pick U.S. counties and crop sites."""

import json
from pathlib import Path
from urllib.parse import quote

import streamlit as st

from grid_weather import cell_name, coverage, grid_cell
from locations import BOONE_COUNTY, BOUNDARY_SOURCE, SITES, coordinates, county_features, county_name


SELECTED_COUNTY = "comparison-county"
MAP_REGION = "coverage-map-region"
VIEWS = {
    "World": (33.0, -90.0, 2.25),
    "Lower 48": (38.6, -96.0, 3.05),
    "Alaska": (61.0, -153.0, 3.0),
    "Hawaii": (20.8, -157.0, 5.0),
}
WORLD_BOUNDARIES = Path(__file__).with_name("data") / "world-countries.geojson"
WORLD_SOURCE = "https://www.naturalearthdata.com/downloads/110m-cultural-vectors/110m-admin-0-countries/"
ASSETS = Path(__file__).with_name("assets")
CROP_COLOR = "#365c4b"


def pin_icon(fill, symbol):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="40" viewBox="0 0 32 40">'
        '<path d="M16 38C13 33 2 22 2 16a14 14 0 1 1 28 0c0 6-11 17-14 22Z" '
        f'fill="{fill}" stroke="white" stroke-width="2"/>{symbol}</svg>'
    )
    return {"url": "data:image/svg+xml," + quote(svg), "width": 32, "height": 40, "anchorY": 38}


PIN = pin_icon(CROP_COLOR, '<circle cx="16" cy="16" r="4.5" fill="white"/>')
SELECTED_PIN = pin_icon(
    "#9c4700", '<path d="m10 16 4 4 8-8" fill="none" stroke="white" stroke-width="3"/>'
)
_DECK_LIBRARY = (ASSETS / "deck.gl-9.2.10.min.js").read_text(encoding="utf-8")
_MAP_SCRIPT = (ASSETS / "coverage-map.js").read_text(encoding="utf-8")
_COVERAGE_MAP = st.components.v2.component(
    "rotationlab_map",
    html='<div class="map-frame" role="region" aria-label="World map and U.S. weather coverage"></div>',
    css="""
        .map-frame { height: 400px; width: 100%; position: relative; overflow: hidden;
                     border-radius: .4rem; background: #ecf0e8; }
        .deck-tooltip { font: 13px 'Segoe UI', sans-serif; }
    """,
    js="const deckLibrary = (() => { const module = { exports: {} }; const exports = module.exports;\n"
    + _DECK_LIBRARY + "\nreturn module.exports; })();\n" + _MAP_SCRIPT,
)


@st.cache_data
def map_data(region, cells):
    available_cells = set(cells)
    counties = []
    for county, feature in county_features().items():
        county_region = {"02": "Alaska", "15": "Hawaii"}.get(county[:2], "Lower 48")
        if region != "World" and county_region != region:
            continue
        available = county == BOONE_COUNTY or cell_name(grid_cell(*coordinates(county))) in available_cells
        geometry = feature["geometry"]
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        label = "NASA POWER weather" if available else "Weather unavailable"
        for polygon in polygons:
            counties.append({
                "county": county, "polygon": polygon,
                "fill": [181, 211, 227] if available else [236, 240, 232],
                "tooltip": f"{county_name(county)} · {label}",
            })
    return counties


@st.cache_data
def world_boundaries():
    geojson = json.loads(WORLD_BOUNDARIES.read_text(encoding="utf-8"))
    for feature in geojson["features"]:
        props = feature["properties"]
        props["fill"] = [208, 226, 234] if props.get("ocean") else [222, 231, 219]
    return geojson


def select_from_map(map_key):
    county = st.session_state[map_key].picked
    if county in county_features():
        st.session_state[SELECTED_COUNTY] = county


def show_location_picker():
    with st.container(border=True, key="location_picker"):
        st.markdown("### Choose a location")
        st.caption("Drag and zoom to explore. Click a U.S. county for weather or a study-site pin for crop rotations.")
        region = st.radio("Map area", VIEWS, horizontal=True, key=MAP_REGION)
        map_key = f"coverage-map-{region}"
        st.html(
            '<div class="coverage-legend">'
            '<span><i class="coverage-swatch"></i> NASA POWER weather</span>'
            '<span><i class="crop-swatch"></i> Crop calendars</span></div>'
        )
        map_slot = st.container()
        with st.container(horizontal=True):
            for county, (name, _, _) in SITES.items():
                st.button(name, on_click=st.session_state.update,
                          kwargs={SELECTED_COUNTY: county, MAP_REGION: "Lower 48"})

    active = st.session_state.get(SELECTED_COUNTY, BOONE_COUNTY)
    counties = map_data(region, coverage()["cells"])
    crop_sites = [
        {"county": county, "position": [lon, lat], "icon": SELECTED_PIN if county == active else PIN,
         "tooltip": f"{name} · Crop calendars"}
        for county, (name, lat, lon) in SITES.items()
    ] if region in ("World", "Lower 48") else []
    lat, lon, zoom = VIEWS[region]
    with map_slot:
        _COVERAGE_MAP(
            key=map_key, on_picked_change=lambda: select_from_map(map_key), height=400,
            data={"region": region, "countries": world_boundaries(), "counties": counties, "sites": crop_sites,
                  "active": active, "siteZoom": 5.5,
                  "camera": {"latitude": lat, "longitude": lon, "zoom": zoom,
                                                "minZoom": -.4, "maxZoom": 10}},
        )
    map_slot.caption(f"Boundaries · [Natural Earth]({WORLD_SOURCE}) · [U.S. Census Bureau]({BOUNDARY_SOURCE})")
    return active
