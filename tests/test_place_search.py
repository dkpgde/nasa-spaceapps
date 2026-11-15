from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from locations import BOONE_COUNTY, county_at
from place_search import coordinate_place, search_places


def test_coordinates_validate_ranges_and_locate_counties():
    point = coordinate_place("42.0167° N 93.7833° W")
    assert (point.latitude, point.longitude) == (42.0167, -93.7833)
    assert county_at(point.latitude, point.longitude) == BOONE_COUNTY
    assert county_at(21.3069, -157.8583) == "15003"
    assert county_at(48.8534, 2.3488) is None
    with pytest.raises(ValueError, match="latitude"):
        coordinate_place("95, -93.7833")


def test_city_index_handles_regions_and_alternate_names():
    assert search_places("Ames, Iowa")[0].label == "Ames, Iowa, United States"
    assert search_places("Paris, TX")[0].label == "Paris, Texas, United States"
    assert search_places("Paris France")[0].label == "Paris, Île-de-France, France"
    assert search_places("München")[0].label.startswith("Munich,")
    assert len(search_places("Springfield")) > 1


def test_search_updates_map_and_only_shows_weather_for_the_selected_county():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=15)
    app.session_state["location-map-details"] = True
    app.run()
    app.text_input(key="map-search-query").set_value("48.8534, 2.3488")
    next(button for button in app.button if button.label == "Find").click().run()
    assert not app.exception
    assert app.session_state["comparison-county"] is None
    assert any("The pin is on the map" in note.value for note in app.info)

    app.text_input(key="map-search-query").set_value("42.0167 -93.7833")
    next(button for button in app.button if button.label == "Find").click().run()
    assert not app.exception
    assert app.session_state["comparison-county"] == BOONE_COUNTY
    assert app.selectbox(key="rain-source").value == "NASA POWER"
