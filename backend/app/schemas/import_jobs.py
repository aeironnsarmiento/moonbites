from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel

from .extract import ExtractResponse


class ImportJobState(str, Enum):
    QUEUED = "queued"
    STARTING_REEL = "starting_reel"
    WAITING_REEL = "waiting_reel"
    RESOLVING_REEL = "resolving_reel"
    PARSING_CAPTION = "parsing_caption"
    RESOLVING_RECIPE = "resolving_recipe"
    STARTING_PROFILE = "starting_profile"
    WAITING_PROFILE = "waiting_profile"
    RESOLVING_PROFILE = "resolving_profile"
    SAVING = "saving"
    SUCCEEDED = "succeeded"
    NOT_RECIPE = "not_recipe"
    FAILED = "failed"


TERMINAL_JOB_STATES = frozenset(
    {ImportJobState.SUCCEEDED, ImportJobState.NOT_RECIPE, ImportJobState.FAILED}
)


class ImportJobErrorCode(str, Enum):
    INSTAGRAM_UNAVAILABLE = "instagram_unavailable"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_INVALID_RESPONSE = "provider_invalid_response"
    RESOLUTION_TIMEOUT = "resolution_timeout"
    AMBIGUOUS_EXTERNAL_OPERATION = "ambiguous_external_operation"
    JOB_STALLED = "job_stalled"
    SAVE_FAILED = "save_failed"


ERROR_CODE_MESSAGES: dict[ImportJobErrorCode, str] = {
    ImportJobErrorCode.INSTAGRAM_UNAVAILABLE: "This Instagram Reel is unavailable.",
    ImportJobErrorCode.PROVIDER_UNAVAILABLE: "The Instagram provider is unavailable.",
    ImportJobErrorCode.PROVIDER_TIMEOUT: "The Instagram provider timed out.",
    ImportJobErrorCode.PROVIDER_INVALID_RESPONSE: (
        "The Instagram provider returned an invalid response."
    ),
    ImportJobErrorCode.RESOLUTION_TIMEOUT: (
        "The Reel or linked recipe took too long to resolve."
    ),
    ImportJobErrorCode.AMBIGUOUS_EXTERNAL_OPERATION: (
        "Moonbites stopped rather than risk running the external operation twice."
    ),
    ImportJobErrorCode.JOB_STALLED: "This import did not finish in time.",
    ImportJobErrorCode.SAVE_FAILED: "The recipe was found but could not be saved safely.",
}


class ImportJobRecord(BaseModel):
    id: str
    owner_email: str
    canonical_reel_url: str
    state: ImportJobState
    version: int
    lease_token: Optional[str] = None
    lease_expires_at: Optional[datetime] = None
    next_advance_at: datetime
    stale_deadline: datetime
    reel_run_id: Optional[str] = None
    reel_dataset_id: Optional[str] = None
    profile_run_id: Optional[str] = None
    profile_dataset_id: Optional[str] = None
    candidate_name: Optional[str] = None
    normalized_result_json: Optional[dict] = None
    linked_recipe_url: Optional[str] = None
    recipe_id: Optional[str] = None
    error_code: Optional[ImportJobErrorCode] = None
    created_at: datetime
    updated_at: datetime


class PendingImportResponse(BaseModel):
    kind: Literal["pending"] = "pending"
    job_id: str
    state: ImportJobState
    retry_after_ms: int


class ResultImportResponse(BaseModel):
    kind: Literal["result"] = "result"
    result: ExtractResponse


class FailedImportResponse(BaseModel):
    kind: Literal["failed"] = "failed"
    job_id: str
    error_code: ImportJobErrorCode
    message: str


ImportJobResponse = Union[PendingImportResponse, ResultImportResponse, FailedImportResponse]


MIN_RETRY_AFTER_MS = 7000


def retry_after_ms(job: ImportJobRecord, *, now: datetime) -> int:
    delta_ms = int((job.next_advance_at - now).total_seconds() * 1000)
    return max(MIN_RETRY_AFTER_MS, delta_ms)


def pending_response(job: ImportJobRecord, *, now: datetime) -> PendingImportResponse:
    return PendingImportResponse(
        job_id=job.id, state=job.state, retry_after_ms=retry_after_ms(job, now=now)
    )


def failed_response(job: ImportJobRecord) -> FailedImportResponse:
    code = job.error_code or ImportJobErrorCode.PROVIDER_UNAVAILABLE
    return FailedImportResponse(
        job_id=job.id, error_code=code, message=ERROR_CODE_MESSAGES[code]
    )


def result_response(job: ImportJobRecord) -> ResultImportResponse:
    payload = job.normalized_result_json or {}
    return ResultImportResponse(result=ExtractResponse.model_validate(payload))


def terminal_response(job: ImportJobRecord) -> Union[ResultImportResponse, FailedImportResponse]:
    if job.state == ImportJobState.FAILED:
        return failed_response(job)
    return result_response(job)
