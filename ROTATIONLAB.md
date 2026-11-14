# RotationLab

## Summary

Compare up to three Iowa crop plans side by side. Start with a prefilled comparison, load a rotation studied in Iowa, or build a plan that matches the farm. Switch between **Typical**, **Wet Spring**, and **Dry Summer** to see how each plan fares under the same historical NASA weather. The demo shows where planned living cover lines up with heavy rain, where fieldwork windows get squeezed, and which crops encounter dry spells during sensitive growth stages.

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

Use complete, consecutive four-year weather blocks so the full alfalfa rotation fits and fall seeding, winter cover, and spring termination stay in order. Repeat shorter rotations across the same four years. Use the selected starting phase to determine the preceding crop at the start of the timeline, and show any carryover cover only where the plan and available weather support it. Pick a Typical block with a year near the historical median for both spring and summer rainfall. For Wet Spring, select the block by March–May rainfall in year two, when the default plan terminates rye ahead of soybean. For Dry Summer, select by June–August rainfall in year three, when the defaults compare corn with oats undersown with red clover. Apply the same weather block and rainfall rules to every plan. Display the years, rainfall totals, and selection rule.

| Scenario | What to show |
| --- | --- |
| Typical | Establish the baseline crop calendars, planned living cover, and fieldwork windows. |
| Wet Spring | Count heavy-rain days outside planned living cover. Show qualifying low-rain windows for planting and, where applicable, cover crop termination. Check their order and any interval required by the selected recipe. |
| Dry Summer | Highlight the longest low-rain stretch within each crop’s documented sensitive growth window. Show the dates and number of days so the farmer can see which crops were exposed and when. |

Show all three checks in every scenario and emphasize the ones relevant to the selected weather. Use the same documented rainfall thresholds across plans. Label the results **planned living cover**, **rainfall-based fieldwork windows**, and **dry-spell exposure**. Soil texture is context for interpreting the results. Actual field access, crop water stress, and erosion depend on field conditions and management.

## Build order for the weekend

1. **Get one comparison working.** Fetch and save NASA weather for the demo location. Build the three default plans from crop calendars and cover crop rules, and pick the historical blocks. Check the dates and counts for one wet and one dry example.
2. **Add the rotation builder.** Add the four-year alfalfa rotation, the remaining Iowa starter recipes, and the crop year and starting phase controls. Verify that winterkill, spring termination, and forage carryover appear at the right points in the timelines.
3. **Build and rehearse the screen.** Connect the scenario buttons to the timelines and show the dates, assumptions, and sources behind each result. Open on Typical, switch to Wet Spring to show the rye fieldwork trade-off, then switch to Dry Summer to show which crops encounter a dry spell during a sensitive window. Swap in the alfalfa rotation to show the fourth year. Use the cached data for the live demo.

The team can split into weather and rules, local crop and soil research, dashboard design, and demo storytelling. The finish line is a two-minute demo someone can run from a cold start with no farmer setup or live data calls.

## Stretch goal

If the historical demo is ready early, replay a few individual NASA POWER climate-model sequences for 2027–2030 through the same comparison. Show how often each plan’s windows are squeezed across the runs. The dated sequences are simulated weather for stress testing. For a later feature about the coming season, NASA GEOS seasonal forecasts are the relevant product, and their local rainfall skill would need checking. The core demo requires no custom ML. [NASA POWER climate projections](https://power.larc.nasa.gov/docs/services/api/projection/) · [NASA GEOS seasonal predictions](https://gmao.gsfc.nasa.gov/seasonal-decadal-analysis_prediction/)
