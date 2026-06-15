"""Tests merge CDM."""

import json
from pathlib import Path

from app.cdm.merge import merge_matches
from app.cdm.models import ExternalMatch

FIXTURES = Path(__file__).parent / "fixtures"


def _load_sample():
    return json.loads((FIXTURES / "cdm_sample.json").read_text(encoding="utf-8"))


def test_merge_updates_scheduled_match_with_consensus():
    data = _load_sample()
    externals = [
        ExternalMatch("HTI", "SCO", 0, 2, "finished", "matchcalendar.football"),
        ExternalMatch("HTI", "SCO", 0, 2, "finished", "franceinfo"),
    ]
    stats = merge_matches(data, externals)
    assert stats.matches_updated == 1
    match = next(m for m in data["matches"] if m["id"] == "M005")
    assert match["score"]["home"] == 0
    assert match["score"]["away"] == 2
    assert match["score"]["status"] == "finished"


def test_merge_keeps_existing_on_conflict():
    data = _load_sample()
    externals = [
        ExternalMatch("MEX", "RSA", 3, 0, "finished", "matchcalendar.football"),
        ExternalMatch("MEX", "RSA", 3, 0, "finished", "franceinfo"),
    ]
    stats = merge_matches(data, externals)
    assert stats.matches_updated == 0
    assert len(stats.conflicts) == 1
    match = next(m for m in data["matches"] if m["id"] == "M001")
    assert match["score"]["home"] == 2


def test_merge_detects_live():
    data = _load_sample()
    data["matches"].append(
        {
            "id": "M099",
            "stage": "group",
            "group": "B",
            "home": "CAN",
            "away": "BIH",
            "score": {"home": None, "away": None, "status": "scheduled"},
        }
    )
    externals = [
        ExternalMatch("CAN", "BIH", 1, 0, "live", "matchcalendar.football"),
        ExternalMatch("CAN", "BIH", 1, 0, "live", "franceinfo"),
    ]
    stats = merge_matches(data, externals)
    assert stats.matches_updated == 1
    match = next(m for m in data["matches"] if m["id"] == "M099")
    assert match["score"]["status"] == "live"
    assert match["score"]["home"] == 1
