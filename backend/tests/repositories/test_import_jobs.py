from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.repositories.import_jobs import (
    ImportJobStorageError,
    checkpoint_job,
    claim_job_lease,
    create_or_reuse_job,
    delete_expired_terminal_jobs,
    find_existing_recipe_by_canonical_url,
    get_job_for_owner,
    reconcile_provider_admission,
    release_provider_admission,
    reserve_provider_admission,
    terminalize_stale_jobs,
)


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeRpcCall:
    def __init__(self, data, error):
        self._data = data
        self._error = error

    def execute(self):
        if self._error is not None:
            raise self._error
        return _FakeResponse(self._data)


class _FakeTableQuery:
    def __init__(self, data, error):
        self._data = data
        self._error = error
        self.filters: list[tuple[str, object]] = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self._error is not None:
            raise self._error
        return _FakeResponse(self._data)


class _FakeClient:
    def __init__(self):
        self.rpc_calls: list[tuple[str, dict]] = []
        self.table_calls: list[str] = []
        self._rpc_responses: dict[str, tuple[object, Exception | None]] = {}
        self._table_responses: dict[str, tuple[object, Exception | None]] = {}
        self.last_table_query: _FakeTableQuery | None = None

    def set_rpc(self, fn_name, data=None, error=None):
        self._rpc_responses[fn_name] = (data, error)

    def set_table(self, table_name, data=None, error=None):
        self._table_responses[table_name] = (data, error)

    def rpc(self, fn_name, params):
        self.rpc_calls.append((fn_name, params))
        data, error = self._rpc_responses.get(fn_name, ([], None))
        return _FakeRpcCall(data, error)

    def table(self, table_name):
        self.table_calls.append(table_name)
        data, error = self._table_responses.get(table_name, ([], None))
        query = _FakeTableQuery(data, error)
        self.last_table_query = query
        return query


def _job_row(**overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": "job-1",
        "owner_email": "admin@example.com",
        "canonical_reel_url": "https://www.instagram.com/reel/abc123/",
        "state": "queued",
        "version": 0,
        "lease_token": None,
        "lease_expires_at": None,
        "next_advance_at": now,
        "stale_deadline": now,
        "reel_run_id": None,
        "reel_dataset_id": None,
        "profile_run_id": None,
        "profile_dataset_id": None,
        "candidate_name": None,
        "normalized_result_json": None,
        "linked_recipe_url": None,
        "recipe_id": None,
        "error_code": None,
        "created_at": now,
        "updated_at": now,
    }
    row.update(overrides)
    return row


def _patched(client):
    return (
        patch("app.repositories.import_jobs.get_settings"),
        patch(
            "app.repositories.import_jobs.get_supabase_client", return_value=client
        ),
    )


# --- create_or_reuse_job -----------------------------------------------------


def test_create_or_reuse_job_returns_reused_outcome():
    client = _FakeClient()
    client.set_rpc(
        "create_or_reuse_instagram_import_job",
        data=[{**_job_row(), "outcome": "reused"}],
    )

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        outcome = create_or_reuse_job("admin@example.com", "https://www.instagram.com/reel/abc123/")

    assert outcome.outcome == "reused"
    assert outcome.job is not None
    assert outcome.job.id == "job-1"
    fn_name, params = client.rpc_calls[0]
    assert fn_name == "create_or_reuse_instagram_import_job"
    assert params["p_owner_email"] == "admin@example.com"
    assert params["p_canonical_reel_url"] == "https://www.instagram.com/reel/abc123/"


def test_create_or_reuse_job_returns_created_outcome():
    client = _FakeClient()
    client.set_rpc(
        "create_or_reuse_instagram_import_job",
        data=[{**_job_row(), "outcome": "created"}],
    )

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        outcome = create_or_reuse_job("admin@example.com", "https://www.instagram.com/reel/abc123/")

    assert outcome.outcome == "created"
    assert outcome.job is not None


