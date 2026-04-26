from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import AuthenticatedAdmin, require_admin_user
from ...repositories.recipe_imports import (
    get_recipe_import,
    list_cuisine_facets,
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
    CreateManualRecipeRequest,
    CuisineFacetsResponse,
    PaginatedRecipeImportsResponse,
    RecipeImportRecord,
    RecipeSortOption,
    UpdateImageRequest,
    UpdateRecipeMetadataRequest,
    UpdateRecipeOverridesRequest,
    UpdateServingsRequest,
    UpdateTimesCookedRequest,
)


router = APIRouter(prefix="/api", tags=["recipes"])


@router.post("/recipes/manual", response_model=RecipeImportRecord)
async def create_manual_recipe(
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
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error


@router.get("/recipes", response_model=PaginatedRecipeImportsResponse)
async def get_saved_recipes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    limit: Optional[int] = Query(default=None, ge=1, le=50),
    sort: RecipeSortOption = Query(default=RecipeSortOption.recent),
    cuisine: Optional[str] = Query(default=None),
    favorite: Optional[bool] = Query(default=None),
) -> PaginatedRecipeImportsResponse:
    try:
        return list_recipe_imports(
            page=page,
            page_size=limit or page_size,
            sort=sort,
            cuisine=cuisine,
            favorite=favorite,
        )
    except RuntimeError as error:
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error


@router.get("/recipes/cuisines", response_model=CuisineFacetsResponse)
async def get_recipe_cuisines() -> CuisineFacetsResponse:
    try:
        return list_cuisine_facets()
    except RuntimeError as error:
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error


@router.get("/recipes/{recipe_import_id}", response_model=RecipeImportRecord)
async def get_saved_recipe(recipe_import_id: str) -> RecipeImportRecord:
    try:
        record = get_recipe_import(recipe_import_id)
    except RuntimeError as error:
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.patch(
    "/recipes/{recipe_import_id}/times-cooked", response_model=RecipeImportRecord
)
async def patch_times_cooked(
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
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.patch("/recipes/{recipe_import_id}/favorite", response_model=RecipeImportRecord)
async def patch_favorite(
    recipe_import_id: str,
    admin: AuthenticatedAdmin = Depends(require_admin_user),
) -> RecipeImportRecord:
    try:
        record = toggle_favorite(recipe_import_id, access_token=admin.access_token)
    except RuntimeError as error:
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.patch("/recipes/{recipe_import_id}/servings", response_model=RecipeImportRecord)
async def patch_servings(
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
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.patch("/recipes/{recipe_import_id}/image", response_model=RecipeImportRecord)
async def patch_image(
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
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.patch("/recipes/{recipe_import_id}/metadata", response_model=RecipeImportRecord)
async def patch_metadata(
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
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.patch(
    "/recipes/{recipe_import_id}/overrides", response_model=RecipeImportRecord
)
async def patch_recipe_overrides(
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
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record
