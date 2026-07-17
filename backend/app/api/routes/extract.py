from fastapi import APIRouter, Depends, Request

from ..auth import AuthenticatedAdmin, require_admin_user
from ...core.rate_limit import limiter
from ...repositories.recipe_imports import save_recipe_import
from ...schemas.extract import DisplayTitleSource, ExtractRequest, ExtractResponse
from ...services.extraction_types import ParseStatus
from ...services.extractor import extract_recipes_from_url
from ...services.gemini.title_generator import generate_display_title


router = APIRouter(prefix="/api", tags=["extract"])
GENERIC_SAVE_SUCCESS_MESSAGE = "Recipe saved to your collection."


def _sanitize_database_message(database_saved: bool, message: str) -> str:
    if database_saved and "Supabase table" in message:
        return GENERIC_SAVE_SUCCESS_MESSAGE

    return message


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/extract", response_model=ExtractResponse)
@limiter.limit("10/minute")
async def extract_ld_json(
    request: Request,
    payload: ExtractRequest,
    admin: AuthenticatedAdmin = Depends(require_admin_user),
) -> ExtractResponse:
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
        # Generation hangs off the route rather than extract_recipes_from_url
        # because the refetch CLI calls that dispatcher too, and re-titling on
        # refetch is out of scope. No try/except: the generator never raises,
        # degrading to a cleaned source title instead, so a title can never
        # fail an import.
        display_title = await generate_display_title(
            source_title=result.title,
            recipes=result.recipes,
        )
        database_saved, database_message = save_recipe_import(
            submitted_url=result.source_url,
            final_url=result.final_url,
            title=result.title,
            recipes=result.recipes,
            image_url=result.image_url,
            access_token=admin.access_token,
            display_title=display_title.value,
            display_title_source=DisplayTitleSource(display_title.source),
        )
        database_message = _sanitize_database_message(database_saved, database_message)
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
        image_url=result.image_url,
        recipes=result.recipes,
        database_saved=database_saved,
        database_message=database_message,
        parse_status="recipe",
    )
