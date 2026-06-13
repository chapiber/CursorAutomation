"""API REST skills-runner."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .jobs import get_job
from .runner import execute_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("skills-runner")

app = FastAPI(title="Cursor Skills Runner", version="0.1.0")


class RunRequest(BaseModel):
    job_id: str = Field(..., description="Identifiant du job (config/jobs.json)")


def verify_api_key(x_api_key: str | None) -> None:
    expected = os.environ.get("RUNNER_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=500, detail="RUNNER_API_KEY non configuré")
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="X-API-Key invalide")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "skills-runner"}


@app.post("/api/v1/run")
def run_job(
    body: RunRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    verify_api_key(x_api_key)

    try:
        job = get_job(body.job_id)
    except KeyError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except FileNotFoundError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err

    logger.info("Run demandé job_id=%s", body.job_id)
    result = execute_job(job)
    logger.info("Run terminé job_id=%s status=%s", body.job_id, result.get("status"))

    if result.get("status") != "ok":
        raise HTTPException(status_code=502, detail=result)

    return result
