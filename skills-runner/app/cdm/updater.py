"""Orchestration MAJ CDM 2026."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .fetchers import fetch_all
from .merge import merge_matches
from .models import UpdateStats
from .standings import compute_standings

logger = logging.getLogger("skills-runner.cdm")

ProgressFn = Callable[[str], None]


def run_cdm_update(
    data_path: Path,
    *,
    progress: ProgressFn | None = None,
) -> tuple[dict[str, Any], UpdateStats, bool]:
    """
    Lit le JSON, fetch web, merge, standings, écrit si diff.
    Retourne (data, stats, written).
    """
    def _log(msg: str) -> None:
        if progress:
            progress(msg)
        logger.info("CDM: %s", msg)

    if not data_path.is_file():
        raise FileNotFoundError(f"Fichier CDM introuvable : {data_path}")

    _log("lecture JSON existant")
    original_text = data_path.read_text(encoding="utf-8")
    data: dict[str, Any] = json.loads(original_text)

    _log("fetch sources web")
    externals, fetch_errors, sources = fetch_all()

    stats = merge_matches(data, externals)
    stats.fetch_errors = fetch_errors
    stats.sources = sources

    _log(f"merge terminé — {stats.matches_updated} match(s) modifié(s)")
    if stats.conflicts:
        _log(f"{len(stats.conflicts)} conflit(s) ignoré(s)")

    _log("recalcul standings")
    data["groups"] = compute_standings(data.get("matches", []), data.get("groups"))

    meta = data.setdefault("meta", {})
    meta["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    meta["updatedBy"] = "cloud"
    if sources:
        meta["sources"] = sorted(set(meta.get("sources", []) + sources))

    new_text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    written = new_text != original_text
    if written:
        data_path.write_text(new_text, encoding="utf-8")
        _log("JSON écrit")
    else:
        _log("aucun changement JSON")

    return data, stats, written
