from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..clients.supabase_client import get_supabase_client
from ..core.config import get_settings
from ..schemas.import_jobs import ImportJobRecord


DEFAULT_STALE_WINDOW_SECONDS = 1800
DEFAULT_LEASE_SECONDS = 60
DEFAULT_MAX_PER_OWNER = 3
DEFAULT_MAX_GLOBAL = 5
DEFAULT_RETENTION_SECONDS = 24 * 60 * 60
DEFAULT_NEXT_ADVANCE_SECONDS = 7


class ImportJobStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class JobCreationOutcome:
    job: Optional[ImportJobRecord]
    outcome: str


def _client():
    settings = get_settings()
    client = get_supabase_client(settings)
    if client is None:
        raise ImportJobStorageError("Supabase is not configured")
    return client


def _row_to_record(row: dict) -> ImportJobRecord:
    row = dict(row)
    row.pop("outcome", None)
    return ImportJobRecord.model_validate(row)


def create_or_reuse_job(
    owner_email: str,
    canonical_reel_url: str,
    *,
    stale_window_seconds: int = DEFAULT_STALE_WINDOW_SECONDS,
    max_per_owner: int = DEFAULT_MAX_PER_OWNER,
    max_global: int = DEFAULT_MAX_GLOBAL,
) -> JobCreationOutcome:
    client = _client()
    try:
        response = client.rpc(
            "create_or_reuse_instagram_import_job",
            {
                "p_owner_email": owner_email,
                "p_canonical_reel_url": canonical_reel_url,
                "p_stale_window_seconds": stale_window_seconds,
                "p_max_per_owner": max_per_owner,
                "p_max_global": max_global,
            },
        ).execute()
    except Exception as error:
        message = str(error)
        if "owner_active_job_ceiling" in message:
            return JobCreationOutcome(job=None, outcome="owner_ceiling")
        if "global_active_job_ceiling" in message:
            return JobCreationOutcome(job=None, outcome="global_ceiling")
        raise ImportJobStorageError("Supabase job creation failed") from error

    rows = response.data or []
    if not rows:
        raise ImportJobStorageError("Supabase job creation returned no row")
    row = rows[0]
    return JobCreationOutcome(
        job=_row_to_record(row), outcome=row.get("outcome") or "created"
    )


