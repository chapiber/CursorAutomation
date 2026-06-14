"""Invocation Cursor SDK cloud + orchestration git pull / deploy."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
import traceback
from pathlib import Path
from typing import Any

from cursor_sdk import Agent, AgentOptions, CloudAgentOptions, CloudRepository, CursorAgentError

from .agent_stream import is_agent_success, run_cloud_agent_streaming
from .jobs import JobConfig, load_prompt
from .report import build_report_text
from .run_store import update_run

logger = logging.getLogger("skills-runner")

AGENT_TIMEOUT_SEC = int(os.environ.get("AGENT_TIMEOUT_SEC", "1200"))


def workspace_path(job: JobConfig) -> Path:
    base = Path(os.environ.get("WORKSPACE_DIR", "/workspaces"))
    return base / job.workspace_subdir


def run_cloud_agent(job: JobConfig) -> dict[str, Any]:
    """Mode sync legacy (Agent.prompt)."""
    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not api_key:
        return {
            "agent_status": "startup_error",
            "agent_error": "CURSOR_API_KEY manquant",
            "duration_sec": 0,
        }

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
    except Exception as err:
        logger.exception("Exception agent cloud job=%s", job.job_id)
        return {
            "agent_status": "startup_error",
            "agent_error": str(err),
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


def ensure_workspace_clone(job: JobConfig) -> tuple[Path, dict[str, Any] | None]:
    """Clone ou réutilise le workspace. Retourne (path, erreur éventuelle)."""
    ws = workspace_path(job)
    ws.parent.mkdir(parents=True, exist_ok=True)

    if (ws / ".git").is_dir():
        return ws, None

    if ws.exists():
        logger.warning("Workspace %s existe sans .git — réinitialisation", ws)
        shutil.rmtree(ws)

    logger.info("Clone initial %s -> %s", job.repo_url, ws)
    proc = subprocess.run(
        ["git", "clone", "--branch", job.branch, job.repo_url, str(ws)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "git clone échoué")[:500]
        logger.error("git clone échoué : %s", err)
        return ws, {"clone_ok": False, "clone_stderr": err}

    return ws, None


def _git_rev_parse(ws: Path, ref: str = "HEAD") -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", ref],
        cwd=ws,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def count_committed_files(ws: Path, head_before: str | None, head_after: str | None) -> int:
    if not head_before or not head_after or head_before == head_after:
        return 0
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{head_before}..{head_after}"],
        cwd=ws,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return 0
    return len([line for line in proc.stdout.splitlines() if line.strip()])


def git_pull(job: JobConfig) -> dict[str, Any]:
    ws, clone_err = ensure_workspace_clone(job)
    if clone_err:
        return {
            "pull_ok": False,
            "pull_stderr": clone_err.get("clone_stderr", ""),
            "commit": None,
            "files_committed": 0,
        }

    head_before = _git_rev_parse(ws)

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
        proc = subprocess.run(
            ["git", "pull", "--ff-only", "origin", job.branch],
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=120,
        )

    head_after = _git_rev_parse(ws)
    head_proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ws,
        capture_output=True,
        text=True,
    )
    commit = head_proc.stdout.strip() if head_proc.returncode == 0 else None
    files_committed = count_committed_files(ws, head_before, head_after)

    return {
        "pull_ok": proc.returncode == 0,
        "pull_stderr": (proc.stderr or "")[:500] if proc.returncode != 0 else "",
        "commit": commit,
        "files_committed": files_committed,
    }


def run_deploy(job: JobConfig) -> dict[str, Any]:
    if not job.deploy:
        return {"deploy": "skipped", "reason": "no deploy configured"}

    script = Path(f"/deploy-scripts/{job.deploy}.sh")
    if not script.is_file():
        return {"deploy": "error", "exit_code": -1, "stderr_tail": f"Script introuvable : {script}"}

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


def _finalize_error(out: dict[str, Any], phase: str, message: str, started: float) -> dict[str, Any]:
    out["status"] = "error"
    out["phase"] = phase
    out["error"] = message
    out["duration_sec"] = round(time.time() - started, 1)
    return out


def execute_job(job: JobConfig) -> dict[str, Any]:
    """Exécution synchrone (legacy)."""
    started = time.time()
    out: dict[str, Any] = {"job_id": job.job_id, "repo": job.repo, "skill": job.skill}

    try:
        agent_result = run_cloud_agent(job)
        out["agent"] = agent_result

        if not is_agent_success(agent_result.get("agent_status")):
            return _finalize_error(
                out,
                "agent",
                agent_result.get("agent_error") or agent_result.get("agent_result") or "Agent échoué",
                started,
            )

        pull_result = git_pull(job)
        out["git_pull"] = pull_result

        if not pull_result.get("pull_ok"):
            return _finalize_error(
                out,
                "git_pull",
                pull_result.get("pull_stderr") or "git pull échoué",
                started,
            )

        deploy_result = run_deploy(job)
        out["deploy_result"] = deploy_result

        if deploy_result.get("deploy") == "error":
            return _finalize_error(
                out,
                "deploy",
                deploy_result.get("stderr_tail") or "deploy échoué",
                started,
            )

        out["status"] = "ok"
        out["phase"] = "done"
        out["commit"] = pull_result.get("commit")
        out["duration_sec"] = round(time.time() - started, 1)
        return out

    except Exception as err:
        logger.exception("execute_job exception job=%s", job.job_id)
        out["traceback_tail"] = traceback.format_exc()[-1500:]
        return _finalize_error(out, "exception", str(err), started)


def _attach_report(out: dict[str, Any], run_id: str, job: JobConfig, status: str, message: str) -> dict[str, Any]:
    record = {
        "run_id": run_id,
        "job_id": job.job_id,
        "status": status,
        "phase": out.get("phase", status),
        "message": message,
        "result": out,
    }
    out["report_text"] = build_report_text(record)
    return out


def execute_job_async(run_id: str, job: JobConfig) -> None:
    """Exécution async avec suivi run_store."""
    started = time.time()
    out: dict[str, Any] = {"job_id": job.job_id, "repo": job.repo, "skill": job.skill}

    try:
        agent_result = run_cloud_agent_streaming(job, run_id)
        out["agent"] = agent_result

        if not is_agent_success(agent_result.get("agent_status")):
            msg = agent_result.get("agent_error") or agent_result.get("agent_result") or "Agent échoué"
            result = _finalize_error(out, "agent", msg, started)
            _attach_report(result, run_id, job, "error", msg)
            update_run(run_id, status="error", phase="error", message=msg, result=result)
            return

        update_run(run_id, phase="git_pull", message="git pull en cours")
        pull_result = git_pull(job)
        out["git_pull"] = pull_result
        update_run(run_id, log_line=f"[git_pull] ok={pull_result.get('pull_ok')} commit={pull_result.get('commit')} files={pull_result.get('files_committed', 0)}")

        if not pull_result.get("pull_ok"):
            msg = pull_result.get("pull_stderr") or "git pull échoué"
            result = _finalize_error(out, "git_pull", msg, started)
            _attach_report(result, run_id, job, "error", msg)
            update_run(run_id, status="error", phase="error", message=msg, result=result)
            return

        update_run(run_id, phase="deploy", message="Déploiement portailClub")
        deploy_result = run_deploy(job)
        out["deploy_result"] = deploy_result
        update_run(run_id, log_line=f"[deploy] status={deploy_result.get('deploy')}")

        if deploy_result.get("deploy") == "error":
            msg = deploy_result.get("stderr_tail") or "deploy échoué"
            result = _finalize_error(out, "deploy", msg, started)
            _attach_report(result, run_id, job, "error", msg)
            update_run(run_id, status="error", phase="error", message=msg, result=result)
            return

        out["status"] = "ok"
        out["phase"] = "done"
        out["commit"] = pull_result.get("commit")
        out["duration_sec"] = round(time.time() - started, 1)
        done_msg = f"Terminé — commit {out.get('commit')}"
        _attach_report(out, run_id, job, "done", done_msg)
        update_run(
            run_id,
            status="done",
            phase="done",
            message=done_msg,
            result=out,
        )
        logger.info("Run async terminé run_id=%s status=ok", run_id)

    except Exception as err:
        logger.exception("execute_job_async exception run_id=%s", run_id)
        result = _finalize_error(out, "exception", str(err), started)
        result["traceback_tail"] = traceback.format_exc()[-1500:]
        _attach_report(result, run_id, job, "error", str(err))
        update_run(run_id, status="error", phase="error", message=str(err), result=result)
