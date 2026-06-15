"""Fetchers CDM — normalisation des codes équipe."""

from __future__ import annotations

import re
from typing import Iterable

# Codes FIFA utilisés dans cdm2026.json
TEAM_CODES: frozenset[str] = frozenset(
    {
        "MEX", "KOR", "RSA", "CZE", "CAN", "BIH", "SUI", "QAT", "BRA", "MAR", "SCO", "HTI",
        "USA", "AUS", "PAR", "TUR", "GER", "ECU", "CIV", "CUW", "NED", "JPN", "TUN", "SWE",
        "BEL", "IRN", "EGY", "NZL", "ESP", "URU", "KSA", "CPV", "FRA", "SEN", "NOR", "IRQ",
        "ARG", "AUT", "ALG", "JOR", "POR", "COL", "UZB", "COD", "ENG", "CRO", "PAN", "GHA",
    }
)

NAME_ALIASES: dict[str, str] = {
    "mexique": "MEX",
    "mexico": "MEX",
    "corée du sud": "KOR",
    "coree du sud": "KOR",
    "south korea": "KOR",
    "afrique du sud": "RSA",
    "south africa": "RSA",
    "république tchèque": "CZE",
    "republique tcheque": "CZE",
    "czech republic": "CZE",
    "canada": "CAN",
    "bosnie-herzégovine": "BIH",
    "bosnie": "BIH",
    "suisse": "SUI",
    "switzerland": "SUI",
    "qatar": "QAT",
    "brésil": "BRA",
    "bresil": "BRA",
    "brazil": "BRA",
    "maroc": "MAR",
    "morocco": "MAR",
    "écosse": "SCO",
    "ecosse": "SCO",
    "scotland": "SCO",
    "haïti": "HTI",
    "haiti": "HTI",
    "états-unis": "USA",
    "etats-unis": "USA",
    "usa": "USA",
    "united states": "USA",
    "australie": "AUS",
    "australia": "AUS",
    "paraguay": "PAR",
    "turquie": "TUR",
    "turkey": "TUR",
    "allemagne": "GER",
    "germany": "GER",
    "équateur": "ECU",
    "equateur": "ECU",
    "ecuador": "ECU",
    "côte d'ivoire": "CIV",
    "cote d'ivoire": "CIV",
    "ivory coast": "CIV",
    "curaçao": "CUW",
    "curacao": "CUW",
    "pays-bas": "NED",
    "pays bas": "NED",
    "netherlands": "NED",
    "japon": "JPN",
    "japan": "JPN",
    "tunisie": "TUN",
    "tunisia": "TUN",
    "suède": "SWE",
    "suede": "SWE",
    "sweden": "SWE",
    "belgique": "BEL",
    "belgium": "BEL",
    "iran": "IRN",
    "égypte": "EGY",
    "egypte": "EGY",
    "egypt": "EGY",
    "nouvelle-zélande": "NZL",
    "nouvelle-zelande": "NZL",
    "new zealand": "NZL",
    "espagne": "ESP",
    "spain": "ESP",
    "uruguay": "URU",
    "arabie saoudite": "KSA",
    "saudi arabia": "KSA",
    "cap-vert": "CPV",
    "cape verde": "CPV",
    "france": "FRA",
    "sénégal": "SEN",
    "senegal": "SEN",
    "norvège": "NOR",
    "norvege": "NOR",
    "norway": "NOR",
    "irak": "IRQ",
    "iraq": "IRQ",
    "argentine": "ARG",
    "argentina": "ARG",
    "autriche": "AUT",
    "austria": "AUT",
    "algérie": "ALG",
    "algerie": "ALG",
    "algeria": "ALG",
    "jordanie": "JOR",
    "jordan": "JOR",
    "portugal": "POR",
    "colombie": "COL",
    "colombia": "COL",
    "ouzbékistan": "UZB",
    "ouzbekistan": "UZB",
    "uzbekistan": "UZB",
    "rd congo": "COD",
    "congo dr": "COD",
    "angleterre": "ENG",
    "england": "ENG",
    "croatie": "CRO",
    "croatia": "CRO",
    "panama": "PAN",
    "ghana": "GHA",
}

SCORE_LINE_RE = re.compile(
    r"(?P<home>[A-Z]{3})\s*(?P<hs>\d+)\s*[-–:]\s*(?P<aws>\d+)\s*(?P<away>[A-Z]{3})",
    re.IGNORECASE,
)

LIVE_MARKERS = ("live", "en direct", "mi-temps", "half-time", "ht ", " 1ère mi", " 2ème mi")


def normalize_team_code(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip()
    upper = cleaned.upper()
    if len(upper) == 3 and upper in TEAM_CODES:
        return upper
    key = cleaned.lower().replace("’", "'")
    return NAME_ALIASES.get(key)


def infer_status(text: str, *, has_score: bool) -> str:
    lower = text.lower()
    if any(marker in lower for marker in LIVE_MARKERS):
        return "live"
    if has_score:
        return "finished"
    return "scheduled"


def parse_score_lines(text: str, source: str) -> list:
    from ..models import ExternalMatch

    results: list[ExternalMatch] = []
    seen: set[tuple[str, str]] = set()
    for match in SCORE_LINE_RE.finditer(text):
        home = normalize_team_code(match.group("home"))
        away = normalize_team_code(match.group("away"))
        if not home or not away or home == away:
            continue
        key = (home, away)
        if key in seen:
            continue
        seen.add(key)
        context_start = max(0, match.start() - 80)
        context_end = min(len(text), match.end() + 80)
        context = text[context_start:context_end]
        hs = int(match.group("hs"))
        aws = int(match.group("aws"))
        status = infer_status(context, has_score=True)
        results.append(
            ExternalMatch(
                home=home,
                away=away,
                home_score=hs,
                away_score=aws,
                status=status,
                source=source,
            )
        )
    return results


def merge_external_lists(lists: Iterable[list]) -> list:
    """Fusionne les listes en conservant toutes les sources (merge.py décide)."""
    out: list = []
    for batch in lists:
        out.extend(batch)
    return out
