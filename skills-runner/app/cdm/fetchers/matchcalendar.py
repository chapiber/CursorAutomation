"""Source matchcalendar.football."""

from __future__ import annotations

from typing import Callable

from bs4 import BeautifulSoup

from ..models import ExternalMatch
from .base import parse_score_lines

URL = "https://matchcalendar.football/"
SOURCE = "matchcalendar.football"


def fetch(http_get: Callable[[str], str]) -> tuple[list[ExternalMatch], str]:
    html = http_get(URL)
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    matches = parse_score_lines(text, SOURCE)
    # Complément : balises data-* ou classes si présentes
    for node in soup.select("[data-home][data-away]"):
        home = node.get("data-home", "")
        away = node.get("data-away", "")
        score = node.get("data-score", "")
        if home and away and score and "-" in score:
            text_block = f"{home} {score.replace('-', ' - ')} {away}"
            matches.extend(parse_score_lines(text_block, SOURCE))
    return _dedupe(matches), SOURCE


def _dedupe(matches: list[ExternalMatch]) -> list[ExternalMatch]:
    seen: set[tuple[str, str, int | None, int | None]] = set()
    out: list[ExternalMatch] = []
    for m in matches:
        key = (m.home, m.away, m.home_score, m.away_score)
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    return out
