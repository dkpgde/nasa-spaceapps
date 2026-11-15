"""Show a world overview and pick U.S. counties and crop sites."""

import json
from html import escape
from pathlib import Path
from urllib.parse import quote

import streamlit as st

from grid_weather import cell_name, coverage, grid_cell
from locations import BOONE_COUNTY, BOUNDARY_SOURCE, SITES, coordinates, county_at, county_features, county_name
from place_search import GEONAMES_SOURCE, Place, search_places


SELECTED_COUNTY = "comparison-county"
MAP_REGION = "coverage-map-region"
MAP_STYLE = "coverage-map-style"
MAP_FOCUS = "coverage-map-focus"
MAP_REVISION = "coverage-map-revision"
SEARCH_INPUT = "map-search-query"
SEARCH_RESULTS = "map-search-results"
SEARCH_CHOICE = "map-search-choice"
SEARCH_ERROR = "map-search-error"
SATELLITE = "Satellite"
COVERAGE = "Weather coverage"
IMAGERY_SOURCE = "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer"
MERCATOR_LIMIT = 85.05112878
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
SEARCH_PIN = pin_icon("#245cc4", '<circle cx="16" cy="16" r="5" fill="white"/>')
_DECK_LIBRARY = (ASSETS / "deck.gl-9.2.10.min.js").read_text(encoding="utf-8")
_MAP_SCRIPT = (ASSETS / "coverage-map.js").read_text(encoding="utf-8")
_COVERAGE_MAP = st.components.v2.component(
    "rotationlab_map",
    html=f"""
        <div class="map-shell">
            <div class="map-frame" role="region" aria-label="Location map"></div>
            <div class="map-controls" aria-label="Map controls">
                <button type="button" data-zoom="1" aria-label="Zoom in" title="Zoom in">+</button>
                <button type="button" data-zoom="-1" aria-label="Zoom out" title="Zoom out">−</button>
                <button type="button" data-recenter aria-label="Recenter map" title="Recenter map">⌖</button>
            </div>
            <p class="map-status" role="status" hidden></p>
            <div class="map-attribution" hidden>
                <a href="{IMAGERY_SOURCE}" target="_blank" rel="noopener noreferrer">
                    Esri, Vantor, Earthstar Geographics, GIS User Community
                </a>
            </div>
        </div>
    """,
    css="""
        .map-shell { position: relative; overflow: hidden; border-radius: .95rem; isolation: isolate;
                     border: 1px solid #afc1b7; background: #e9f1ed; }
        .map-frame { height: clamp(360px, 60vh, 630px); width: 100%; position: relative; }
        .map-controls { position: absolute; right: .8rem; top: .8rem; display: grid; gap: 1px;
                        overflow: hidden; border-radius: .65rem; background: #d5e3dc;
                        box-shadow: 0 3px 14px #0d2b3260; }
        .map-controls button { background: #fff; color: #17382e; border: 0; width: 2.5rem;
                               height: 2.5rem; cursor: pointer; font: 600 1.3rem system-ui; }
        .map-controls button:hover { background: #e8f5ec; }
        .map-controls button:focus-visible { outline: 2px solid #245cc4; outline-offset: -4px; }
        .map-status, .map-attribution { position: absolute; bottom: .6rem; border-radius: .35rem;
              background: #122d29ed; color: #fff; padding: .3rem .55rem; margin: 0; font: .7rem system-ui; }
        .map-status { left: .6rem; bottom: 2.45rem; max-width: calc(100% - 2.5rem); }
        .map-attribution { right: .6rem; max-width: calc(100% - 2.5rem); }
        .map-attribution a { color: inherit; }
        .deck-tooltip { font: 13px system-ui, sans-serif; }
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
        if region in ("Lower 48", "Alaska", "Hawaii") and county_region != region:
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
        st.session_state.pop(MAP_FOCUS, None)


def focus_place(place, *, study_site=False):
    county = county_at(place.latitude, place.longitude)
    st.session_state[SELECTED_COUNTY] = county
    st.session_state[MAP_REVISION] = st.session_state.get(MAP_REVISION, 0) + 1
    st.session_state[MAP_FOCUS] = place
    if not study_site:
        st.session_state[MAP_STYLE] = SATELLITE if abs(place.latitude) <= MERCATOR_LIMIT else COVERAGE
    st.session_state[MAP_REGION] = "World" if not study_site else "Lower 48"


def submit_search():
    query = st.session_state[SEARCH_INPUT].strip()
    try:
        results = search_places(query)
    except ValueError as error:
        st.session_state[SEARCH_ERROR] = str(error)
        return
    except OSError:
        st.session_state[SEARCH_ERROR] = "City search is unavailable. You can still search by decimal coordinates."
        return
    if not results:
        st.session_state[SEARCH_ERROR] = "Enter a city and state or country, or decimal coordinates such as 42.0167, -93.7833."
        return
    st.session_state.pop(SEARCH_ERROR, None)
    st.session_state[SEARCH_RESULTS] = results
    st.session_state[SEARCH_CHOICE] = 0
    focus_place(results[0])


def choose_search_result():
    focus_place(st.session_state[SEARCH_RESULTS][st.session_state[SEARCH_CHOICE]])


def choose_site(county):
    name, latitude, longitude = SITES[county]
    focus_place(Place(name, latitude, longitude, zoom=14), study_site=True)
    st.session_state[SELECTED_COUNTY] = county
    st.session_state.pop(SEARCH_RESULTS, None)
    st.session_state.pop(SEARCH_ERROR, None)


def show_location_picker():
    active = st.session_state.get(SELECTED_COUNTY, BOONE_COUNTY)
    with st.container(border=True, key="location_picker"):
        st.header("Choose a location", anchor="choose-location")
        st.caption("Pick a research site for rotation comparisons. Use the map to look up county weather.")
        with st.container(horizontal=True):
            for county, (name, _, _) in SITES.items():
                st.button(name, type="primary" if county == active else "secondary",
                          on_click=choose_site, args=(county,))
        with st.expander("Find a city, coordinates, or county on the map", key="location-map-details",
                         on_change="rerun") as details:
            if details.open:
                show_map(active)
    return active


def show_map(active):
    with st.form("location-search", border=False):
        search, submit = st.columns([5, 1], vertical_alignment="bottom")
        search.text_input("City or coordinates", placeholder="Ames, Iowa or 42.0167, -93.7833",
                          max_chars=120, key=SEARCH_INPUT)
        submit.form_submit_button("Find", type="primary", icon=":material/search:",
                                  on_click=submit_search, width="stretch")
    if error := st.session_state.get(SEARCH_ERROR):
        st.warning(error)
    if len(results := st.session_state.get(SEARCH_RESULTS, [])) > 1:
        st.selectbox("Matching places", range(len(results)), format_func=lambda i: results[i].label,
                     key=SEARCH_CHOICE, on_change=choose_search_result)
    mode = st.radio("Map layer", (SATELLITE, COVERAGE), horizontal=True, key=MAP_STYLE)
    st.caption("Drag to explore or use the zoom buttons. Select a U.S. county for weather or a study-site pin for rotations.")
    if mode == COVERAGE:
        region = st.radio("Map area", VIEWS, horizontal=True, key=MAP_REGION)
        st.html(
            '<div class="coverage-legend">'
            '<span><i class="coverage-swatch"></i> NASA POWER weather</span>'
            '<span><i class="crop-swatch"></i> Crop calendars</span></div>'
        )
    else:
        region = SATELLITE
    map_key = f"coverage-map-{region}"
    map_slot = st.container()
    focus = st.session_state.get(MAP_FOCUS)
    if mode == SATELLITE and focus and abs(focus.latitude) > MERCATOR_LIMIT:
        map_slot.info("Polar coordinates are visible in Weather coverage → World.")
    if focus:
        coordinate_label = f"{focus.latitude:.5f}, {focus.longitude:.5f}"
        detail = "" if focus.label == coordinate_label else f"<span>{coordinate_label}</span>"
        map_slot.html(f'<div class="map-result"><strong>{escape(focus.label)}</strong>{detail}</div>')
        location = quote(f"{focus.latitude:.6f}, {focus.longitude:.6f}", safe="")
        map_slot.link_button("Open in Google Earth", f"https://earth.google.com/web/search/{location}",
                             icon=":material/open_in_new:")
    counties = map_data(region, coverage()["cells"])
    crop_sites = [
        {"county": county, "position": [lon, lat], "icon": SELECTED_PIN if county == active else PIN,
         "tooltip": f"{name} · Crop calendars"}
        for county, (name, lat, lon) in SITES.items()
    ] if region in ("World", "Lower 48", SATELLITE) else []
    satellite = mode == SATELLITE
    lat, lon = coordinates(active if active in county_features() else BOONE_COUNTY)
    if satellite:
        zoom = 13 if active in SITES else 10
    else:
        lat, lon, zoom = VIEWS[region]
    if focus and ((satellite and abs(focus.latitude) <= MERCATOR_LIMIT) or region == "World" or
                  region == "Lower 48" and not satellite and focus.label in {site[0] for site in SITES.values()}):
        lat, lon = focus.latitude, focus.longitude
        zoom = focus.zoom if satellite else 5.5
    with map_slot:
        _COVERAGE_MAP(
            key=map_key, on_picked_change=lambda: select_from_map(map_key), height="content",
            data={"region": region, "countries": world_boundaries(), "counties": counties, "sites": crop_sites,
                  "active": active, "siteZoom": 14 if satellite else 5.5,
                  "imagery": f"{IMAGERY_SOURCE}/tile/{{z}}/{{y}}/{{x}}" if satellite else None,
                  "revision": st.session_state.get(MAP_REVISION, 0),
                  "search": {"position": [focus.longitude, focus.latitude], "tooltip": focus.label, "icon": SEARCH_PIN}
                            if focus and (not satellite or abs(focus.latitude) <= MERCATOR_LIMIT) else None,
                  "camera": {"latitude": lat, "longitude": lon, "zoom": zoom,
                             "minZoom": 1 if satellite else -.4, "maxZoom": 19 if satellite else 10}},
        )
    st.caption(f"Place names · [GeoNames]({GEONAMES_SOURCE}) · Boundaries · "
               f"[Natural Earth]({WORLD_SOURCE}) · [U.S. Census Bureau]({BOUNDARY_SOURCE})")
