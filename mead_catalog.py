"""Eastern Nebraska crop calendars and published Mead rotation examples."""

from dataclasses import replace

from catalog import CORN_STRESS, OAT_STRESS, SOY_STRESS, Crop
from rotation import Plan


STUDY = ("University of Nebraska and USDA-ARS Mead rotation study",
         "https://cropwatch.unl.edu/2021/more-diverse-crop-rotations-improve-yield-yield-stability-and-soil-health/")
SOIL_STUDY = ("Schmer et al. (2020) study site and soils", "https://doi.org/10.1002/agg2.20055")
NASS = ("USDA NASS usual Nebraska field crop dates (p. 42)",
        "https://esmis.nal.usda.gov/sites/default/release-files/vm40xr56k/dv13zw65p/w9505297d/planting-10-29-2010.pdf#page=42")
PEA_TRIAL = ("University of Nebraska Mead field pea trial", "https://projects.sare.org/project-reports/gnc18-271/")
MILLET = ("University of Nebraska proso millet production",
          "https://cropwatch.unl.edu/millet-and-field-pea-drought-resilient-options-nebraska-corn-soybean-systems/")
SILAGE = ("Nebraska Extension silage harvest timing",
          "https://cropwatch.unl.edu/pasture-and-forage-minute-considerations-corn-silage-harvest-and-following-cover-crops/")

corn = Crop("Grain corn", ((4, 27), (5, 15)), ((10, 4), (11, 10)), (9, 20),
            ((7, 10), (8, 5)), "Around silking", (NASS, STUDY, CORN_STRESS))
CROPS = {
    "corn": corn,
    "silage": replace(corn, name="Corn silage", harvest=((8, 26), (9, 19)),
                      living_end=(9, 7), sources=(*corn.sources, SILAGE)),
    "soy": Crop("Soybean", ((5, 11), (5, 31)), ((9, 29), (10, 24)), (9, 26),
                ((8, 1), (8, 31)), "Pod development to full seed", (NASS, STUDY, SOY_STRESS)),
    "sorghum": Crop("Grain sorghum", ((5, 16), (6, 9)), ((10, 8), (11, 8)), (9, 24),
                    ((8, 1), (9, 10)), "Boot to dough stage", (NASS, STUDY, OAT_STRESS)),
    "oats": Crop("Spring oats (grain)", ((4, 1), (4, 24)), ((7, 10), (7, 30)), (7, 6),
                 ((6, 1), (6, 25)), "Stem elongation to flowering", (NASS, STUDY, OAT_STRESS)),
    "winter_wheat": Crop("Winter wheat", ((9, 9), (10, 2)), ((7, 3), (7, 21)), (6, 27),
                         ((5, 15), (6, 10)), "Heading through early grain fill", (NASS, OAT_STRESS), fall_planted=True),
    "field_pea": Crop("Dry field pea", ((3, 12), (3, 26)), ((7, 1), (7, 15)), (6, 28),
                      None, "", (PEA_TRIAL,)),
    "millet": Crop("Proso millet", ((5, 15), (6, 20)), ((8, 10), (9, 10)), (8, 19),
                   None, "", (MILLET, PEA_TRIAL)),
    "sunflower": Crop("Sunflower (grain)", ((6, 5), (6, 30)), ((10, 5), (10, 25)), (9, 22),
                      None, "", (NASS, PEA_TRIAL)),
    "dry_bean": Crop("Dry edible bean", ((5, 27), (6, 16)), ((9, 13), (10, 9)), (9, 10),
                     ((7, 15), (8, 15)), "Flowering and pod set", (NASS, OAT_STRESS)),
    "sugarbeet": Crop("Sugarbeet", ((4, 10), (4, 30)), ((10, 10), (10, 30)), (10, 19),
                      None, "", (NASS,)),
}
EXAMPLES = {
    "Mead · Corn → soybean": Plan(("corn", "soy"), (False, False)),
    "Mead · Sorghum → soybean": Plan(("sorghum", "soy"), (False, False)),
    "Mead · Continuous corn": Plan(("corn",), (False,)),
}
