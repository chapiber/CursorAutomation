"""Tests compte-rendu programmatique."""

from app.report import build_report_text


def test_report_cdm_programmatic_no_tokens():
    record = {
        "status": "done",
        "job_id": "cdm2026-daily",
        "result": {
            "handler": "cdm_update",
            "cdm": {
                "duration_sec": 42,
                "stats": {
                    "matches_updated": 1,
                    "updated_matches": [
                        {
                            "id": "M005",
                            "stage": "group",
                            "group": "C",
                            "home": "HTI",
                            "away": "SCO",
                            "home_name": "Haïti",
                            "away_name": "Écosse",
                            "kickoff_paris": "2026-06-14T03:00:00+02:00",
                            "previous_home": None,
                            "previous_away": None,
                            "previous_status": "scheduled",
                            "new_home": 0,
                            "new_away": 2,
                            "new_status": "finished",
                            "source": "franceinfo",
                        }
                    ],
                },
            },
            "git_push": {"files_committed": 1},
            "commit": "abc1234",
            "duration_sec": 55,
        },
    }
    text = build_report_text(record)
    assert "Durée MAJ : 42 s" in text
    assert "Matchs mis à jour : 1" in text
    assert "Matchs modifiés :" in text
    assert "Haïti 0-2 Écosse" in text
    assert "groupe C" in text
    assert "terminé" in text
    assert "Tokens" not in text
    assert "Commit : abc1234" in text
