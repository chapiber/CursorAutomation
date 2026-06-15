"""Tests standings CDM."""

from app.cdm.standings import compute_standings


def _row(table, team):
    return next(r for r in table if r["team"] == team)


def test_standings_points_and_sort():
    matches = [
        {
            "stage": "group",
            "group": "A",
            "home": "MEX",
            "away": "RSA",
            "score": {"home": 2, "away": 0, "status": "finished"},
        },
        {
            "stage": "group",
            "group": "A",
            "home": "KOR",
            "away": "CZE",
            "score": {"home": 1, "away": 1, "status": "finished"},
        },
    ]
    groups_meta = [
        {
            "id": "A",
            "teams": ["MEX", "KOR", "RSA", "CZE"],
            "standings": [],
        }
    ]
    result = compute_standings(matches, groups_meta)
    assert len(result) == 1
    table = result[0]["standings"]

    mex = _row(table, "MEX")
    assert mex["pts"] == 3
    assert mex["won"] == 1
    assert mex["gf"] == 2

    kor = _row(table, "KOR")
    assert kor["pts"] == 1
    assert kor["drawn"] == 1

    assert table[0]["team"] == "MEX"


def test_standings_ignores_unfinished():
    matches = [
        {
            "stage": "group",
            "group": "A",
            "home": "MEX",
            "away": "RSA",
            "score": {"home": None, "away": None, "status": "scheduled"},
        },
    ]
    groups_meta = [{"id": "A", "teams": ["MEX", "KOR", "RSA", "CZE"], "standings": []}]
    result = compute_standings(matches, groups_meta)
    for row in result[0]["standings"]:
        assert row["played"] == 0
        assert row["pts"] == 0
