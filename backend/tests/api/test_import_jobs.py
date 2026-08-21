from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.app.api.auth import AuthenticatedAdmin, require_admin_user
from backend.app.repositories.import_jobs import ImportJobStorageError
from backend.app.schemas.import_jobs import ImportJobRecord, ImportJobState


client = TestClient(app)


def _job(**overrides) -> ImportJobRecord:
    now = datetime.now(timezone.utc)
    fields = {
        "id": "job-1",
        "owner_email": "admin@example.com",
        "canonical_reel_url": "https://www.instagram.com/reel/DZuzc9PNedT/",
        "state": ImportJobState.WAITING_REEL,
        "version": 1,
        "next_advance_at": now,
        "stale_deadline": now + timedelta(minutes=30),
        "created_at": now,
        "updated_at": now,
    }
    fields.update(overrides)
    return ImportJobRecord(**fields)


def _authenticated():
    app.dependency_overrides[require_admin_user] = lambda: AuthenticatedAdmin(
        email="admin@example.com", access_token="admin-token"
    )


def test_advance_returns_404_for_missing_or_wrong_owner_job():
    _authenticated()
    try:
        with patch(
            "backend.app.api.routes.import_jobs.get_job_for_owner", return_value=None
        ):
            response = client.post("/api/extract/jobs/job-1/advance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_advance_returns_result_envelope_for_terminal_succeeded_job():
    _authenticated()
    job = _job(
        state=ImportJobState.SUCCEEDED,
        normalized_result_json={
            "source_url": "https://www.instagram.com/reel/DZuzc9PNedT/",
            "final_url": "https://www.instagram.com/reel/DZuzc9PNedT/",
            "title": "Chia Pudding",
            "image_url": None,
            "recipes": [
                {
                    "name": "Chia Pudding",
                    "ingredients": ["1 cup chia"],
                    "instructions": ["Soak overnight."],
                }
            ],
            "database_saved": True,
            "database_message": "Recipe saved to your collection.",
            "parse_status": "recipe",
        },
    )
    try:
        with patch(
            "backend.app.api.routes.import_jobs.get_job_for_owner", return_value=job
        ):
            response = client.post("/api/extract/jobs/job-1/advance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "result"
    assert body["result"]["recipes"][0]["name"] == "Chia Pudding"


def test_advance_returns_failed_envelope_for_terminal_failed_job():
    _authenticated()
    job = _job(state=ImportJobState.FAILED, error_code="provider_timeout")
    try:
        with patch(
            "backend.app.api.routes.import_jobs.get_job_for_owner", return_value=job
        ):
            response = client.post("/api/extract/jobs/job-1/advance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "failed"
    assert body["job_id"] == "job-1"
    assert body["error_code"] == "provider_timeout"
    assert body["message"]


def test_advance_returns_result_envelope_for_terminal_not_recipe_job():
    _authenticated()
    job = _job(
        state=ImportJobState.NOT_RECIPE,
        normalized_result_json={
            "source_url": "https://www.instagram.com/reel/DZuzc9PNedT/",
            "final_url": "https://www.instagram.com/reel/DZuzc9PNedT/",
            "title": None,
            "image_url": None,
            "recipes": [],
            "database_saved": False,
            "database_message": "Skipped — not a recipe.",
            "parse_status": "not_recipe",
        },
    )
    try:
        with patch(
            "backend.app.api.routes.import_jobs.get_job_for_owner", return_value=job
        ):
            response = client.post("/api/extract/jobs/job-1/advance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "result"
    assert body["result"]["parse_status"] == "not_recipe"


def test_advance_claims_lease_and_returns_orchestrated_pending_snapshot():
    _authenticated()
    job = _job(version=1)
    claimed = _job(version=2, lease_token="lease-abc")
    advanced = _job(version=3, state=ImportJobState.WAITING_REEL)
    try:
        with (
            patch(
                "backend.app.api.routes.import_jobs.get_job_for_owner",
                return_value=job,
            ),
            patch(
                "backend.app.api.routes.import_jobs.claim_job_lease",
                return_value=claimed,
            ) as claim,
            patch(
                "backend.app.api.routes.import_jobs.advance_instagram_job",
                new=AsyncMock(return_value=advanced),
            ) as advance,
        ):
            response = client.post("/api/extract/jobs/job-1/advance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    body = response.json()
    assert body["kind"] == "pending"
    assert body["job_id"] == "job-1"
    assert body["state"] == "waiting_reel"
    assert body["retry_after_ms"] >= 7000
    claim.assert_called_once_with("job-1", "admin@example.com", 1)
    advance.assert_awaited_once()
    assert advance.await_args.args[0] is claimed


def test_advance_returns_result_when_orchestration_reaches_a_terminal_state():
    _authenticated()
    job = _job(version=1)
    claimed = _job(version=2, lease_token="lease-abc")
    succeeded = _job(
        version=3,
        state=ImportJobState.SUCCEEDED,
        normalized_result_json={
            "source_url": job.canonical_reel_url,
            "final_url": job.canonical_reel_url,
            "title": "Chia Pudding",
            "image_url": None,
            "recipes": [
                {"name": "Chia Pudding", "ingredients": ["1 cup chia"], "instructions": ["Mix."]}
            ],
            "database_saved": True,
            "database_message": "Recipe saved to your collection.",
            "parse_status": "recipe",
        },
    )
    try:
        with (
            patch(
                "backend.app.api.routes.import_jobs.get_job_for_owner",
                return_value=job,
            ),
            patch(
                "backend.app.api.routes.import_jobs.claim_job_lease",
                return_value=claimed,
            ),
            patch(
                "backend.app.api.routes.import_jobs.advance_instagram_job",
                new=AsyncMock(return_value=succeeded),
            ),
        ):
            response = client.post("/api/extract/jobs/job-1/advance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "result"
    assert body["result"]["recipes"][0]["name"] == "Chia Pudding"


def test_advance_falls_back_to_pending_when_orchestration_raises_unexpectedly():
    _authenticated()
    job = _job(version=1)
    claimed = _job(version=2, lease_token="lease-abc")
    try:
        with (
            patch(
                "backend.app.api.routes.import_jobs.get_job_for_owner",
                return_value=job,
            ),
            patch(
                "backend.app.api.routes.import_jobs.claim_job_lease",
                return_value=claimed,
            ),
            patch(
                "backend.app.api.routes.import_jobs.advance_instagram_job",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            response = client.post("/api/extract/jobs/job-1/advance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    body = response.json()
    assert body["kind"] == "pending"
    assert body["job_id"] == "job-1"


def test_advance_returns_pending_snapshot_when_lease_is_busy():
    _authenticated()
    job = _job(version=1)
    try:
        with (
            patch(
                "backend.app.api.routes.import_jobs.get_job_for_owner",
                return_value=job,
            ),
            patch(
                "backend.app.api.routes.import_jobs.claim_job_lease",
                return_value=None,
            ),
            patch(
                "backend.app.api.routes.import_jobs.advance_instagram_job"
            ) as advance,
        ):
            response = client.post("/api/extract/jobs/job-1/advance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    body = response.json()
    assert body["kind"] == "pending"
    assert body["state"] == "waiting_reel"
    advance.assert_not_called()


def test_advance_returns_pending_snapshot_early_without_claiming_a_lease():
    _authenticated()
    job = _job(next_advance_at=datetime.now(timezone.utc) + timedelta(seconds=30))
    try:
        with (
            patch(
                "backend.app.api.routes.import_jobs.get_job_for_owner",
                return_value=job,
            ),
            patch(
                "backend.app.api.routes.import_jobs.claim_job_lease"
            ) as claim,
            patch(
                "backend.app.api.routes.import_jobs.advance_instagram_job"
            ) as advance,
        ):
            response = client.post("/api/extract/jobs/job-1/advance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    body = response.json()
    assert body["kind"] == "pending"
    assert body["retry_after_ms"] >= 7000
    claim.assert_not_called()
    advance.assert_not_called()


def test_advance_returns_503_when_job_lookup_storage_unavailable():
    _authenticated()
    try:
        with patch(
            "backend.app.api.routes.import_jobs.get_job_for_owner",
            side_effect=ImportJobStorageError("down"),
        ):
            response = client.post("/api/extract/jobs/job-1/advance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503


def test_advance_returns_503_when_lease_claim_storage_unavailable():
    _authenticated()
    job = _job()
    try:
        with (
            patch(
                "backend.app.api.routes.import_jobs.get_job_for_owner",
                return_value=job,
            ),
            patch(
                "backend.app.api.routes.import_jobs.claim_job_lease",
                side_effect=ImportJobStorageError("down"),
            ),
        ):
            response = client.post("/api/extract/jobs/job-1/advance")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503


def test_advance_requires_authentication():
    response = client.post("/api/extract/jobs/job-1/advance")

    assert response.status_code == 401
