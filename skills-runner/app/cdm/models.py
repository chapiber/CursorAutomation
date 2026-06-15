"""Modèles pour la MAJ CDM 2026."""

from __future__ import annotations

from dataclasses import dataclass, field


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
    sources: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    fetch_errors: list[str] = field(default_factory=list)

    def summary_text(self) -> str:
        lines = [
            "## Résumé MAJ CDM 2026 (programmatique)",
            f"- Matchs mis à jour : **{self.matches_updated}**",
            f"- Sources : {', '.join(self.sources) if self.sources else 'aucune'}",
        ]
        if self.conflicts:
            lines.append(f"- Conflits non résolus : {len(self.conflicts)}")
            for c in self.conflicts[:5]:
                lines.append(f"  - {c}")
        if self.fetch_errors:
            lines.append(f"- Erreurs fetch : {len(self.fetch_errors)}")
        lines.append("")
        lines.append(f"[CDM_STATS] {{\"matches_updated\": {self.matches_updated}}}")
        return "\n".join(lines)
