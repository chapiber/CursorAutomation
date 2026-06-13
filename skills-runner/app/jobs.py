"""Charge la configuration des jobs depuis config/jobs.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class JobConfig:
    job_id: str
    repo: str
    repo_url: str
    branch: str
    skill: str
    deploy: str | None
    prompt_file: str
    workspace_subdir: str


def config_dir() -> Path:
    return Path(os.environ.get("CONFIG_DIR", "/config"))


def load_jobs() -> dict[str, JobConfig]:
    path = config_dir() / "jobs.json"
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    jobs: dict[str, JobConfig] = {}
    for job_id, entry in raw.items():
        jobs[job_id] = JobConfig(
            job_id=job_id,
            repo=entry["repo"],
            repo_url=entry.get("repo_url", f"https://github.com/{entry['repo']}.git"),
            branch=entry.get("branch", "main"),
            skill=entry["skill"],
            deploy=entry.get("deploy"),
            prompt_file=entry["prompt_file"],
            workspace_subdir=entry.get("workspace_subdir", entry["repo"].split("/")[-1]),
        )
    return jobs


def get_job(job_id: str) -> JobConfig:
    jobs = load_jobs()
    if job_id not in jobs:
        raise KeyError(f"Job inconnu : {job_id}")
    return jobs[job_id]


def load_prompt(job: JobConfig) -> str:
    path = config_dir() / job.prompt_file
    if not path.is_file():
        raise FileNotFoundError(f"Prompt introuvable : {path}")
    return path.read_text(encoding="utf-8").strip()