def get_job_for_owner(job_id: str, owner_email: str) -> Optional[ImportJobRecord]:
    client = _client()
    try:
        response = (
            client.table("instagram_import_jobs")
            .select("*")
            .eq("id", job_id)
            .eq("owner_email", owner_email)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise ImportJobStorageError("Supabase job lookup failed") from error

    rows = response.data or []
    if not rows:
        return None
    return _row_to_record(rows[0])


def claim_job_lease(
    job_id: str,
    owner_email: str,
    expected_version: int,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> Optional[ImportJobRecord]:
    client = _client()
    try:
        response = client.rpc(
            "claim_instagram_import_job_lease",
            {
                "p_id": job_id,
                "p_owner_email": owner_email,
                "p_expected_version": expected_version,
                "p_lease_seconds": lease_seconds,
            },
        ).execute()
    except Exception as error:
        raise ImportJobStorageError("Supabase lease claim failed") from error

    rows = response.data or []
    if not rows:
        return None
    return _row_to_record(rows[0])


def checkpoint_job(
    job_id: str,
    lease_token: str,
    expected_version: int,
    *,
    state: str,
    reel_run_id: Optional[str] = None,
    reel_dataset_id: Optional[str] = None,
    profile_run_id: Optional[str] = None,
    profile_dataset_id: Optional[str] = None,
    candidate_name: Optional[str] = None,
    normalized_result_json: Optional[dict[str, Any]] = None,
    linked_recipe_url: Optional[str] = None,
    recipe_id: Optional[str] = None,
    error_code: Optional[str] = None,
    next_advance_seconds: int = 0,
    stale_window_seconds: Optional[int] = None,
    release_lease: bool = False,
) -> Optional[ImportJobRecord]:
    client = _client()
    try:
        response = client.rpc(
            "checkpoint_instagram_import_job",
            {
                "p_id": job_id,
                "p_lease_token": lease_token,
                "p_expected_version": expected_version,
                "p_state": state,
                "p_reel_run_id": reel_run_id,
                "p_reel_dataset_id": reel_dataset_id,
                "p_profile_run_id": profile_run_id,
                "p_profile_dataset_id": profile_dataset_id,
                "p_candidate_name": candidate_name,
                "p_normalized_result_json": normalized_result_json,
                "p_linked_recipe_url": linked_recipe_url,
                "p_recipe_id": recipe_id,
                "p_error_code": error_code,
                "p_next_advance_seconds": next_advance_seconds,
                "p_stale_window_seconds": stale_window_seconds,
                "p_release_lease": release_lease,
            },
        ).execute()
    except Exception as error:
        raise ImportJobStorageError("Supabase job checkpoint failed") from error

    rows = response.data or []
    if not rows:
        return None
    return _row_to_record(rows[0])


def reserve_provider_admission(
    job_id: str, run_kind: str, max_charge_usd: float
) -> bool:
    client = _client()
    try:
        response = client.rpc(
            "reserve_instagram_provider_admission",
            {
                "p_job_id": job_id,
                "p_run_kind": run_kind,
                "p_max_charge_usd": max_charge_usd,
            },
        ).execute()
    except Exception as error:
        raise ImportJobStorageError(
            "Supabase provider admission reserve failed"
        ) from error
    return bool(response.data)


def release_provider_admission(job_id: str) -> bool:
    client = _client()
    try:
        response = client.rpc(
            "release_instagram_provider_admission", {"p_job_id": job_id}
        ).execute()
    except Exception as error:
        raise ImportJobStorageError(
            "Supabase provider admission release failed"
        ) from error
    return bool(response.data)


def reconcile_provider_admission(
    *, dry_run: bool = True, min_age_seconds: Optional[int] = None
) -> list[dict]:
    """Clear an admission slot whose holder job is terminal or gone.

    `min_age_seconds` gates the reclaim on how long the slot has been held,
    so an ambiguous holder is only reclaimed once its Actor run could no
    longer be in flight. `None` (the ops-sweep default) applies no age gate.
    """
    client = _client()
    try:
        response = client.rpc(
            "reconcile_instagram_provider_admission",
            {"p_dry_run": dry_run, "p_min_age_seconds": min_age_seconds},
        ).execute()
    except Exception as error:
        raise ImportJobStorageError(
            "Supabase provider admission reconciliation failed"
        ) from error
    return response.data or []


def find_existing_recipe_by_canonical_url(canonical_url: str) -> Optional[dict]:
    client = _client()
    try:
        response = (
            client.table("recipe_imports")
            .select(
                "id, submitted_url, final_url, page_title, image_url, "
                "recipes_json, linked_recipe_url"
            )
            .eq("final_url", canonical_url)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise ImportJobStorageError("Supabase recipe lookup failed") from error
    rows = response.data or []
    return rows[0] if rows else None


def terminalize_stale_jobs(
    *, error_code: str = "job_stalled", dry_run: bool = True
) -> list[ImportJobRecord]:
    client = _client()
    try:
        response = client.rpc(
            "terminalize_stale_instagram_import_jobs",
            {"p_error_code": error_code, "p_dry_run": dry_run},
        ).execute()
    except Exception as error:
        raise ImportJobStorageError("Supabase stale terminalization failed") from error
    return [_row_to_record(row) for row in (response.data or [])]


def delete_expired_terminal_jobs(
    *, retention_seconds: int = DEFAULT_RETENTION_SECONDS, dry_run: bool = True
) -> list[ImportJobRecord]:
    client = _client()
    try:
        response = client.rpc(
            "delete_expired_instagram_import_jobs",
            {"p_retention_seconds": retention_seconds, "p_dry_run": dry_run},
        ).execute()
    except Exception as error:
        raise ImportJobStorageError("Supabase terminal job deletion failed") from error
    return [_row_to_record(row) for row in (response.data or [])]
