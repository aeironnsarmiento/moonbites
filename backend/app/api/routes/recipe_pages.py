from html import escape
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ...core.config import get_settings
from ...core.rate_limit import limiter
from ...repositories.recipe_imports import get_recipe_import
from ...services.recipe_page import load_shell, render_recipe_page


router = APIRouter(tags=["recipe-pages"])

RECIPE_PAGE_CACHE_CONTROL = "public, max-age=0, s-maxage=300, stale-while-revalidate=600"


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


@router.get(
    "/recipe-pages/{recipe_import_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
@limiter.limit("60/minute")
async def get_recipe_page(request: Request, recipe_import_id: str) -> HTMLResponse:
    """Serve the SPA shell for /recipes/:id with recipe metadata injected.

    Vercel rewrites /recipes/:id here. Any failure falls back to the plain
    shell so the page still loads; the SPA renders its own not-found state.
    """
    settings = get_settings()
    try:
        shell = await load_shell(settings)
    except RuntimeError as error:
        return HTMLResponse(
            f"<!doctype html><title>moonbites</title><p>{escape(str(error))}</p>",
            status_code=502,
        )

    if not _is_uuid(recipe_import_id):
        return HTMLResponse(shell, status_code=404)

    try:
        record = get_recipe_import(recipe_import_id)
    except RuntimeError:
        return HTMLResponse(shell)

    if record is None:
        return HTMLResponse(shell, status_code=404)

    return HTMLResponse(
        render_recipe_page(shell, record, settings),
        headers={"Cache-Control": RECIPE_PAGE_CACHE_CONTROL},
    )
