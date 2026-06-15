"""Fusion des résultats externes dans cdm2026.json."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models import ExternalMatch, UpdateStats


def _score_tuple(ext: ExternalMatch) -> tuple[int | None, int | None, str]:
    return (ext.home_score, ext.away_score, ext.status)


def _existing_score(match: dict[str, Any]) -> dict[str, Any]:
    return match.get("score") or {"home": None, "away": None, "status": "scheduled"}


def _scores_conflict(a: dict[str, Any], b: ExternalMatch) -> bool:
    if a.get("status") == "finished" and a.get("home") is not None and a.get("away") is not None:
        if b.home_score is None or b.away_score is None:
            return False
        return int(a["home"]) != b.home_score or int(a["away"]) != b.away_score
    return False


def _pick_consensus(candidates: list[ExternalMatch]) -> ExternalMatch | None:
    if not candidates:
        return None
    buckets: dict[tuple[int | None, int | None, str], list[ExternalMatch]] = defaultdict(list)
    for c in candidates:
        if c.home_score is None or c.away_score is None:
            continue
        buckets[_score_tuple(c)].append(c)

    if not buckets:
        live = [c for c in candidates if c.status == "live" and c.home_score is not None]
        return live[0] if live else None

    best_key = max(buckets.keys(), key=lambda k: len(buckets[k]))
    if len(buckets[best_key]) >= 2:
        return buckets[best_key][0]

    # Une seule source : accepter si score final
    only = next(iter(buckets.values()))
    ext = only[0]
    if ext.status == "finished":
        return ext
    return None


def _apply_external(match: dict[str, Any], ext: ExternalMatch) -> bool:
    score = _existing_score(match)
    new_score = dict(score)
    changed = False

    if ext.home_score is not None and ext.away_score is not None:
        new_score["home"] = ext.home_score
        new_score["away"] = ext.away_score
        new_score["status"] = ext.status if ext.status in ("live", "finished") else "finished"
        if ext.status == "live":
            new_score["status"] = "live"
        elif ext.status != "live":
            new_score["status"] = "finished"
    elif ext.status == "live":
        new_score["status"] = "live"

    if new_score != score:
        match["score"] = new_score
        changed = True
    return changed


def merge_matches(data: dict[str, Any], externals: list[ExternalMatch]) -> UpdateStats:
    """Applique les résultats externes ; ne jamais inventer de score."""
    stats = UpdateStats()
    by_pair: dict[tuple[str, str], list[ExternalMatch]] = defaultdict(list)
    for ext in externals:
        by_pair[(ext.home, ext.away)].append(ext)

    for match in data.get("matches", []):
        home = match.get("home")
        away = match.get("away")
        if not home or not away:
            continue

        candidates = by_pair.get((home, away), [])
        if not candidates:
            continue

        existing = _existing_score(match)
        consensus = _pick_consensus(candidates)
        if consensus is None:
            continue

        if _scores_conflict(existing, consensus):
            stats.conflicts.append(
                f"{match.get('id', '?')} {home}-{away}: "
                f"existant {existing.get('home')}-{existing.get('away')} vs "
                f"{consensus.home_score}-{consensus.away_score} ({consensus.source})"
            )
            continue

        if _apply_external(match, consensus):
            stats.matches_updated += 1

    return stats
