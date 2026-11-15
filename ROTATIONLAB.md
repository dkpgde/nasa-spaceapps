# RotationLab

## Summary

Compare up to three Iowa crop plans side by side. Start with a prefilled comparison, load a rotation studied in Iowa, or build a plan that matches the farm. Choose **Custom years** or a preset to see how each plan fares under the same daily weather. The demo shows where planned living cover lines up with heavy rain, where fieldwork windows get squeezed, and which crops encounter dry spells during sensitive growth stages.

## What we’ll build

One Streamlit comparison screen opens with a representative Boone County, Iowa location, a sourced local soil profile, and locally sourced crop calendars. The first click can still change the weather scenario. The default comparison opens with corn–soybean, corn–soybean with cereal rye ahead of soybean, and corn–soybean–oats with red clover. Each plan can be replaced or edited.

The rotation builder lets farmers order one to four crop years, choose the starting phase, and add a cover crop between compatible cash crops. Start with grain corn, corn silage, soybean, spring oats, oats with red clover, oats with alfalfa, and established alfalfa hay. Include the following rotations from [Iowa State's Marsden Farm study in Boone County](https://inrc.cals.iastate.edu/project-location/marsden-long-term-rotation-study).

| Years | Rotation studied at Marsden Farm |
| --- | --- |
| 2 | Corn → soybeans |
| 3 | Corn → soybeans → oats undersown with red clover. Keep the clover after oat harvest and show its carryover into the following year. |
| 4 | Corn → soybeans → oats undersown with alfalfa → alfalfa hay |

Add all four [Iowa starter cover-crop recipes](https://www.midwestcovercrops.org/iowa) as options for the matching transitions.

| Cash crop transition | Cover crop |
| --- | --- |
| Grain corn → soybean | Cereal rye |
| Soybean → corn | Oats that winterkill |
| Corn silage → soybean | Cereal rye |
| Corn silage → corn | Cereal rye |

Model grain corn and corn silage separately so the recipes use the right harvest window. Use the recipe's seeding window and, where applicable, spring termination guidance. Distinguish spring oats grown for grain from fall oats used as cover. Label custom plans separately from the published examples and show which checks are unavailable when a crop or operation lacks a sourced calendar or rule. The starting catalog covers the Boone County study and the council's Iowa starter recipes. Iowa conservation planning also covers other crops and systems, with choices that depend on the field and its goals. [Iowa conservation practice scenarios](https://www.nrcs.usda.gov/sites/default/files/2026-04/FY26%20FA%20Program%20Scenario%20Booklet%20April%202026.pdf)

Use cached daily NASA POWER precipitation and temperature records. Check that both series have complete data at the chosen location before settling on the demo years. Use [Iowa State crop guidance](https://crops.extension.iastate.edu/post/corn-and-soybean-planting-date-considerations), [local oats and clover trials](https://practicalfarmers.org/resources/research-reports/establishing-legume-forages-with-oats/), and [USDA soil survey data](https://www.nrcs.usda.gov/resources/data-and-reports/ssurgo-portal) for the prefilled context. Keep the crop calendar sources and rule definitions visible. [NASA POWER daily data](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) · [Iowa State winter rye guidance](https://store.extension.iastate.edu/product/15548.pdf)

## Weather scenarios and results

Use complete, consecutive four-year weather blocks so the full alfalfa rotation fits and fall seeding, winter cover, and spring termination stay in order. Repeat shorter rotations across the same four years. Use the selected starting phase to determine the preceding crop at the start of the timeline, and show any carryover cover only where the plan and available weather support it. Default to Custom years and let the user choose the starting year. Pick an Average block with a year near the historical median for both spring and summer rainfall. For Wet Spring, select the block by March–May rainfall in year two, when the default plan terminates rye ahead of soybean. For Dry Summer, select by June–August rainfall in year three, when the defaults compare corn with oats undersown with red clover. Apply the same weather block and rainfall rules to every plan. Display the years, rainfall totals, and selection rule.

| Scenario | What to show |
| --- | --- |
| Custom years | Compare plans over four years of available weather starting in the selected year. |
| Average | Establish the baseline crop calendars, planned living cover, and fieldwork windows. |
| Wet Spring | Count heavy-rain days outside planned living cover. Show qualifying low-rain windows for planting and, where applicable, cover crop termination. Check their order and any interval required by the selected recipe. |
| Dry Summer | Highlight the longest low-rain stretch within each crop’s documented sensitive growth window. Show the dates and number of days so the farmer can see which crops were exposed and when. |

Show all three checks in every scenario and emphasize the ones relevant to the selected weather. Use the same documented rainfall thresholds across plans. Label the results **planned living cover**, **rainfall-based fieldwork windows**, and **dry-spell exposure**. Soil texture is context for interpreting the results. Actual field access, crop water stress, and erosion depend on field conditions and management.

### Run the comparison

Install the dependencies with `python -m pip install -r requirements.txt`, then run
`python -m streamlit run app.py`. The app loads the bundled weather files locally.
Run `python weather.py` to refresh the 1991–2025 cache from NASA POWER.

For the two-minute demo, open on Custom years and compare the cash crop and cover
crop timelines. Switch to **Wet Spring** to see the 2013 heavy-rain counts and
rye termination-to-planting pairs. Switch to **Dry Summer** to compare the
2013 grain corn and oats sensitive windows. Open **Edit plan** on the third
card, select the four-year Marsden rotation, and click **Load preset**. Select
the fourth year to see established alfalfa hay. Expand **Rainfall checks and
calendar** on any card for dates and sources. Weather data and assumptions are
below the comparison.

The request uses a representative point in the Marsden Farm experiment area
(42.013628° N, 93.784149° W). The bundled response preserves NASA's header with
the coordinates, units, dataset, missing-value marker, and time standard. It
contains corrected daily precipitation (mm/day) and mean 2 m air temperature
(°C) from MERRA-2 in Local Solar Time. Calendar dates are derived from NASA's
year and day of year. Both variables must be present on every date in the
bundled 1991–2025 period, including February 29 in leap years.
[Marsden Farm coordinates](https://www.tandfonline.com/doi/full/10.1080/21683565.2021.2019167) · [NASA POWER daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/)

The preset reference period is **1991–2025**. RotationLab computes its own
seasonal totals from NASA POWER records. Eligible reference years are
1992–2023 for Average and Wet Spring and 1993–2024
for Dry Summer, so each reference year fits its position in a complete four-year block.

- **Custom years** accepts any start from 1991 to 2028 and opens on 2010–2013.
- **Average** uses year two. Rank March–May and June–August totals separately
  across all 35 reference years, averaging tied ranks. Choose the eligible year
  with the smallest maximum distance from the middle rank (18). Break ties
  by total rank distance across both seasons, then by the earlier year.
- **Wet Spring** uses year two and maximizes March–May rainfall among eligible years.
  Break ties by the earlier year.
- **Dry Summer** uses year three and minimizes June–August rainfall among eligible years.
  Break ties by the earlier year.

The wet spring and dry summer both occurred in 2013. They are placed at different
positions in their respective weather blocks to align with the rotation years.
Downstream analysis can call `select_scenario(name, load_weather())` from
`weather.py` to reproduce a historical preset.

## Build order for the weekend

1. **Get one comparison working.** Fetch and save NASA weather for the demo location. Build the three default plans from crop calendars and cover crop rules, and pick the historical blocks. Check the dates and counts for one wet and one dry example.
2. **Add the rotation builder.** Add the four-year alfalfa rotation, the remaining Iowa starter recipes, and the crop year and starting phase controls. Verify that winterkill, spring termination, and forage carryover appear at the right points in the timelines.
3. **Build and rehearse the screen.** Connect the scenario buttons to the timelines and show the dates, assumptions, and sources behind each result. Open on Custom years, switch to Wet Spring to show the rye fieldwork trade-off, then switch to Dry Summer to show which crops encounter a dry spell during a sensitive window. Swap in the alfalfa rotation to show the fourth year. Use the cached data for the live demo.

The team can split into weather and rules, local crop and soil research, dashboard design, and demo storytelling. The finish line is a two-minute demo someone can run from a cold start with no farmer setup or live data calls.

## 2026 forecast and future projections

The 2026 snapshot combines NASA POWER records through November 12 with the
ECMWF SEAS5 control member from Open-Meteo for November 13–December 31. The
snapshot was downloaded on November 15, 2026. Both sources use local dates at
UTC−06:00 for the farm. The seasonal forecast gives one plausible daily
sequence at about 36 km resolution. Individual days are uncertain.
[NASA POWER daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) · [Open-Meteo seasonal forecast](https://open-meteo.com/en/docs/seasonal-forecast-api)

Select **Future projections** under **Weather to compare** to replay 2027–2030
or 2028–2031. **Custom years** also uses the projections for dates from 2027 onward. Choose
ACCESS-CM2 or MPI-ESM1-2-LR under SSP2-4.5 or SSP3-7.0. Every plan uses the
same selected run. Changing models, pathways or weather modes preserves the
rotation plans. These are simulated climate sequences for stress testing.
Exact future dates are uncertain.

The app bundles NASA NEX-GDDP-CMIP6 v2.0 daily point subsets from the NASA
Center for Climate Simulation archive. The selected 0.25° grid cell is
42.125° N, 93.875° W. Each run uses member `r1i1p1f1` and includes 2026
for carryover context. The cache preserves UTC calendar dates and converts
precipitation flux to mm/day and mean air temperature to °C. The app works
offline. Run `python projection.py` to refresh the cache from NASA.
[NASA data and access documentation](https://www.nccs.nasa.gov/data-collections/nex-gddp-cmip6/)
