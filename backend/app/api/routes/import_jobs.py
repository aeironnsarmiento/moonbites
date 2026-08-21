import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..auth import AuthenticatedAdmin, require_admin_user
from ...core.config import get_settings
from ...repositories.import_jobs import ImportJobStorageError, claim_job_lease, get_job_for_owner
from ...schemas.import_jobs import TERMINAL_JOB_STATES, pending_response, terminal_response
from ...services.import_deadline import Deadline
from ...services.instagram.import_job import advance_instagram_job


router = APIRouter(prefix="/api/extract/jobs", tags=["import-jobs"])
logger = logging.getLogger(__name__)


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

    settings = get_settings()
    deadline = Deadline.start(settings.instagram_request_deadline_seconds)
    try:
        updated = await advance_instagram_job(claimed, deadline=deadline)
    except Exception:
        # A crash mid-advance leaves the job in whatever intent state it last
        # checkpointed; the next advance call detects and terminalizes that
        # state as ambiguous rather than repeating the external operation, so
        # the safe response here is just the current snapshot.
        logger.exception("Instagram job advance failed unexpectedly for %s", claimed.id)
        return JSONResponse(
            content=jsonable_encoder(
                pending_response(claimed, now=datetime.now(timezone.utc))
            ),
            status_code=202,
        )

    if updated.state in TERMINAL_JOB_STATES:
        return JSONResponse(
            content=jsonable_encoder(terminal_response(updated)), status_code=200
        )

    return JSONResponse(
        content=jsonable_encoder(
            pending_response(updated, now=datetime.now(timezone.utc))
        ),
        status_code=202,
    )
