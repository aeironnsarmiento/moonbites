from fastapi import APIRouter

from backend.app.repositories.recipe_imports import save_recipe_import
from backend.app.schemas.extract import ExtractRequest, ExtractResponse
from backend.app.services.extractor import extract_recipes_from_url


router = APIRouter(prefix="/api", tags=["extract"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/extract", response_model=ExtractResponse)
async def extract_ld_json(payload: ExtractRequest) -> ExtractResponse:
    result = await extract_recipes_from_url(payload.url)
    database_saved, database_message = save_recipe_import(
        submitted_url=result.source_url,
        final_url=result.final_url,
        title=result.title,
        recipes=result.recipes,
    )

    return ExtractResponse(
        source_url=result.source_url,
        final_url=result.final_url,
        title=result.title,
        recipe_count=len(result.recipes),
        recipes=result.recipes,
        database_saved=database_saved,
        database_message=database_message,
    )