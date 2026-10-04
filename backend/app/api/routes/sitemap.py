from typing import Optional
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Request, Response

from ...core.config import get_settings
from ...core.rate_limit import limiter
from ...repositories.recipe_imports import list_recipe_sitemap_entries


router = APIRouter(tags=["sitemap"])

SITEMAP_CACHE_CONTROL = "public, max-age=3600, s-maxage=3600"
STATIC_PATHS = ("/", "/recipes")


def _url_element(loc: str, lastmod: Optional[str] = None) -> str:
    lastmod_element = f"<lastmod>{escape(lastmod)}</lastmod>" if lastmod else ""
    return f"<url><loc>{escape(loc)}</loc>{lastmod_element}</url>"


@router.get("/sitemap.xml", include_in_schema=False)
@limiter.limit("10/minute")
async def get_sitemap(request: Request) -> Response:
    try:
        entries = list_recipe_sitemap_entries()
    except RuntimeError as error:
        message = str(error)
        status_code = 503 if "not configured" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from error

    site_url = get_settings().public_site_url
    urls = [_url_element(f"{site_url}{path}") for path in STATIC_PATHS]
    urls.extend(
        _url_element(f"{site_url}/recipes/{entry.id}", entry.created_at[:10])
        for entry in entries
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(urls)
        + "</urlset>"
    )
    return Response(
        content=body,
        media_type="application/xml",
        headers={"Cache-Control": SITEMAP_CACHE_CONTROL},
    )
