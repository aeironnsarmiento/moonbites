from fastapi import APIRouter, HTTPException, Query

from ...repositories.recipe_imports import get_recipe_import, list_recipe_imports
from ...schemas.extract import PaginatedRecipeImportsResponse, RecipeImportRecord


router = APIRouter(prefix="/api", tags=["recipes"])


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