@pytest.mark.parametrize(
    ("exception_message", "expected_outcome"),
    [
        ("owner_active_job_ceiling", "owner_ceiling"),
        ("global_active_job_ceiling", "global_ceiling"),
    ],
)
def test_create_or_reuse_job_maps_ceiling_exceptions(exception_message, expected_outcome):
    client = _FakeClient()
    client.set_rpc(
        "create_or_reuse_instagram_import_job", error=RuntimeError(exception_message)
    )

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        outcome = create_or_reuse_job("admin@example.com", "https://www.instagram.com/reel/abc123/")

    assert outcome.outcome == expected_outcome
    assert outcome.job is None


def test_create_or_reuse_job_raises_storage_error_on_unrelated_failure():
    client = _FakeClient()
    client.set_rpc("create_or_reuse_instagram_import_job", error=RuntimeError("connection reset"))

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        with pytest.raises(ImportJobStorageError):
            create_or_reuse_job("admin@example.com", "https://www.instagram.com/reel/abc123/")


def test_create_or_reuse_job_raises_when_supabase_not_configured():
    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=None
    ):
        with pytest.raises(ImportJobStorageError):
            create_or_reuse_job("admin@example.com", "https://www.instagram.com/reel/abc123/")


# --- get_job_for_owner --------------------------------------------------------


def test_get_job_for_owner_returns_none_when_no_row_matches():
    client = _FakeClient()
    client.set_table("instagram_import_jobs", data=[])

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        job = get_job_for_owner("job-1", "wrong-owner@example.com")

    assert job is None
    assert client.last_table_query.filters == [
        ("id", "job-1"),
        ("owner_email", "wrong-owner@example.com"),
    ]


def test_get_job_for_owner_returns_record_when_found():
    client = _FakeClient()
    client.set_table("instagram_import_jobs", data=[_job_row()])

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        job = get_job_for_owner("job-1", "admin@example.com")

    assert job is not None
    assert job.id == "job-1"


def test_get_job_for_owner_raises_storage_error_on_failure():
    client = _FakeClient()
    client.set_table("instagram_import_jobs", error=RuntimeError("boom"))

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        with pytest.raises(ImportJobStorageError):
            get_job_for_owner("job-1", "admin@example.com")


# --- claim_job_lease -----------------------------------------------------------


def test_claim_job_lease_returns_none_when_busy_or_version_mismatched():
    client = _FakeClient()
    client.set_rpc("claim_instagram_import_job_lease", data=[])

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        job = claim_job_lease("job-1", "admin@example.com", 0)

    assert job is None


def test_claim_job_lease_returns_record_and_sends_expected_params():
    client = _FakeClient()
    client.set_rpc(
        "claim_instagram_import_job_lease",
        data=[{**_job_row(), "lease_token": "lease-abc", "version": 1}],
    )

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        job = claim_job_lease("job-1", "admin@example.com", 0, lease_seconds=60)

    assert job is not None
    assert job.lease_token == "lease-abc"
    fn_name, params = client.rpc_calls[0]
    assert fn_name == "claim_instagram_import_job_lease"
    assert params == {
        "p_id": "job-1",
        "p_owner_email": "admin@example.com",
        "p_expected_version": 0,
        "p_lease_seconds": 60,
    }


# --- checkpoint_job --------------------------------------------------------------


def test_checkpoint_job_returns_none_when_lease_or_version_mismatched():
    client = _FakeClient()
    client.set_rpc("checkpoint_instagram_import_job", data=[])

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        job = checkpoint_job(
            "job-1", "lease-abc", 1, state="waiting_reel"
        )

    assert job is None


def test_checkpoint_job_forwards_all_fields_and_release_flag():
    client = _FakeClient()
    client.set_rpc(
        "checkpoint_instagram_import_job",
        data=[{**_job_row(), "state": "saving", "version": 3}],
    )

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        job = checkpoint_job(
            "job-1",
            "lease-abc",
            2,
            state="saving",
            reel_run_id="run-1",
            candidate_name="Miso Salmon Rice",
            next_advance_seconds=7,
            release_lease=True,
        )

    assert job is not None
    assert job.state.value == "saving"
    fn_name, params = client.rpc_calls[0]
    assert fn_name == "checkpoint_instagram_import_job"
    assert params["p_id"] == "job-1"
    assert params["p_lease_token"] == "lease-abc"
    assert params["p_expected_version"] == 2
    assert params["p_state"] == "saving"
    assert params["p_reel_run_id"] == "run-1"
    assert params["p_candidate_name"] == "Miso Salmon Rice"
    assert params["p_release_lease"] is True
    assert params["p_profile_run_id"] is None


