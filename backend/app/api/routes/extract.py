from fastapi import APIRouter, Depends

from ..auth import AuthenticatedAdmin, require_admin_user
from ...repositories.recipe_imports import save_recipe_import
from ...schemas.extract import ExtractRequest, ExtractResponse
from ...services.extractor import extract_recipes_from_url


router = APIRouter(prefix="/api", tags=["extract"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/extract", response_model=ExtractResponse)
async def extract_ld_json(
    payload: ExtractRequest,
    admin: AuthenticatedAdmin = Depends(require_admin_user),
) -> ExtractResponse:
    result = await extract_recipes_from_url(payload.url)
    if result.recipes:
        database_saved, database_message = save_recipe_import(
            submitted_url=result.source_url,
            final_url=result.final_url,
            title=result.title,
            recipes=result.recipes,
            image_url=result.image_url,
            access_token=admin.access_token,
        )
    else:
        database_saved = False
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
        recipe_count=len(result.recipes),
        recipes=result.recipes,
        database_saved=database_saved,
        database_message=database_message,
    )
