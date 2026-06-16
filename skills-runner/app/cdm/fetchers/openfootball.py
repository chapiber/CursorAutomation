"""Source openfootball/worldcup.json — JSON public mis à jour régulièrement."""

from __future__ import annotations

import json
from typing import Any, Callable

from ..models import ExternalMatch

URL_MATCHES = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
)
URL_TEAMS = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.teams.json"
)
SOURCE = "openfootball/worldcup.json"

# Écarts FIFA entre openfootball et cdm2026.json
_FIFA_ALIASES: dict[str, str] = {
    "HAI": "HTI",
}


def _to_cdm_code(fifa_code: str) -> str | None:
    from .base import TEAM_CODES

    code = _FIFA_ALIASES.get(fifa_code, fifa_code)
    return code if code in TEAM_CODES else None


def _build_name_index(teams: list[dict[str, Any]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for team in teams:
        fifa = team.get("fifa_code")
        if not fifa:
            continue
        code = _to_cdm_code(str(fifa))
        if not code:
            continue
        for key in ("name", "name_normalised"):
            raw = team.get(key)
            if raw:
                index[str(raw).strip().lower()] = code
        index[str(fifa).strip().lower()] = code
    return index


def _resolve_team(name: str, index: dict[str, str]) -> str | None:
    if not name:
        return None
    code = index.get(name.strip().lower())
    if code:
        return code
    from .base import normalize_team_code

    return normalize_team_code(name)


def parse_openfootball_payload(
    matches_data: dict[str, Any],
    teams_data: list[dict[str, Any]],
    *,
    source: str = SOURCE,
) -> list[ExternalMatch]:
    """Convertit le JSON openfootball en ExternalMatch."""
    index = _build_name_index(teams_data)
    results: list[ExternalMatch] = []

    for item in matches_data.get("matches", []):
        home = _resolve_team(str(item.get("team1", "")), index)
        away = _resolve_team(str(item.get("team2", "")), index)
        if not home or not away or home == away:
            continue

        score = item.get("score") or {}
        ft = score.get("ft")
        if not isinstance(ft, list) or len(ft) != 2:
            continue

        try:
            home_score = int(ft[0])
            away_score = int(ft[1])
        except (TypeError, ValueError):
            continue

        results.append(
            ExternalMatch(
                home=home,
                away=away,
                home_score=home_score,
                away_score=away_score,
                status="finished",
                source=source,
            )
        )

    return results


def fetch(http_get: Callable[[str], str]) -> tuple[list[ExternalMatch], str]:
    matches_raw = json.loads(http_get(URL_MATCHES))
    teams_raw = json.loads(http_get(URL_TEAMS))
    return parse_openfootball_payload(matches_raw, teams_raw), SOURCE
