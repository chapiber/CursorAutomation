"""Persistance JSON des runs async (phases + journal)."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .report import build_report_text

_lock = threading.Lock()
_MAX_LOG_LINES = 200
_LOG_TAIL_SIZE = 20

PHASES = (
    "queued",
    "agent_starting",
    "agent_running",
    "agent_done",
    "git_pull",
    "deploy",
    "done",
)


def runs_dir() -> Path:
    base = Path(os.environ.get("LOG_DIR", "/app/logs"))
    path = base / "runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_path(run_id: str) -> Path:
    return runs_dir() / f"{run_id}.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def create_run(job_id: str) -> dict[str, Any]:
    run_id = uuid.uuid4().hex[:12]
    now = _now_iso()
    record: dict[str, Any] = {
        "run_id": run_id,
        "job_id": job_id,
        "status": "running",
        "phase": "queued",
        "message": "Run en file d'attente",
        "agent_id": None,
        "started_at": now,
        "updated_at": now,
        "log_lines": [],
        "result": None,
    }
    with _lock:
        _write(_run_path(run_id), record)
    return record


def get_run(run_id: str) -> dict[str, Any] | None:
    path = _run_path(run_id)
    if not path.is_file():
        return None
    with _lock:
        return _read(path)


def get_latest_run(job_id: str) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    latest_ts = ""
    for path in runs_dir().glob("*.json"):
        try:
            data = _read(path)
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("job_id") != job_id:
            continue
        started = data.get("started_at") or ""
        if started >= latest_ts:
            latest_ts = started
            latest = data
    return latest


def update_run(
    run_id: str,
    *,
    status: str | None = None,
    phase: str | None = None,
    message: str | None = None,
    agent_id: str | None = None,
    log_line: str | None = None,
    result: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    path = _run_path(run_id)
    with _lock:
        if not path.is_file():
            return None
        data = _read(path)
        if status is not None:
            data["status"] = status
        if phase is not None:
            data["phase"] = phase
        if message is not None:
            data["message"] = message
        if agent_id is not None:
            data["agent_id"] = agent_id
        if log_line is not None:
            lines: list[str] = data.setdefault("log_lines", [])
            lines.append(log_line)
            if len(lines) > _MAX_LOG_LINES:
                data["log_lines"] = lines[-_MAX_LOG_LINES:]
        if result is not None:
            data["result"] = result
        data["updated_at"] = _now_iso()
        _write(path, data)
        return data


def public_view(record: dict[str, Any]) -> dict[str, Any]:
    started = record.get("started_at", "")
    elapsed = 0.0
    if started:
        try:
            dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            elapsed = round(time.time() - dt.timestamp(), 1)
        except ValueError:
            elapsed = 0.0
    lines: list[str] = record.get("log_lines") or []
    view: dict[str, Any] = {
        "run_id": record["run_id"],
        "job_id": record["job_id"],
        "status": record["status"],
        "phase": record["phase"],
        "message": record.get("message", ""),
        "agent_id": record.get("agent_id"),
        "elapsed_sec": elapsed,
        "started_at": started,
        "updated_at": record.get("updated_at"),
        "log_tail": lines[-_LOG_TAIL_SIZE:],
        "result": record.get("result"),
    }
    view["report_text"] = build_report_text({**record, "elapsed_sec": elapsed})
    return view
