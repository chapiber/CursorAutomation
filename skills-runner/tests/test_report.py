"""Tests compte-rendu programmatique."""

from app.report import build_report_text


def test_report_cdm_programmatic_no_tokens():
    record = {
        "status": "done",
        "job_id": "cdm2026-daily",
        "result": {
            "handler": "cdm_update",
            "cdm": {"duration_sec": 42, "stats": {"matches_updated": 3}},
            "git_push": {"files_committed": 1},
            "commit": "abc1234",
            "duration_sec": 55,
        },
    }
    text = build_report_text(record)
    assert "Durée MAJ : 42 s" in text
    assert "Matchs mis à jour : 3" in text
    assert "Tokens" not in text
    assert "Commit : abc1234" in text
