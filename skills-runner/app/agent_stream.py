"""Agent cloud avec streaming des messages vers run_store."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

from cursor_sdk import Agent, CloudAgentOptions, CloudRepository, CursorAgentError, SendOptions

from .jobs import JobConfig, load_prompt
from .run_store import update_run

logger = logging.getLogger("skills-runner")

PROGRESS_RE = re.compile(r"\[CDM_PROGRESS\]\s*(.+)", re.IGNORECASE)
STATS_RE = re.compile(r"\[CDM_STATS\]\s*(\{.*\})", re.IGNORECASE)
AGENT_SUCCESS_STATUSES = frozenset({"finished", "completed", "success"})


def is_agent_success(status: str | None) -> bool:
    if not status:
        return False
    return status.lower() in AGENT_SUCCESS_STATUSES


def _extract_message_text(message: Any) -> str:
    """Extrait le texte d'un message SDK (assistant / tool)."""
    parts: list[str] = []
    msg_type = getattr(message, "type", None)
    if msg_type == "assistant":
        inner = getattr(message, "message", None)
        content = getattr(inner, "content", None) if inner else None
        if content:
            for block in content:
                if getattr(block, "type", None) == "text":
                    text = getattr(block, "text", "")
                    if text:
                        parts.append(text)
    elif msg_type == "tool_call":
        name = getattr(message, "name", None) or getattr(message, "tool_name", "tool")
        parts.append(f"[tool] {name}")
    elif msg_type == "tool_result":
        parts.append("[tool_result]")
    else:
        text = getattr(message, "text", None) or getattr(message, "content", None)
        if isinstance(text, str) and text.strip():
            parts.append(text.strip()[:500])
    return "\n".join(parts).strip()


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class _RunMetrics:
    """Métriques collectées pendant le stream agent."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read_tokens = 0
        self.cache_write_tokens = 0
        self.token_delta_sum = 0
        self.matches_updated: int | None = None

    def on_delta(self, update: Any) -> None:
        update_type = _get_attr(update, "type")
        if update_type == "turn-ended":
            usage = _get_attr(update, "usage")
            if usage:
                self.input_tokens += int(_get_attr(usage, "input_tokens", 0) or _get_attr(usage, "inputTokens", 0) or 0)
                self.output_tokens += int(_get_attr(usage, "output_tokens", 0) or _get_attr(usage, "outputTokens", 0) or 0)
                self.cache_read_tokens += int(
                    _get_attr(usage, "cache_read_tokens", 0) or _get_attr(usage, "cacheReadTokens", 0) or 0
                )
                self.cache_write_tokens += int(
                    _get_attr(usage, "cache_write_tokens", 0) or _get_attr(usage, "cacheWriteTokens", 0) or 0
                )
        elif update_type == "token-delta":
            self.token_delta_sum += int(_get_attr(update, "tokens", 0) or 0)

    def apply_stats_line(self, line: str) -> None:
        match = STATS_RE.search(line)
        if not match:
            return
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.warning("CDM_STATS JSON invalide : %s", match.group(1)[:120])
            return
        if "matches_updated" in data:
            self.matches_updated = int(data["matches_updated"])

    def to_dict(self) -> dict[str, Any]:
        stats: dict[str, Any] = {}
        if self.matches_updated is not None:
            stats["matches_updated"] = self.matches_updated
        tokens = self._tokens_dict()
        if tokens:
            stats["tokens"] = tokens
        return stats

    def _tokens_dict(self) -> dict[str, Any] | None:
        if self.input_tokens or self.output_tokens:
            total = self.input_tokens + self.output_tokens
            return {
                "input": self.input_tokens,
                "output": self.output_tokens,
                "cache_read": self.cache_read_tokens,
                "cache_write": self.cache_write_tokens,
                "total": total,
            }
        if self.token_delta_sum:
            return {"total": self.token_delta_sum, "estimated": True}
        return None


def _handle_text_chunk(run_id: str, text: str, metrics: _RunMetrics) -> None:
    if not text:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        update_run(run_id, log_line=line)
        progress = PROGRESS_RE.search(line)
        if progress:
            update_run(run_id, message=progress.group(1).strip(), phase="agent_running")
        metrics.apply_stats_line(line)


def run_cloud_agent_streaming(job: JobConfig, run_id: str) -> dict[str, Any]:
    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not api_key:
        return {
            "agent_status": "startup_error",
            "agent_error": "CURSOR_API_KEY manquant",
            "duration_sec": 0,
        }

    prompt = load_prompt(job)
    repo_url = f"https://github.com/{job.repo}"
    metrics = _RunMetrics()
    update_run(run_id, phase="agent_starting", message="Démarrage agent cloud")
    logger.info("Démarrage agent cloud stream job=%s run_id=%s", job.job_id, run_id)
    started = time.time()

    try:
        with Agent.create(
            model="composer-2.5",
            api_key=api_key,
            cloud=CloudAgentOptions(
                repos=[CloudRepository(url=repo_url, starting_ref=job.branch)],
                skip_reviewer_request=True,
            ),
        ) as agent:
            agent_id = getattr(agent, "id", None) or getattr(agent, "agent_id", None)
            if agent_id:
                update_run(run_id, agent_id=str(agent_id))

            update_run(run_id, phase="agent_running", message="Agent en cours d'exécution")
            run = agent.send(prompt, SendOptions(on_delta=metrics.on_delta))

            if hasattr(run, "messages"):
                for message in run.messages():
                    chunk = _extract_message_text(message)
                    _handle_text_chunk(run_id, chunk, metrics)

            result = run.wait()
    except CursorAgentError as err:
        logger.error("Échec agent stream : %s (retryable=%s)", err.message, err.is_retryable)
        update_run(run_id, log_line=f"[error] {err.message}")
        return {
            "agent_status": "startup_error",
            "agent_error": err.message,
            "duration_sec": round(time.time() - started, 1),
            "stats": metrics.to_dict(),
        }
    except Exception as err:
        logger.exception("Exception agent stream run_id=%s", run_id)
        update_run(run_id, log_line=f"[error] {err}")
        return {
            "agent_status": "startup_error",
            "agent_error": str(err),
            "duration_sec": round(time.time() - started, 1),
            "stats": metrics.to_dict(),
        }

    duration = round(time.time() - started, 1)
    status = getattr(result, "status", "error")
    stats = metrics.to_dict()

    if status == "error":
        logger.error("Run agent en erreur run_id=%s", getattr(result, "id", "?"))
        summary = (getattr(result, "result", None) or "")[:2000]
        _handle_text_chunk(run_id, summary, metrics)
        stats = metrics.to_dict()
        update_run(run_id, log_line=f"[error] Agent: {summary[:200]}")
        return {
            "agent_status": "error",
            "agent_result": summary,
            "run_id": getattr(result, "id", None),
            "duration_sec": duration,
            "stats": stats,
        }

    summary = (getattr(result, "result", None) or "")[:4000]
    _handle_text_chunk(run_id, summary, metrics)
    stats = metrics.to_dict()
    git_info = getattr(result, "git", None)
    commit_hash = None
    if git_info is not None:
        commit_hash = getattr(git_info, "commit_hash", None) or getattr(git_info, "commit", None)

    logger.info("Agent stream terminé status=%s duration=%ss", status, duration)
    update_run(
        run_id,
        phase="agent_done",
        message="Agent cloud terminé",
        log_line=f"[agent_done] status={status} duration={duration}s",
    )
    return {
        "agent_status": status,
        "agent_summary": summary,
        "commit_hint": commit_hash,
        "run_id": getattr(result, "id", None),
        "duration_sec": duration,
        "stats": stats,
    }
