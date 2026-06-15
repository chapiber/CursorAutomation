"""Charge la configuration des jobs depuis config/jobs.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_PARIS = ZoneInfo("Europe/Paris")


@dataclass(frozen=True)
class JobConfig:
    job_id: str
    handler: str
    repo: str
    repo_url: str
    branch: str
    deploy: str | None
    workspace_subdir: str
    stop_after: str | None = None
    skill: str | None = None
    prompt_file: str | None = None
    data_file: str | None = None


def job_is_expired(job: JobConfig, *, today: date | None = None) -> bool:
    """True si la date du jour (Paris) dépasse stop_after (dernier jour inclus)."""
    if not job.stop_after:
        return False
    current = today or datetime.now(_PARIS).date()
    return current > date.fromisoformat(job.stop_after)


def config_dir() -> Path:
    return Path(os.environ.get("CONFIG_DIR", "/config"))


def load_jobs() -> dict[str, JobConfig]:
    path = config_dir() / "jobs.json"
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    jobs: dict[str, JobConfig] = {}
    for job_id, entry in raw.items():
        jobs[job_id] = JobConfig(
            job_id=job_id,
            handler=entry.get("handler", "agent"),
            repo=entry["repo"],
            repo_url=entry.get("repo_url", f"https://github.com/{entry['repo']}.git"),
            branch=entry.get("branch", "main"),
            skill=entry.get("skill"),
            deploy=entry.get("deploy"),
            prompt_file=entry.get("prompt_file"),
            workspace_subdir=entry.get("workspace_subdir", entry["repo"].split("/")[-1]),
            stop_after=entry.get("stop_after"),
            data_file=entry.get("data_file"),
        )
    return jobs


def get_job(job_id: str) -> JobConfig:
    jobs = load_jobs()
    if job_id not in jobs:
        raise KeyError(f"Job inconnu : {job_id}")
    return jobs[job_id]


def load_prompt(job: JobConfig) -> str:
    if not job.prompt_file:
        raise FileNotFoundError(f"prompt_file non configuré pour job {job.job_id}")
    path = config_dir() / job.prompt_file
    if not path.is_file():
        raise FileNotFoundError(f"Prompt introuvable : {path}")
    return path.read_text(encoding="utf-8").strip()
