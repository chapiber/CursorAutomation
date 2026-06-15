"""Source FIFA — page scores (optionnelle)."""

from __future__ import annotations

from typing import Callable

from bs4 import BeautifulSoup

from ..models import ExternalMatch
from .base import parse_score_lines

URL = "https://www.fifa.com/fifaplus/en/tournaments/mens/worldcup/canadamexicousa2026/scores"
SOURCE = "fifa.com"


def fetch(http_get: Callable[[str], str]) -> tuple[list[ExternalMatch], str]:
    html = http_get(URL)
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    matches = parse_score_lines(text, SOURCE)
    return matches, SOURCE
