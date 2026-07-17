from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..auth import AuthenticatedAdmin, require_admin_user
from ...core.rate_limit import limiter
from ...repositories.recipe_imports import (
    RecipeWriteDeniedError,
    apply_display_titles,
    delete_recipe_import,
    get_recipe_import,
    list_cuisine_facets,
    list_highlighted_recipes,
    list_recipe_imports,
    save_manual_recipe,
    toggle_favorite,
    update_recipe_overrides,
    update_image_url,
    update_recipe_metadata,
    update_servings,
    update_times_cooked,
)
from ...schemas.extract import (
    ApplyTitleResult,
    ApplyTitlesRequest,
    ApplyTitlesResponse,
    CreateManualRecipeRequest,
    CuisineFacetsResponse,
    DeleteRecipeImportResponse,
    HighlightedRecipesResponse,
    PaginatedRecipeImportsResponse,
    RecipeImportRecord,
    RecipeSortOption,
    TitleCleanupPreviewRequest,
    TitleCleanupPreviewResponse,
    UpdateImageRequest,
    UpdateRecipeMetadataRequest,
    UpdateRecipeOverridesRequest,
    UpdateServingsRequest,
    UpdateTimesCookedRequest,
)
from ...services.title_cleanup import preview_title_cleanup


router = APIRouter(prefix="/api", tags=["recipes"])


def _raise_repository_http_error(error: RuntimeError) -> None:
    message = str(error)
    if isinstance(error, RecipeWriteDeniedError):
        status_code = 403
    else:
        status_code = 503 if "not configured" in message else 502

    raise HTTPException(status_code=status_code, detail=message) from error


@router.post("/recipes/manual", response_model=RecipeImportRecord)
@limiter.limit("30/minute")
async def create_manual_recipe(
    request: Request,
    payload: CreateManualRecipeRequest,
    admin: AuthenticatedAdmin = Depends(require_admin_user),
) -> RecipeImportRecord:
    try:
        return save_manual_recipe(
            payload.recipe,
            title=payload.title,
            access_token=admin.access_token,
        )
    except RuntimeError as error:
        _raise_repository_http_error(error)


@router.get("/recipes", response_model=PaginatedRecipeImportsResponse)
@limiter.limit("60/minute")
async def get_saved_recipes(
    request: Request,
    page: int = Query(default=1, ge=1, le=1_000_000),
    page_size: int = Query(default=10, ge=1, le=50),
    limit: Optional[int] = Query(default=None, ge=1, le=50),
    sort: RecipeSortOption = Query(default=RecipeSortOption.recent),
    cuisine: Optional[str] = Query(default=None),
    favorite: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None, min_length=2, max_length=100),
) -> PaginatedRecipeImportsResponse:
    stripped_search = (search or "").strip()
    try:
        return list_recipe_imports(
            page=page,
            page_size=limit or page_size,
            sort=sort,
            cuisine=cuisine,
            favorite=favorite,
            search=stripped_search if len(stripped_search) >= 2 else None,
        )
    except RuntimeError as error:
        _raise_repository_http_error(error)


@router.get("/recipes/cuisines", response_model=CuisineFacetsResponse)
@limiter.limit("60/minute")
async def get_recipe_cuisines(request: Request) -> CuisineFacetsResponse:
    try:
        return list_cuisine_facets()
    except RuntimeError as error:
        _raise_repository_http_error(error)


@router.get("/recipes/highlights", response_model=HighlightedRecipesResponse)
@limiter.limit("60/minute")
async def get_recipe_highlights(
    request: Request,
    recent_limit: int = Query(default=5, ge=1, le=20),
    favorite_limit: int = Query(default=4, ge=1, le=20),
) -> HighlightedRecipesResponse:
    try:
        return list_highlighted_recipes(
            recent_limit=recent_limit,
            favorite_limit=favorite_limit,
        )
    except RuntimeError as error:
        _raise_repository_http_error(error)


# POST rather than GET: both endpoints spend Gemini quota and write, so they
# must stay off any caching path. Declared above /recipes/{recipe_import_id}
# per the convention the literal cuisines/highlights routes follow.
@router.post("/recipes/titles/preview", response_model=TitleCleanupPreviewResponse)
@limiter.limit("30/minute")
async def post_title_cleanup_preview(
    request: Request,
    payload: TitleCleanupPreviewRequest,
    admin: AuthenticatedAdmin = Depends(require_admin_user),
) -> TitleCleanupPreviewResponse:
    try:
        return await preview_title_cleanup(cursor=payload.cursor, limit=payload.limit)
    except RuntimeError as error:
        _raise_repository_http_error(error)


