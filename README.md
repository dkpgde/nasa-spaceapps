# RotationLab

A Streamlit dashboard for exploring U.S. weather and comparing crop rotations at Marsden Farm in Iowa and the Eastern Nebraska Research and Extension Center near Mead. See [ROTATIONLAB.md](ROTATIONLAB.md) for the original Marsden presets and rainfall methods.

## Run locally

Python 3.11 or later:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Choose **Marsden Farm** or **Mead ENREC**, select rotations and a shared weather period, then choose a goal in **Which rotation fits your goal?** The decision tool compares one year or the whole four-year period, shows ties and missing results, and adds a summary to each plan card. The four-year view adds days across the period for cover and exposure counts, averages eligible planting dates per year that needs planting, and uses the worst annual dry spell. Charts and source data are below the decision summaries.

Open **Find a city, coordinates, or county on the map** to search for a city such as **Ames, Iowa** or decimal coordinates such as **42.0167, -93.7833**. The map zooms to the point and offers a Google Earth link. Add a state or country to distinguish cities with the same name. The offline index contains GeoNames `cities1000` records, with place names, first-level regions, country names, coordinates, population, and alternate names for larger cities. [GeoNames data](https://www.geonames.org/export/) · [GeoNames CC BY 4.0 license](https://download.geonames.org/export/dump/readme.txt).

**Satellite** uses [Esri World Imagery](https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer) to show fields and vegetation. Imagery tiles load over the internet and the capture date and resolution vary by location. **Weather coverage** works offline and offers the globe, Lower 48, Alaska, and Hawaii views. Blue shading marks daily NASA POWER coverage for 3,143 counties and county equivalents across all 50 states and D.C. Select a county to view and download its weather series. Each county uses the native 0.5° × 0.625° MERRA-2 grid point closest to its Census reference coordinate. The two crop sites use their research-area coordinates. [Natural Earth world boundaries](https://www.naturalearthdata.com/downloads/110m-cultural-vectors/110m-admin-0-countries/) · [Census 2020 county boundaries and reference points](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/55).

The offline archive contains `PRECTOTCORR` and `T2M` in Local Solar Time from January 1981 through September 2026 at 1,906 distinct grid points. To update it, install `numcodecs` in the project virtual environment and run `python download_grid_weather.py`. The importer reads the primary [NASA POWER Analysis Ready Datastore](https://power.larc.nasa.gov/docs/services/aws/). Normal app use needs only the packages in `requirements.txt`.

Green pins open the crop-rotation comparisons. **Marsden Farm** offers 10 crop and forage choices, including winter wheat, winter grain rye and buckwheat. **Mead ENREC** offers 11 choices, including grain sorghum, field pea, proso millet and sunflower, with published corn–soybean, sorghum–soybean and continuous corn examples. The sources shown on each crop calendar distinguish statewide date ranges from local trial evidence. A crop without a sensitive-stage window still has planting and harvest data. Fall-planted grains are shown in their harvest year. [Iowa USDA dates](https://www.nass.usda.gov/Publications/Todays_Reports/reports/fcdate10.pdf#page=39) · [Nebraska USDA dates](https://esmis.nal.usda.gov/sites/default/release-files/vm40xr56k/dv13zw65p/w9505297d/planting-10-29-2010.pdf#page=42) · [Mead rotation trial](https://cropwatch.unl.edu/2021/more-diverse-crop-rotations-improve-yield-yield-stability-and-soil-health/).

**Custom years** opens on 2010–2013 and accepts starting years from 1981 through 2028 in Iowa and 1981 through 2022 in Nebraska. At Marsden, NASA POWER weather runs through November 12, 2026. An ECMWF seasonal forecast fills the rest of 2026, and NASA climate projections cover 2027–2031.

**Average**, **Wet Spring**, and **Dry Summer** use only complete historical years through 2025. Iowa's preset baseline starts in 1991 and Mead's starts in 1981. **Future projections** offers four-year blocks at Marsden starting in 2027 or 2028. Choose one year to inspect and expand **See dates, rules and sources** on a plan for the calculation details and calendar.

At Marsden Farm, use **Historical precipitation** to select NASA POWER, GPM IMERG, or PRISM to run the comparison with that product. IMERG and PRISM use complete historical blocks through 2025. **Rotation impacts** also compares freezing air temperatures during planting windows, high temperatures during sensitive growth, and low regional root-zone moisture during sensitive growth. **Boone County observations** shows the USDA soil map unit and horizons, SRTM elevation, CDL crop classifications, MODIS greenness, and weather and moisture charts. Coverage and data provenance are documented in [ROTATIONLAB.md](ROTATIONLAB.md#boone-county-observations).

Each card shows its four-year crop sequence and highlights the selected year. Its decision summary compares living cover, heavy rain without cover, eligible planting days, and the longest dry spell. Planting checks combine low-rain windows with any required wait after ending a cover crop, with each planting date counted once. Established hay shows **Not needed** for planting. Download all four years as a CSV with the results and the separate rainfall and termination checks. In the CSV, `N/A` means a check does not apply and `Unavailable` means required information is missing. **Restore starting plans** restores the three starting rotations while keeping the selected weather.

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

The standalone calendar uses a representative Clarion loam series profile. The Marsden comparison uses the USDA SSURGO map unit intersecting its representative observation coordinate. These mapped soil estimates and regional observations help interpret exposure. Field access, erosion, yield, and rotation-induced changes in soil water or organic matter require local measurements or additional modeling.

## Verification

```sh
.venv/bin/python -m pytest -q
```

Tests check sourced planting/harvest endpoints, repeated sequences and both starting phases, four-year boundaries, partial coverage, known empty versus unavailable rules, explicit prior-phase carryover, leap days, invalid inputs, and Streamlit controls/error states. Browser verification checks the rendered chart and source display.
