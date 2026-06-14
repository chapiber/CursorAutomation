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
        agent = result.get("agent") or {}
        agent_dur = agent.get("duration_sec")
        lines = [title, f"Statut : erreur — {error}"]
        if agent_dur is not None:
            lines.append(f"Durée agent : {agent_dur} s")
        stats = agent.get("stats") or {}
        if stats.get("matches_updated") is not None:
            lines.append(f"Matchs mis à jour : {stats['matches_updated']}")
        tokens_line = _format_tokens(stats.get("tokens"))
        if tokens_line != "n/d":
            lines.append(f"Tokens : {tokens_line}")
        return "\n".join(lines)

    agent = result.get("agent") or {}
    git_pull = result.get("git_pull") or {}
    stats = agent.get("stats") or {}

    lines = [title]
    agent_dur = agent.get("duration_sec")
    if agent_dur is not None:
        lines.append(f"Durée agent : {agent_dur} s")

    matches = stats.get("matches_updated")
    lines.append(f"Matchs mis à jour : {matches if matches is not None else 'n/d'}")
    lines.append(f"Tokens : {_format_tokens(stats.get('tokens'))}")

    files = git_pull.get("files_committed")
    if files is None:
        files = 0
    lines.append(f"Fichiers commités : {files}")

    commit = result.get("commit")
    if commit:
        lines.append(f"Commit : {commit}")

    total_dur = result.get("duration_sec")
    if total_dur is not None and total_dur != agent_dur:
        lines.append(f"Durée totale (pull + deploy) : {total_dur} s")

    return "\n".join(lines)