@router.post("/recipes/titles/apply", response_model=ApplyTitlesResponse)
@limiter.limit("30/minute")
async def post_title_cleanup_apply(
    request: Request,
    payload: ApplyTitlesRequest,
    admin: AuthenticatedAdmin = Depends(require_admin_user),
) -> ApplyTitlesResponse:
    try:
        results = apply_display_titles(
            [(item.recipe_import_id, item.title) for item in payload.items],
            access_token=admin.access_token,
        )
    except RuntimeError as error:
        _raise_repository_http_error(error)

    return ApplyTitlesResponse(
        results=[
            ApplyTitleResult(
                recipe_import_id=result.recipe_import_id,
                status=result.status,
                reason=result.reason,
            )
            for result in results
        ],
        applied_count=sum(1 for result in results if result.status == "applied"),
    )


@router.get("/recipes/{recipe_import_id}", response_model=RecipeImportRecord)
@limiter.limit("60/minute")
async def get_saved_recipe(
    request: Request,
    recipe_import_id: str,
) -> RecipeImportRecord:
    try:
        record = get_recipe_import(recipe_import_id)
    except RuntimeError as error:
        _raise_repository_http_error(error)

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.delete("/recipes/{recipe_import_id}", response_model=DeleteRecipeImportResponse)
@limiter.limit("30/minute")
async def delete_saved_recipe(
    request: Request,
    recipe_import_id: str,
    admin: AuthenticatedAdmin = Depends(require_admin_user),
) -> DeleteRecipeImportResponse:
    try:
        deleted = delete_recipe_import(
            recipe_import_id,
            access_token=admin.access_token,
        )
    except RuntimeError as error:
        _raise_repository_http_error(error)

    if not deleted:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return DeleteRecipeImportResponse(id=recipe_import_id)


@router.patch(
    "/recipes/{recipe_import_id}/times-cooked", response_model=RecipeImportRecord
)
@limiter.limit("30/minute")
async def patch_times_cooked(
    request: Request,
    recipe_import_id: str,
    payload: UpdateTimesCookedRequest,
    admin: AuthenticatedAdmin = Depends(require_admin_user),
) -> RecipeImportRecord:
    if payload.delta not in {-1, 1}:
        raise HTTPException(status_code=400, detail="delta must be -1 or 1")

    try:
        record = update_times_cooked(
            recipe_import_id,
            payload.delta,
            access_token=admin.access_token,
        )
    except RuntimeError as error:
        _raise_repository_http_error(error)

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.patch("/recipes/{recipe_import_id}/favorite", response_model=RecipeImportRecord)
@limiter.limit("30/minute")
async def patch_favorite(
    request: Request,
    recipe_import_id: str,
    admin: AuthenticatedAdmin = Depends(require_admin_user),
) -> RecipeImportRecord:
    try:
        record = toggle_favorite(recipe_import_id, access_token=admin.access_token)
    except RuntimeError as error:
        _raise_repository_http_error(error)

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.patch("/recipes/{recipe_import_id}/servings", response_model=RecipeImportRecord)
@limiter.limit("30/minute")
async def patch_servings(
    request: Request,
    recipe_import_id: str,
    payload: UpdateServingsRequest,
    admin: AuthenticatedAdmin = Depends(require_admin_user),
) -> RecipeImportRecord:
    try:
        record = update_servings(
            recipe_import_id,
            payload.servings,
            access_token=admin.access_token,
        )
    except RuntimeError as error:
        _raise_repository_http_error(error)

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.patch("/recipes/{recipe_import_id}/image", response_model=RecipeImportRecord)
@limiter.limit("30/minute")
async def patch_image(
    request: Request,
    recipe_import_id: str,
    payload: UpdateImageRequest,
    admin: AuthenticatedAdmin = Depends(require_admin_user),
) -> RecipeImportRecord:
    try:
        record = update_image_url(
            recipe_import_id,
            payload.image_url,
            access_token=admin.access_token,
        )
    except RuntimeError as error:
        _raise_repository_http_error(error)

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.patch("/recipes/{recipe_import_id}/metadata", response_model=RecipeImportRecord)
@limiter.limit("30/minute")
async def patch_metadata(
    request: Request,
    recipe_import_id: str,
    payload: UpdateRecipeMetadataRequest,
    admin: AuthenticatedAdmin = Depends(require_admin_user),
) -> RecipeImportRecord:
    try:
        record = update_recipe_metadata(
            recipe_import_id,
            payload,
            access_token=admin.access_token,
        )
    except RuntimeError as error:
        _raise_repository_http_error(error)

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.patch(
    "/recipes/{recipe_import_id}/overrides", response_model=RecipeImportRecord
)
@limiter.limit("30/minute")
async def patch_recipe_overrides(
    request: Request,
    recipe_import_id: str,
    payload: UpdateRecipeOverridesRequest,
    admin: AuthenticatedAdmin = Depends(require_admin_user),
) -> RecipeImportRecord:
    try:
        record = update_recipe_overrides(
            recipe_import_id,
            payload.recipe_index,
            payload.overrides,
            access_token=admin.access_token,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        _raise_repository_http_error(error)

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record
