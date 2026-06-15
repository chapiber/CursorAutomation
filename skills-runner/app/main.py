"""API REST skills-runner."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .jobs import get_job, job_is_expired
from .run_store import create_run, get_latest_run, get_run, public_view
from .runner import execute_job, execute_job_async

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("skills-runner")

app = FastAPI(title="Cursor Skills Runner", version="0.2.0")


class RunRequest(BaseModel):
    job_id: str = Field(..., description="Identifiant du job (config/jobs.json)")


def verify_api_key(x_api_key: str | None) -> None:
    expected = os.environ.get("RUNNER_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=500, detail="RUNNER_API_KEY non configuré")
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="X-API-Key invalide")


def _resolve_job(job_id: str):
    try:
        return get_job(job_id)
    except KeyError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except FileNotFoundError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err


def _check_job_not_expired(job) -> None:
    if job_is_expired(job):
        raise HTTPException(
            status_code=410,
            detail={
                "job_expired": True,
                "job_id": job.job_id,
                "stop_after": job.stop_after,
                "message": f"Job expiré — dernière exécution autorisée le {job.stop_after}",
            },
        )


def _start_background(run_id: str, job) -> None:
    thread = threading.Thread(
        target=execute_job_async,
        args=(run_id, job),
        name=f"run-{run_id}",
        daemon=True,
    )
    thread.start()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "skills-runner"}


@app.post("/api/v1/runs", status_code=202)
def start_run(
    body: RunRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> JSONResponse:
    verify_api_key(x_api_key)
    job = _resolve_job(body.job_id)
    _check_job_not_expired(job)

    record = create_run(body.job_id)
    run_id = record["run_id"]
    logger.info("Run async démarré run_id=%s job_id=%s", run_id, body.job_id)

    background_tasks.add_task(_start_background, run_id, job)

    payload = public_view(record)
    return JSONResponse(status_code=202, content=payload)


@app.get("/api/v1/runs/latest")
def latest_run(
    job_id: str = Query(..., description="Identifiant du job"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    verify_api_key(x_api_key)
    record = get_latest_run(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Aucun run pour job_id={job_id}")
    return public_view(record)


@app.get("/api/v1/runs/{run_id}")
def run_status(
    run_id: str,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    verify_api_key(x_api_key)
    record = get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run inconnu : {run_id}")
    return public_view(record)


@app.post("/api/v1/run")
def run_job(
    body: RunRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    """Exécution synchrone (legacy — préférer POST /api/v1/runs)."""
    verify_api_key(x_api_key)
    job = _resolve_job(body.job_id)
    _check_job_not_expired(job)

    logger.info("Run sync demandé job_id=%s", body.job_id)
    result = execute_job(job)
    logger.info("Run sync terminé job_id=%s status=%s", body.job_id, result.get("status"))

    if result.get("status") != "ok":
        raise HTTPException(status_code=502, detail=result)

    return result
