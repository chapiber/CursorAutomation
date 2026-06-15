"""Modèles pour la MAJ CDM 2026."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _format_kickoff_paris(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m %Hh")
    except ValueError:
        return ""


def _status_label(status: str | None) -> str:
    labels = {
        "finished": "terminé",
        "live": "en direct",
        "scheduled": "programmé",
    }
    return labels.get(status or "", status or "?")


def _format_score(home: int | None, away: int | None) -> str:
    if home is None or away is None:
        return "—"
    return f"{home}-{away}"


@dataclass
class UpdatedMatchInfo:
    """Détail métier d'un match dont le score a changé."""

    id: str
    stage: str
    group: str | None
    home: str
    away: str
    home_name: str
    away_name: str
    kickoff_paris: str | None
    previous_home: int | None
    previous_away: int | None
    previous_status: str
    new_home: int | None
    new_away: int | None
    new_status: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "stage": self.stage,
            "group": self.group,
            "home": self.home,
            "away": self.away,
            "home_name": self.home_name,
            "away_name": self.away_name,
            "kickoff_paris": self.kickoff_paris,
            "previous_home": self.previous_home,
            "previous_away": self.previous_away,
            "previous_status": self.previous_status,
            "new_home": self.new_home,
            "new_away": self.new_away,
            "new_status": self.new_status,
            "source": self.source,
        }

    def report_line(self) -> str:
        grp = f"groupe {self.group}" if self.group else self.stage
        kickoff = _format_kickoff_paris(self.kickoff_paris)
        when = f", {kickoff}" if kickoff else ""
        score = _format_score(self.new_home, self.new_away)
        line = (
            f"• {self.id} — {self.home_name} {score} {self.away_name}"
            f" ({grp}{when}) — {_status_label(self.new_status)}"
        )
        prev_score = _format_score(self.previous_home, self.previous_away)
        prev_status = self.previous_status or "scheduled"
        had_score = self.previous_home is not None and self.previous_away is not None
        if had_score and prev_score != score:
            line += f" (était {prev_score})"
        elif not had_score and prev_status != self.new_status:
            line += f" (était {_status_label(prev_status)})"
        return line


@dataclass(frozen=True)
class ExternalMatch:
    home: str
    away: str
    home_score: int | None
    away_score: int | None
    status: str  # scheduled | live | finished
    source: str


@dataclass
class UpdateStats:
    matches_updated: int = 0
    updated_matches: list[UpdatedMatchInfo] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    fetch_errors: list[str] = field(default_factory=list)

    def summary_text(self) -> str:
        lines = [
            "## Résumé MAJ CDM 2026 (programmatique)",
            f"- Matchs mis à jour : **{self.matches_updated}**",
            f"- Sources : {', '.join(self.sources) if self.sources else 'aucune'}",
        ]
        for match in self.updated_matches:
            lines.append(f"- {match.report_line().lstrip('• ')}")
        if self.conflicts:
            lines.append(f"- Conflits non résolus : {len(self.conflicts)}")
            for c in self.conflicts[:5]:
                lines.append(f"  - {c}")
        if self.fetch_errors:
            lines.append(f"- Erreurs fetch : {len(self.fetch_errors)}")
        lines.append("")
        lines.append(f"[CDM_STATS] {{\"matches_updated\": {self.matches_updated}}}")
        return "\n".join(lines)
