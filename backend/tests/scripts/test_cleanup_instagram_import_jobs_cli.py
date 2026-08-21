from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from backend.scripts.cleanup_instagram_import_jobs import main
from app.schemas.import_jobs import ImportJobRecord, ImportJobState


def _job(job_id: str, state: ImportJobState) -> ImportJobRecord:
    now = datetime.now(timezone.utc)
    return ImportJobRecord(
        id=job_id,
        owner_email="admin@example.com",
        canonical_reel_url="https://www.instagram.com/reel/abc123/",
        state=state,
        version=1,
        next_advance_at=now,
        stale_deadline=now,
        created_at=now,
        updated_at=now,
    )


def test_cleanup_defaults_to_dry_run_and_reports_all_three_stages(capsys):
    with (
        patch(
            "backend.scripts.cleanup_instagram_import_jobs.terminalize_stale_jobs"
        ) as terminalize,
        patch(
            "backend.scripts.cleanup_instagram_import_jobs.reconcile_provider_admission"
        ) as reconcile,
        patch(
            "backend.scripts.cleanup_instagram_import_jobs.delete_expired_terminal_jobs"
        ) as delete_expired,
    ):
        terminalize.return_value = [_job("job-1", ImportJobState.FAILED)]
        reconcile.return_value = [{"id": True}]
        delete_expired.return_value = [_job("job-2", ImportJobState.SUCCEEDED)]

        exit_code = main([])

    assert exit_code == 0
    terminalize.assert_called_once_with(dry_run=True)
    reconcile.assert_called_once_with(dry_run=True)
    delete_expired.assert_called_once_with(dry_run=True)

    output = capsys.readouterr().out
    assert "Stale jobs terminalized: 1" in output
    assert "job-1 (failed)" in output
    assert "Provider admission slots reconciled: 1" in output
    assert "Expired terminal jobs deleted: 1" in output
    assert "job-2 (succeeded)" in output
    assert "Dry run" in output


def test_cleanup_apply_flag_disables_dry_run():
    with (
        patch(
            "backend.scripts.cleanup_instagram_import_jobs.terminalize_stale_jobs",
            return_value=[],
        ) as terminalize,
        patch(
            "backend.scripts.cleanup_instagram_import_jobs.reconcile_provider_admission",
            return_value=[],
        ) as reconcile,
        patch(
            "backend.scripts.cleanup_instagram_import_jobs.delete_expired_terminal_jobs",
            return_value=[],
        ) as delete_expired,
    ):
        exit_code = main(["--apply"])

    assert exit_code == 0
    terminalize.assert_called_once_with(dry_run=False)
    reconcile.assert_called_once_with(dry_run=False)
    delete_expired.assert_called_once_with(dry_run=False)
