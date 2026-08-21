from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from ..auth import AuthenticatedAdmin, require_admin_user
from ...core.rate_limit import limiter
from ...repositories.import_jobs import (
    ImportJobStorageError,
    create_or_reuse_job,
    find_existing_recipe_by_canonical_url,
)
from ...repositories.recipe_imports import save_recipe_import
from ...schemas.extract import ExtractRequest, ExtractResponse, NormalizedRecipe
from ...schemas.import_jobs import ResultImportResponse, pending_response
from ...services.extraction_types import ParseStatus
from ...services.extractor import extract_recipes_from_url
from ...services.instagram.urls import (
    InstagramUrlError,
    is_instagram_url,
    parse_instagram_reel_url,
)


router = APIRouter(prefix="/api", tags=["extract"])
GENERIC_SAVE_SUCCESS_MESSAGE = "Recipe saved to your collection."


def _sanitize_database_message(database_saved: bool, message: str) -> str:
    if database_saved and "Supabase table" in message:
        return GENERIC_SAVE_SUCCESS_MESSAGE

    return message


def _existing_recipe_response(record: dict) -> ExtractResponse:
    recipes = [
        NormalizedRecipe.model_validate(item)
        for item in record.get("recipes_json") or []
    ]
    return ExtractResponse(
        source_url=record["submitted_url"],
        final_url=record["final_url"],
        title=record.get("page_title"),
        image_url=record.get("image_url"),
        recipes=recipes,
        database_saved=True,
        database_message=GENERIC_SAVE_SUCCESS_MESSAGE,
        parse_status="recipe",
        linked_recipe_url=record.get("linked_recipe_url"),
    )


async def _handle_instagram_extract(
    url: str, admin: AuthenticatedAdmin
) -> JSONResponse:
    try:
        identity = parse_instagram_reel_url(url)
    except InstagramUrlError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    try:
        existing = find_existing_recipe_by_canonical_url(identity.canonical_url)
    except ImportJobStorageError as error:
        raise HTTPException(
            status_code=503, detail="Job storage is unavailable"
        ) from error

    if existing is not None:
        envelope = ResultImportResponse(result=_existing_recipe_response(existing))
        return JSONResponse(content=jsonable_encoder(envelope), status_code=200)

    try:
        outcome = create_or_reuse_job(admin.email, identity.canonical_url)
    except ImportJobStorageError as error:
        raise HTTPException(
            status_code=503, detail="Job storage is unavailable"
        ) from error

    if outcome.outcome in {"owner_ceiling", "global_ceiling"}:
        raise HTTPException(
            status_code=429,
            detail="Too many active Instagram imports right now. Wait for one to finish.",
        )
    if outcome.job is None:
        raise HTTPException(status_code=503, detail="Job storage is unavailable")

    envelope = pending_response(outcome.job, now=datetime.now(timezone.utc))
    return JSONResponse(content=jsonable_encoder(envelope), status_code=202)


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/extract", response_model=ExtractResponse)
@limiter.limit("10/minute")
async def extract_ld_json(
    request: Request,
    payload: ExtractRequest,
    admin: AuthenticatedAdmin = Depends(require_admin_user),
):
    if is_instagram_url(payload.url):
        return await _handle_instagram_extract(payload.url, admin)

    result = await extract_recipes_from_url(payload.url)

    if result.parse_status == ParseStatus.NOT_RECIPE:
        return ExtractResponse(
            source_url=result.source_url,
            final_url=result.final_url,
            title=result.title,
            image_url=result.image_url,
            recipes=[],
            database_saved=False,
            database_message="Skipped — not a recipe.",
            parse_status="not_recipe",
            parse_reason=result.parse_reason,
        )

    if result.recipes:
        thumbnail_candidate = (
            result.tiktok_thumbnail_url
            if isinstance(result.tiktok_thumbnail_url, str)
            else None
        )
        save_result = await save_recipe_import(
            submitted_url=result.source_url,
            final_url=result.final_url,
            title=result.title,
            recipes=result.recipes,
            image_url=result.image_url,
            tiktok_thumbnail_url=thumbnail_candidate,
            access_token=admin.access_token,
        )
        database_saved = save_result.saved
        database_message = _sanitize_database_message(
            save_result.saved,
            save_result.message,
        )
        response_image_url = save_result.image_url
    else:
        database_saved = False
        response_image_url = result.image_url
        if result.recipe_node_count > 0:
            database_message = (
                "Nothing was saved because recipe objects were found on that page, "
                "but they did not include enough data to extract a complete recipe."
            )
        else:
            database_message = (
                "Nothing was saved because no Recipe objects were found on that page."
            )

    return ExtractResponse(
        source_url=result.source_url,
        final_url=result.final_url,
        title=result.title,
        image_url=response_image_url,
        recipes=result.recipes,
        database_saved=database_saved,
        database_message=database_message,
        parse_status="recipe",
    )
