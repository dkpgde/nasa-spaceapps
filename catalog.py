"""Iowa calendar inputs and starter recipes for the historical demo."""

from dataclasses import dataclass, replace


MonthDay = tuple[int, int]
Season = tuple[MonthDay, MonthDay]

MARSDEN = (
    "Marsden Farm rotation study",
    "https://inrc.cals.iastate.edu/project-location/marsden-long-term-rotation-study",
)
MANAGEMENT = (
    "Marsden Farm management (Davis et al., Text S1)",
    "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0047149",
)
SOIL = (
    "Marsden Farm soil study (Lazicki et al.)",
    "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0164209",
)
NASS = (
    "USDA NASS Iowa planting and harvest dates (p. 39)",
    "https://www.nass.usda.gov/Publications/Todays_Reports/reports/fcdate10.pdf#page=39",
)
PLANTING = (
    "Iowa State corn and soybean planting dates",
    "https://crops.extension.iastate.edu/post/corn-and-soybean-planting-date-considerations",
)
CORN_STRESS = (
    "Iowa State corn drought stages",
    "https://crops.extension.iastate.edu/post/drought-effect-corn-and-soybean-and-alternative-management-considerations",
)
SOY_STRESS = (
    "Iowa State soybean drought stages",
    "https://crops.extension.iastate.edu/cropnews/2012/07/soybean-potential-drought-conditions",
)
STAGE_DATES = (
    "Cornell crop water use and seasonal timing",
    "https://nrcca.cals.cornell.edu/crop/CA1/CA0103.php",
)
OAT_STRESS = (
    "Colorado State small-grain water use by growth stage",
    "https://extension.colostate.edu/resource/crop-water-use-and-growth-stages/",
)
OAT_STAGE_DATES = (
    "USDA NASS Iowa oat heading dates (p. 4)",
    "https://publications.iowa.gov/42141/1/IA-Annual-Crop-Progress-2022.pdf#page=4",
)
FORAGES = (
    "Practical Farmers of Iowa oats and forage trial",
    "https://practicalfarmers.org/resources/research-reports/establishing-legume-forages-with-oats/",
)
CLOVER = (
    "Iowa State intercropped red clover management",
    "https://midwestcovercrops.org/wp-content/uploads/2018/12/IA_2006_Intercropping-Winter-Cereal-Grains-and-Red-Clover.pdf",
)
RYE_SPRING = (
    "Iowa State spring cover termination",
    "https://crops.extension.iastate.edu/post/start-planning-2026-cover-crop-termination",
)


@dataclass(frozen=True)
class Crop:
    name: str
    planting: Season | None
    harvest: Season
    living_end: MonthDay
    sensitive: Season | None
    stage: str
    sources: tuple[tuple[str, str], ...]
    undersown: str | None = None


corn = Crop(
    "Grain corn", ((4, 11), (5, 18)), ((10, 5), (11, 9)), (9, 20),
    ((7, 10), (8, 5)), "Around silking", (PLANTING, NASS, CORN_STRESS, STAGE_DATES),
)
oats = Crop(
    "Spring oats (grain)", ((4, 2), (5, 2)), ((7, 17), (8, 5)), (7, 16),
    ((6, 1), (6, 30)), "Stem elongation to flowering",
    (NASS, OAT_STRESS, OAT_STAGE_DATES, FORAGES),
)
CROPS = {
    "corn": corn,
    "silage": replace(
        corn, name="Corn silage", harvest=((8, 25), (9, 20)), living_end=(9, 7),
    ),
    "soy": Crop(
        "Soybean", ((4, 12), (5, 20)), ((9, 28), (10, 20)), (9, 27),
        ((8, 1), (8, 31)), "Pod development to full seed",
        (PLANTING, NASS, SOY_STRESS, STAGE_DATES),
    ),
    "oats": oats,
    "clover": replace(
        oats, name="Oats with red clover", undersown="Red clover",
        sources=(*oats.sources, MARSDEN, MANAGEMENT, CLOVER),
    ),
    "oat_alfalfa": replace(
        oats, name="Oats with alfalfa", undersown="Alfalfa establishment",
        sources=(*oats.sources, MARSDEN, MANAGEMENT),
    ),
    "hay": Crop(
        "Established alfalfa hay", None, ((5, 30), (9, 15)), (12, 31), None, "",
        (NASS, MARSDEN, MANAGEMENT),
    ),
}


@dataclass(frozen=True)
class Recipe:
    name: str
    source: tuple[str, str]
    seed_by: MonthDay
    minimum_gap: int | None = None
    overseeding_from: MonthDay | None = None
    winterkill: MonthDay | None = None


MCCC = "https://www.midwestcovercrops.org/"
RECIPES = {
    ("corn", "soy"): Recipe(
        "Cereal rye", ("MCCC 103 · Grain corn to soybean",
                       MCCC + "2019/01/28/iowa-cover-crop-recipe-post-corn-going-soybean-use-cereal-rye/"),
        (10, 27), minimum_gap=11,
    ),
    ("silage", "soy"): Recipe(
        "Cereal rye", ("MCCC 122 · Corn silage to soybean",
                       MCCC + "wp-content/uploads/2020/03/MCCC-122-IA-post-silage-to-bean-ada.pdf"),
        (10, 28), minimum_gap=10,
    ),
    ("silage", "corn"): Recipe(
        "Cereal rye", ("MCCC 121 · Corn silage to grain corn",
                       MCCC + "2020/03/06/iowa-cover-crop-recipe-post-corn-silage-going-corn-use-cereal-rye/"),
        (10, 28), minimum_gap=10,
    ),
    ("soy", "corn"): Recipe(
        "Fall oats (winterkill)", ("MCCC 104 · Soybean to grain corn",
                                  MCCC + "2019/01/28/iowa-cover-crop-recipe-post-soybean-going-corn-use-oats/"),
        (9, 15), overseeding_from=(8, 22), winterkill=(11, 30),
    ),
}
