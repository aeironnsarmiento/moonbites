from fastapi import APIRouter, HTTPException, Query

from ...repositories.recipe_imports import (
    get_recipe_import,
    list_recipe_imports,
    save_manual_recipe,
    update_recipe_overrides,
    update_times_cooked,
)
from ...schemas.extract import (
    CreateManualRecipeRequest,
    PaginatedRecipeImportsResponse,
    RecipeImportRecord,
    UpdateRecipeOverridesRequest,
    UpdateTimesCookedRequest,
)


router = APIRouter(prefix="/api", tags=["recipes"])


@router.post("/recipes/manual", response_model=RecipeImportRecord)
async def create_manual_recipe(payload: CreateManualRecipeRequest) -> RecipeImportRecord:
    try:
        return save_manual_recipe(payload.recipe, title=payload.title)
    except RuntimeError as error:
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error


@router.get("/recipes", response_model=PaginatedRecipeImportsResponse)
async def get_saved_recipes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
) -> PaginatedRecipeImportsResponse:
    try:
        return list_recipe_imports(page=page, page_size=page_size)
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
    recipe_import_id: str, payload: UpdateTimesCookedRequest
) -> RecipeImportRecord:
    if payload.delta not in {-1, 1}:
        raise HTTPException(status_code=400, detail="delta must be -1 or 1")

    try:
        record = update_times_cooked(recipe_import_id, payload.delta)
    except RuntimeError as error:
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error

    if record is None:
        raise HTTPException(status_code=404, detail="Recipe import not found")

    return record


@router.patch("/recipes/{recipe_import_id}/overrides", response_model=RecipeImportRecord)
async def patch_recipe_overrides(
    recipe_import_id: str, payload: UpdateRecipeOverridesRequest
) -> RecipeImportRecord:
    try:
        record = update_recipe_overrides(
            recipe_import_id,
            payload.recipe_index,
            payload.overrides,
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
