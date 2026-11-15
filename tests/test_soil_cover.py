from dataclasses import replace
from datetime import date

import pandas as pd

from rainfall import analyze
from rotation import Calendar, CropYear, Dates, Event


def test_annual_living_cover_counts_overlap_once_and_screens_heavy_rain():
    span = Dates(date(2020, 1, 1), date(2020, 12, 31))
    events = (
        Event("Forage", "Living cover", Dates(date(2020, 1, 1), date(2020, 1, 10))),
        Event("Cover crop", "Living cover", Dates(date(2020, 1, 5), date(2020, 1, 12))),
    )
    crop_year = CropYear(2020, "Forage", events, None, None, None, None, ())
    calendar = Calendar(span, "Forage", (crop_year,), ())
    daily = pd.DataFrame({"precipitation_mm": 0.0}, index=pd.date_range(span.start, span.end))
    daily.loc[["2020-01-10", "2020-01-13"], "precipitation_mm"] = 25

    result = analyze(calendar, daily)[2020]
    assert result.living_cover_days == 12
    assert result.longest_cover_gap == 354
    assert result.uncovered == ((date(2020, 1, 13), 25.0),)

    missing_rain = analyze(calendar, daily.drop("2020-01-13"))[2020]
    assert missing_rain.living_cover_days == 12
    assert missing_rain.uncovered is None

    unknown_cover = replace(calendar, years=(replace(crop_year, cover_unknown=True),))
    unavailable = analyze(unknown_cover, daily)[2020]
    assert unavailable.living_cover_days is None
    assert unavailable.longest_cover_gap is None