# --- provider admission -----------------------------------------------------------


def test_reserve_provider_admission_true_when_reserved_false_when_busy():
    client = _FakeClient()
    client.set_rpc("reserve_instagram_provider_admission", data=[{"id": True}])

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        assert reserve_provider_admission("job-1", "reel", 0.0073) is True

    client.set_rpc("reserve_instagram_provider_admission", data=[])
    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        assert reserve_provider_admission("job-2", "reel", 0.0073) is False

    fn_name, params = client.rpc_calls[0]
    assert fn_name == "reserve_instagram_provider_admission"
    assert params == {"p_job_id": "job-1", "p_run_kind": "reel", "p_max_charge_usd": 0.0073}


def test_release_provider_admission_true_when_this_job_held_the_slot():
    client = _FakeClient()
    client.set_rpc("release_instagram_provider_admission", data=[{"id": True}])

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        assert release_provider_admission("job-1") is True

    fn_name, params = client.rpc_calls[0]
    assert fn_name == "release_instagram_provider_admission"
    assert params == {"p_job_id": "job-1"}


def test_provider_admission_raises_storage_error_on_failure():
    client = _FakeClient()
    client.set_rpc("reserve_instagram_provider_admission", error=RuntimeError("boom"))

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        with pytest.raises(ImportJobStorageError):
            reserve_provider_admission("job-1", "reel", 0.0073)


# --- cleanup / reconciliation ------------------------------------------------------


def test_terminalize_stale_jobs_dry_run_defaults_and_maps_rows():
    client = _FakeClient()
    client.set_rpc(
        "terminalize_stale_instagram_import_jobs",
        data=[{**_job_row(), "state": "failed", "error_code": "job_stalled"}],
    )

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        jobs = terminalize_stale_jobs()

    assert len(jobs) == 1
    assert jobs[0].state.value == "failed"
    fn_name, params = client.rpc_calls[0]
    assert params == {"p_error_code": "job_stalled", "p_dry_run": True}


def test_reconcile_provider_admission_forwards_dry_run():
    client = _FakeClient()
    client.set_rpc("reconcile_instagram_provider_admission", data=[{"id": True}])

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        rows = reconcile_provider_admission(dry_run=False)

    assert rows == [{"id": True}]
    fn_name, params = client.rpc_calls[0]
    # No age gate by default, so the manual ops sweep keeps its old semantics.
    assert params == {"p_dry_run": False, "p_min_age_seconds": None}


def test_reconcile_provider_admission_forwards_min_age_seconds():
    client = _FakeClient()
    client.set_rpc("reconcile_instagram_provider_admission", data=[{"id": True}])

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        reconcile_provider_admission(dry_run=False, min_age_seconds=180)

    _fn_name, params = client.rpc_calls[0]
    assert params == {"p_dry_run": False, "p_min_age_seconds": 180}


def test_delete_expired_terminal_jobs_defaults_to_dry_run():
    client = _FakeClient()
    client.set_rpc(
        "delete_expired_instagram_import_jobs",
        data=[{**_job_row(), "state": "succeeded"}],
    )

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        jobs = delete_expired_terminal_jobs()

    assert len(jobs) == 1
    fn_name, params = client.rpc_calls[0]
    assert params["p_dry_run"] is True


# --- existing-recipe preflight -------------------------------------------------------


def test_find_existing_recipe_by_canonical_url_returns_row_or_none():
    client = _FakeClient()
    client.set_table("recipe_imports", data=[{"id": "recipe-1"}])

    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        record = find_existing_recipe_by_canonical_url("https://www.instagram.com/reel/abc123/")

    assert record == {"id": "recipe-1"}
    assert client.last_table_query.filters == [
        ("final_url", "https://www.instagram.com/reel/abc123/")
    ]

    client.set_table("recipe_imports", data=[])
    with patch("app.repositories.import_jobs.get_settings"), patch(
        "app.repositories.import_jobs.get_supabase_client", return_value=client
    ):
        assert find_existing_recipe_by_canonical_url("https://www.instagram.com/reel/xyz/") is None
