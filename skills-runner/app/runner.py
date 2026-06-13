"""Invocation Cursor SDK cloud + orchestration git pull / deploy."""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from cursor_sdk import Agent, AgentOptions, CloudAgentOptions, CloudRepository, CursorAgentError

from .jobs import JobConfig, load_prompt

logger = logging.getLogger("skills-runner")

AGENT_TIMEOUT_SEC = int(os.environ.get("AGENT_TIMEOUT_SEC", "1200"))


def workspace_path(job: JobConfig) -> Path:
    base = Path(os.environ.get("WORKSPACE_DIR", "/workspaces"))
    return base / job.workspace_subdir


def run_cloud_agent(job: JobConfig) -> dict[str, Any]:
    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("CURSOR_API_KEY manquant")

    prompt = load_prompt(job)
    repo_url = f"https://github.com/{job.repo}"

    logger.info("Démarrage agent cloud job=%s repo=%s", job.job_id, job.repo)
    started = time.time()

    try:
        result = Agent.prompt(
            prompt,
            AgentOptions(
                model="composer-2.5",
                api_key=api_key,
                cloud=CloudAgentOptions(
                    repos=[
                        CloudRepository(
                            url=repo_url,
                            starting_ref=job.branch,
                        )
                    ],
                    skip_reviewer_request=True,
                ),
            ),
        )
    except CursorAgentError as err:
        logger.error("Échec démarrage agent : %s (retryable=%s)", err.message, err.is_retryable)
        return {
            "agent_status": "startup_error",
            "agent_error": err.message,
            "duration_sec": round(time.time() - started, 1),
        }

    duration = round(time.time() - started, 1)

    if result.status == "error":
        logger.error("Run agent en erreur run_id=%s", getattr(result, "id", "?"))
        return {
            "agent_status": "error",
            "agent_result": (result.result or "")[:2000],
            "run_id": getattr(result, "id", None),
            "duration_sec": duration,
        }

    summary = (result.result or "")[:4000]
    git_info = getattr(result, "git", None)
    commit_hash = None
    if git_info is not None:
        commit_hash = getattr(git_info, "commit_hash", None) or getattr(git_info, "commit", None)

    logger.info("Agent terminé status=%s duration=%ss", result.status, duration)
    return {
        "agent_status": result.status,
        "agent_summary": summary,
        "commit_hint": commit_hash,
        "run_id": getattr(result, "id", None),
        "duration_sec": duration,
    }


def ensure_workspace_clone(job: JobConfig) -> Path:
    ws = workspace_path(job)
    ws.parent.mkdir(parents=True, exist_ok=True)

    if not (ws / ".git").is_dir():
        logger.info("Clone initial %s -> %s", job.repo_url, ws)
        subprocess.run(
            ["git", "clone", "--branch", job.branch, job.repo_url, str(ws)],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    return ws


def git_pull(job: JobConfig) -> dict[str, Any]:
    ws = ensure_workspace_clone(job)
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = "ssh -o StrictHostKeyChecking=accept-new -i /secrets/id_ed25519"

    proc = subprocess.run(
        ["git", "pull", "--ff-only", "origin", job.branch],
        cwd=ws,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    if proc.returncode != 0:
        # Retry sans clé SSH (repo public en HTTPS)
        proc = subprocess.run(
            ["git", "pull", "--ff-only", "origin", job.branch],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=120,
        )

    head_proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ws,
        capture_output=True,
        text=True,
        check=True,
    )
    commit = head_proc.stdout.strip()

    return {
        "pull_ok": proc.returncode == 0,
        "pull_stderr": proc.stderr[:500] if proc.returncode != 0 else "",
        "commit": commit,
    }


def run_deploy(job: JobConfig) -> dict[str, Any]:
    if not job.deploy:
        return {"deploy": "skipped", "reason": "no deploy configured"}

    script = Path(f"/deploy-scripts/{job.deploy}.sh")
    if not script.is_file():
        raise FileNotFoundError(f"Script deploy introuvable : {script}")

    ws = workspace_path(job)
    env = os.environ.copy()
    env["SOURCE_DIR"] = str(ws / "site")
    env["LOG_DIR"] = str(ws / "deploy_logs")

    proc = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )

    return {
        "deploy": "ok" if proc.returncode == 0 else "error",
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-1500:] if proc.stdout else "",
        "stderr_tail": proc.stderr[-500:] if proc.stderr else "",
    }


def execute_job(job: JobConfig) -> dict[str, Any]:
    started = time.time()
    out: dict[str, Any] = {"job_id": job.job_id, "repo": job.repo, "skill": job.skill}

    agent_result = run_cloud_agent(job)
    out["agent"] = agent_result

    if agent_result.get("agent_status") not in ("finished",):
        out["status"] = "error"
        out["duration_sec"] = round(time.time() - started, 1)
        return out

    pull_result = git_pull(job)
    out["git_pull"] = pull_result

    if not pull_result.get("pull_ok"):
        out["status"] = "error"
        out["duration_sec"] = round(time.time() - started, 1)
        return out

    deploy_result = run_deploy(job)
    out["deploy_result"] = deploy_result

    if deploy_result.get("deploy") == "error":
        out["status"] = "error"
    else:
        out["status"] = "ok"
        out["commit"] = pull_result.get("commit")

    out["duration_sec"] = round(time.time() - started, 1)
    return out
