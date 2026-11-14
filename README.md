# RotationLab

A Streamlit dashboard for comparing crop rotations in Boone County, Iowa. See [ROTATIONLAB.md](ROTATIONLAB.md) for the rotation presets, weather scenarios, and data sources.

## Run locally

Python 3.11 or later:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

The dashboard runs offline with bundled NASA weather. Choose weather and a year to inspect, then edit any of the comparison plans. Expand **See dates, rules and sources** on a plan for the calculation details and calendar.

Each card shows its four-year crop sequence and highlights the selected year. The three main results are heavy rain without living cover, days passing planting checks, and the longest dry spell during sensitive growth. Planting checks combine low-rain windows with any required wait after ending a cover crop; each planting date counts once. Established hay shows **Not needed** for planting. Download all four years as a CSV with the main results and the separate rainfall and termination checks. In the CSV, `N/A` means a check does not apply and `Unavailable` means required information is missing. **Restore starting plans** restores the three starting rotations while keeping the selected weather.

Run `python -m streamlit run timeline_app.py` to open the standalone calendar from [Issue #3](https://github.com/dkpgde/nasa-spaceapps/issues/3). Its default range is 2017–2020. Use the sidebar to change the starting crop, first year, and coverage dates. The timeline includes source links, a soil profile, a CSV export, and a selectable cereal rye recipe before soybean. Its rainfall-based fieldwork checks use the same shared crop and recipe calendars with bundled historical weather.

## Shared representation

`rotationlab/model.py` has no Streamlit or weather dependency:

- `RotationPlan`: one to four ordered crop IDs, zero-based starting phase, source references and custom-plan flag.
- `CropCalendar` / `WindowRule`: crop, planting, harvest, living-cover, sensitive-growth and termination rules. Rules include source IDs, explicit assumptions and year offsets for future overwinter cover recipes.
- `expand_rotation(plan, start, end, calendars, coverage=None)`: repeats the rotation over up to four calendar years and identifies the preceding phase. Starting phase belongs to `start.year`. All endpoints are inclusive. Intervals are clipped to both requested dates and optional available coverage (for example, validated weather coverage supplied by Issue #2).
- `ExpandedTimeline`: ordered crop years, dated windows (including original dates and carryover flag), and per-year/crop/category availability. `query(year, crop_id, kind)` returns availability, intervals and a missing-data reason.

`rules=None` or an unknown crop means unavailable. An empty tuple means a known valid calendar with no intervals. Set `unavailable_rules={"sensitive": "No sourced stage rule"}` for a partially known calendar; never substitute an empty tuple for a missing rule. Downstream calculations must check availability before interpreting interval counts. A valid window outside coverage returns an available, empty result.

Explicit living-cover rules from the preceding phase may carry into the supplied range, but are clipped to available dates. The baseline corn–soybean plan has no winter living cover. The cereal rye example applies the MCCC-103 recipe to grain corn → soybean transitions. The central Iowa October 28 cutoff is exclusive; the demo assumes next-day seeding after harvest and a seven-day establishment lag after the last eligible seeding date for the planned cover band. The spring search starts April 1 and checks the recipe’s gap of more than 10 days before soybean planting. Scout rye height and growth separately. Starting with soybean can show conditional rye carryover from the preceding grain-corn phase, clipped to the supplied coverage.

```python
from datetime import date
from rotationlab.catalog import load_catalog
from rotationlab.model import Availability, RotationPlan, expand_rotation

_, calendars = load_catalog()
plan = RotationPlan("Corn–soybean", ("grain_corn", "soybean"), starting_phase=0)
timeline = expand_rotation(plan, date(2017, 1, 1), date(2020, 12, 31), calendars)
cover = timeline.query(2017, "grain_corn", "living_cover")
if cover.availability == Availability.AVAILABLE:
    print(cover.intervals)
```

## Sources and limits

The versioned offline catalog is `rotationlab/data/boone.json`; each rule carries source IDs resolving to visible citations and assumptions. Iowa State planting guidance supplies planting windows; USDA NASS (2010), p.39 supplies historical Iowa harvest ranges. Iowa State water-use guidance documents sensitive growth stages. Exact living-cover and sensitive-stage calendar boundaries are **fixed demo proxies**, not observed phenology or weather-dependent estimates. Crop-season bars use the same assumed emergence-to-senescence period as living cover.

The location is the Marsden study area reported by Lazicki et al. (2016). Clarion loam is a locally documented representative series, with a profile from the USDA NRCS Official Series Description. It is **not** a verified SSURGO map unit for the displayed coordinate; the site also includes other soils. No field access, erosion, yield or soil-water calculation is made here.

## Verification

```sh
.venv/bin/python -m pytest -q
```

Tests check sourced planting/harvest endpoints, repeated sequences and both starting phases, four-year boundaries, partial coverage, known empty versus unavailable rules, explicit prior-phase carryover, leap days, invalid inputs, and Streamlit controls/error states. Browser verification checks the rendered chart and source display.
