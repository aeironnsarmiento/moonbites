from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..auth import AuthenticatedAdmin, require_admin_user
from ...repositories.import_jobs import (
    DEFAULT_NEXT_ADVANCE_SECONDS,
    ImportJobStorageError,
    checkpoint_job,
    claim_job_lease,
    get_job_for_owner,
)
from ...schemas.import_jobs import TERMINAL_JOB_STATES, pending_response, terminal_response


router = APIRouter(prefix="/api/extract/jobs", tags=["import-jobs"])


@router.post("/{job_id}/advance")
async def advance_import_job(
    job_id: str, admin: AuthenticatedAdmin = Depends(require_admin_user)
) -> JSONResponse:
    try:
        job = get_job_for_owner(job_id, admin.email)
    except ImportJobStorageError as error:
        raise HTTPException(
            status_code=503, detail="Job storage is unavailable"
        ) from error

    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found")

    if job.state in TERMINAL_JOB_STATES:
        return JSONResponse(
            content=jsonable_encoder(terminal_response(job)), status_code=200
        )

    now = datetime.now(timezone.utc)
    if job.next_advance_at > now:
        return JSONResponse(
            content=jsonable_encoder(pending_response(job, now=now)), status_code=202
        )

    try:
        claimed = claim_job_lease(job.id, admin.email, job.version)
    except ImportJobStorageError as error:
        raise HTTPException(
            status_code=503, detail="Job storage is unavailable"
        ) from error

    if claimed is None or claimed.lease_token is None:
        return JSONResponse(
            content=jsonable_encoder(pending_response(job, now=datetime.now(timezone.utc))),
            status_code=202,
        )

    try:
        released = checkpoint_job(
            claimed.id,
            claimed.lease_token,
            claimed.version,
            state=claimed.state.value,
            next_advance_seconds=DEFAULT_NEXT_ADVANCE_SECONDS,
            release_lease=True,
        )
    except ImportJobStorageError as error:
        raise HTTPException(
            status_code=503, detail="Job storage is unavailable"
        ) from error

    snapshot = released or claimed
    return JSONResponse(
        content=jsonable_encoder(
            pending_response(snapshot, now=datetime.now(timezone.utc))
        ),
        status_code=202,
    )
