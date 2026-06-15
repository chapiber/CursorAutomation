"""Tests fetchers CDM (snapshots locaux)."""

from pathlib import Path

from app.cdm.fetchers import parse_html_snapshot
from app.cdm.fetchers.base import normalize_team_code, parse_name_ft_lines, parse_score_lines

FIXTURES = Path(__file__).parent / "fixtures"


def test_normalize_team_code():
    assert normalize_team_code("FRA") == "FRA"
    assert normalize_team_code("france") == "FRA"
    assert normalize_team_code("Écosse") == "SCO"


def test_parse_score_lines_from_snapshot():
    html = (FIXTURES / "matchcalendar_sample.html").read_text(encoding="utf-8")
    matches = parse_html_snapshot(html, "matchcalendar.football")
    pairs = {(m.home, m.away, m.home_score, m.away_score) for m in matches}
    assert ("MEX", "RSA", 2, 0) in pairs
    assert ("HTI", "SCO", 0, 2) in pairs


def test_parse_name_ft_lines_matchcalendar():
    text = (
        "Match 14 \u00b7 Group H \u00b7 Spain vs Cape Verde \u00b7 FT 0-0 \u00b7 Mon, Jun 15, 2026\n"
        "Match 3 \u00b7 Group B \u00b7 Canada vs Bosnia and Herzegovina \u00b7 FT 1-1 \u00b7 Fri, Jun 12, 2026"
    )
    matches = parse_name_ft_lines(text, "matchcalendar.football")
    pairs = {(m.home, m.away, m.home_score, m.away_score, m.status) for m in matches}
    assert ("ESP", "CPV", 0, 0, "finished") in pairs
    assert ("CAN", "BIH", 1, 1, "finished") in pairs


def test_parse_score_lines_live_marker():
    text = "CAN 1 - 0 BIH en direct maintenant"
    matches = parse_score_lines(text, "test")
    assert len(matches) == 1
    assert matches[0].status == "live"
