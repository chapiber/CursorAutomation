"""Fetchers web pour scores CDM 2026."""

from __future__ import annotations

import logging
from typing import Callable

import httpx

from ..models import ExternalMatch
from .base import merge_external_lists, parse_score_lines
from . import franceinfo, fifa, matchcalendar

logger = logging.getLogger("skills-runner.cdm")

USER_AGENT = "skills-runner-cdm/1.0 (+https://github.com/chapiber/CursorAutomation)"
TIMEOUT = 30.0

FetcherFn = Callable[[], tuple[list[ExternalMatch], str]]


def _http_get(url: str) -> str:
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def fetch_all() -> tuple[list[ExternalMatch], list[str], list[str]]:
    """Interroge toutes les sources ; erreurs non bloquantes."""
    errors: list[str] = []
    sources: list[str] = []
    batches: list[list[ExternalMatch]] = []

    for fetcher in (matchcalendar.fetch, franceinfo.fetch, fifa.fetch):
        try:
            matches, source = fetcher(_http_get)
            if matches:
                batches.append(matches)
                if source not in sources:
                    sources.append(source)
        except Exception as err:
            name = getattr(fetcher, "__module__", "fetcher").rsplit(".", 1)[-1]
            msg = f"{name}: {err}"
            logger.warning("Fetch CDM échoué — %s", msg)
            errors.append(msg)

    return merge_external_lists(batches), errors, sources


def parse_html_snapshot(html: str, source: str) -> list[ExternalMatch]:
    """Utilitaire tests — parse un snapshot HTML."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    matches = parse_score_lines(text, source)
    for node in soup.select("[data-home][data-away]"):
        home = node.get("data-home", "")
        away = node.get("data-away", "")
        score = node.get("data-score", "")
        if home and away and score and "-" in score:
            block = f"{home} {score.replace('-', ' - ')} {away}"
            matches.extend(parse_score_lines(block, source))
    return matches
