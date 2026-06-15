"""Compte-rendu texte minimaliste pour n8n."""

from __future__ import annotations

from typing import Any


def _format_tokens(tokens: dict[str, Any] | None) -> str:
    if not tokens:
        return "n/d"
    total = tokens.get("total")
    if total is None:
        return "n/d"
    if tokens.get("estimated"):
        return f"{total} (estimé)"
    inp = tokens.get("input", 0)
    out = tokens.get("output", 0)
    return f"{total} (in {inp} / out {out})"


def _job_title(job_id: str) -> str:
    if job_id == "cdm2026-daily":
        return "CDM 2026 — compte-rendu"
    return f"{job_id} — compte-rendu"


def _is_cdm_programmatic(result: dict[str, Any]) -> bool:
    return result.get("handler") == "cdm_update" or bool(result.get("cdm"))


def _extract_stats(result: dict[str, Any]) -> dict[str, Any]:
    cdm = result.get("cdm") or {}
    if cdm.get("stats"):
        return cdm["stats"]
    agent = result.get("agent") or {}
    return agent.get("stats") or {}


def _duration_line(result: dict[str, Any]) -> str | None:
    if _is_cdm_programmatic(result):
        cdm = result.get("cdm") or {}
        dur = cdm.get("duration_sec")
        if dur is not None:
            return f"Durée MAJ : {dur} s"
        return None
    agent = result.get("agent") or {}
    dur = agent.get("duration_sec")
    if dur is not None:
        return f"Durée agent : {dur} s"
    return None


def build_report_text(record: dict[str, Any]) -> str:
    """CR texte à partir d'un record run_store."""
    status = record.get("status", "running")
    job_id = record.get("job_id", "")
    title = _job_title(job_id)
    result = record.get("result") or {}
    message = record.get("message", "")

    if status == "running":
        phase = record.get("phase", "?")
        elapsed = record.get("elapsed_sec")
        if elapsed is None and "started_at" in record:
            elapsed = 0
        tail = f" ({int(elapsed)} s)" if elapsed else ""
        return f"{title}\nStatut : en cours — {phase}{tail}"

    if status == "error":
        error = result.get("error") or message or "erreur inconnue"
        lines = [title, f"Statut : erreur — {error}"]
        dur_line = _duration_line(result)
        if dur_line:
            lines.append(dur_line)
        stats = _extract_stats(result)
        if stats.get("matches_updated") is not None:
            lines.append(f"Matchs mis à jour : {stats['matches_updated']}")
        if not _is_cdm_programmatic(result):
            tokens_line = _format_tokens(stats.get("tokens"))
            if tokens_line != "n/d":
                lines.append(f"Tokens : {tokens_line}")
        return "\n".join(lines)

    git_pull = result.get("git_pull") or {}
    git_push = result.get("git_push") or {}
    stats = _extract_stats(result)

    lines = [title]
    dur_line = _duration_line(result)
    if dur_line:
        lines.append(dur_line)

    matches = stats.get("matches_updated")
    lines.append(f"Matchs mis à jour : {matches if matches is not None else 'n/d'}")

    if not _is_cdm_programmatic(result):
        lines.append(f"Tokens : {_format_tokens(stats.get('tokens'))}")

    files = git_push.get("files_committed")
    if files is None:
        files = git_pull.get("files_committed")
    if files is None:
        files = 0
    lines.append(f"Fichiers commités : {files}")

    commit = result.get("commit")
    if commit:
        lines.append(f"Commit : {commit}")

    total_dur = result.get("duration_sec")
    cdm_dur = (result.get("cdm") or {}).get("duration_sec")
    agent_dur = (result.get("agent") or {}).get("duration_sec")
    ref_dur = cdm_dur if cdm_dur is not None else agent_dur
    if total_dur is not None and ref_dur is not None and total_dur != ref_dur:
        lines.append(f"Durée totale (pull + deploy) : {total_dur} s")

    return "\n".join(lines)
