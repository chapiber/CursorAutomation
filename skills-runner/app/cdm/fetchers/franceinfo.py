"""Source franceinfo — calendrier / résultats CDM 2026."""

from __future__ import annotations

from typing import Callable

from bs4 import BeautifulSoup

from ..models import ExternalMatch
from .base import parse_score_lines

URL = (
    "https://www.franceinfo.fr/coupe-du-monde/calendrier-de-la-coupe-du-monde-2026"
    "-a-quelle-heure-et-sur-quelle-chaine-suivre-tous-les-matchs-du-grand-rendez-vous"
    "-du-football-mondial_8040074.html"
)
SOURCE = "franceinfo"


def fetch(http_get: Callable[[str], str]) -> tuple[list[ExternalMatch], str]:
    html = http_get(URL)
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    matches = parse_score_lines(text, SOURCE)
    return matches, SOURCE
