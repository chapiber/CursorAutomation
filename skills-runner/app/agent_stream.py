"""Agent cloud avec streaming des messages vers run_store."""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

from cursor_sdk import Agent, AgentOptions, CloudAgentOptions, CloudRepository, CursorAgentError

from .jobs import JobConfig, load_prompt
from .run_store import update_run

logger = logging.getLogger("skills-runner")

PROGRESS_RE = re.compile(r"\[CDM_PROGRESS\]\s*(.+)", re.IGNORECASE)
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


def _handle_text_chunk(run_id: str, text: str) -> None:
    if not text:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        update_run(run_id, log_line=line)
        match = PROGRESS_RE.search(line)
        if match:
            update_run(run_id, message=match.group(1).strip(), phase="agent_running")


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
            run = agent.send(prompt)

            if hasattr(run, "messages"):
                for message in run.messages():
                    chunk = _extract_message_text(message)
                    _handle_text_chunk(run_id, chunk)

            result = run.wait()
    except CursorAgentError as err:
        logger.error("Échec agent stream : %s (retryable=%s)", err.message, err.is_retryable)
        update_run(run_id, log_line=f"[error] {err.message}")
        return {
            "agent_status": "startup_error",
            "agent_error": err.message,
            "duration_sec": round(time.time() - started, 1),
        }
    except Exception as err:
        logger.exception("Exception agent stream run_id=%s", run_id)
        update_run(run_id, log_line=f"[error] {err}")
        return {
            "agent_status": "startup_error",
            "agent_error": str(err),
            "duration_sec": round(time.time() - started, 1),
        }

    duration = round(time.time() - started, 1)
    status = getattr(result, "status", "error")

    if status == "error":
        logger.error("Run agent en erreur run_id=%s", getattr(result, "id", "?"))
        summary = (getattr(result, "result", None) or "")[:2000]
        update_run(run_id, log_line=f"[error] Agent: {summary[:200]}")
        return {
            "agent_status": "error",
            "agent_result": summary,
            "run_id": getattr(result, "id", None),
            "duration_sec": duration,
        }

    summary = (getattr(result, "result", None) or "")[:4000]
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
    }
