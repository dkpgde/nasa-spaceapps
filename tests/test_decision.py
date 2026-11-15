from decision import GOALS, rank_measures


def plan_year(plan, year, **metrics):
    return {"Plan": plan, "Year": year, **{measure.column: 0 for measure in GOALS.values()}, **metrics}


def test_rankings_change_with_the_period_and_keep_ties():
    rows = [
        plan_year(1, 2020, **{"Days with living cover": 120, "Longest dry spell (days)": 3}),
        plan_year(1, 2021, **{"Days with living cover": 240, "Longest dry spell (days)": 12}),
        plan_year(2, 2020, **{"Days with living cover": 140, "Longest dry spell (days)": 3}),
        plan_year(2, 2021, **{"Days with living cover": 200, "Longest dry spell (days)": 6}),
    ]
    whole_period = rank_measures(rows)
    assert whole_period["Keep soil covered"].leaders == (1,)
    assert whole_period["Avoid long dry spells"].leaders == (2,)
    assert whole_period["Avoid long dry spells"].values == {1: 12, 2: 6}
    first_year = rank_measures(rows, 2020)
    assert first_year["Keep soil covered"].leaders == (2,)
    assert first_year["Avoid long dry spells"].leaders == (1, 2)


def test_planting_omits_established_hay_and_excludes_missing_years():
    rows = [
        plan_year(1, 2020, **{"Days passing planting checks": 8}),
        plan_year(1, 2021, **{"Days passing planting checks": "N/A"}),
        plan_year(2, 2020, **{"Days passing planting checks": 5}),
        plan_year(2, 2021, **{"Days passing planting checks": 7}),
        plan_year(3, 2020, **{"Days passing planting checks": 9}),
        plan_year(3, 2021, **{"Days passing planting checks": "Unavailable"}),
    ]
    result = rank_measures(rows)["Get more planting opportunities"]
    assert result.values == {1: 8.0, 2: 6.0, 3: "Unavailable"}
    assert result.leaders == (1,)
    assert result.rated == 2
    result = rank_measures([row for row in rows if row["Plan"] != 2])["Get more planting opportunities"]
    assert result.leaders == ()
