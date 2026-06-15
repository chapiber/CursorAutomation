"""Recalcul des classements de poules — port de generate_cdm2026_seed.js."""

from __future__ import annotations

from typing import Any


def compute_standings(
    matches: list[dict[str, Any]],
    groups_meta: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Recalcule groups[].standings à partir des matchs de poule terminés."""
    team_lists: dict[str, list[str]] = {}
    if groups_meta:
        for group in groups_meta:
            gid = group.get("id")
            teams = group.get("teams") or []
            if gid and teams:
                team_lists[gid] = list(teams)

    if not team_lists:
        for match in matches:
            if match.get("stage") != "group" or not match.get("group"):
                continue
            gid = match["group"]
            if gid not in team_lists:
                team_lists[gid] = []
            for code in (match.get("home"), match.get("away")):
                if code and code not in team_lists[gid]:
                    team_lists[gid].append(code)

    standings_map: dict[str, list[dict[str, Any]]] = {}
    for gid, teams in team_lists.items():
        standings_map[gid] = [
            {
                "team": code,
                "played": 0,
                "won": 0,
                "drawn": 0,
                "lost": 0,
                "gf": 0,
                "ga": 0,
                "pts": 0,
            }
            for code in teams
        ]

    by_group: dict[str, list[dict[str, Any]]] = {}
    for match in matches:
        if match.get("stage") != "group" or not match.get("group"):
            continue
        score = match.get("score") or {}
        if score.get("status") != "finished":
            continue
        if score.get("home") is None or score.get("away") is None:
            continue
        gid = match["group"]
        by_group.setdefault(gid, []).append(match)

    for gid, table in standings_map.items():
        idx = {row["team"]: row for row in table}
        for match in by_group.get(gid, []):
            home = match.get("home")
            away = match.get("away")
            if home not in idx or away not in idx:
                continue
            h = idx[home]
            a = idx[away]
            hs = int(match["score"]["home"])
            aws = int(match["score"]["away"])
            h["played"] += 1
            a["played"] += 1
            h["gf"] += hs
            h["ga"] += aws
            a["gf"] += aws
            a["ga"] += hs
            if hs > aws:
                h["won"] += 1
                h["pts"] += 3
                a["lost"] += 1
            elif hs < aws:
                a["won"] += 1
                a["pts"] += 3
                h["lost"] += 1
            else:
                h["drawn"] += 1
                a["drawn"] += 1
                h["pts"] += 1
                a["pts"] += 1

        table.sort(key=lambda r: (-r["pts"], -(r["gf"] - r["ga"]), -r["gf"]))

    return [
        {"id": gid, "teams": team_lists[gid], "standings": standings_map[gid]}
        for gid in sorted(team_lists.keys())
    ]
