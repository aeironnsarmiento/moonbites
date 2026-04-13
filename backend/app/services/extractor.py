import json
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from backend.app.core.config import get_settings
from backend.app.schemas.extract import JsonLdBlock, NormalizedRecipe
from backend.app.services.normalizer import collect_recipe_nodes, normalize_recipe


@dataclass(slots=True)
class ExtractionResult:
    source_url: str
    final_url: str
    title: str | None
    recipes: list[NormalizedRecipe]


def normalize_url(value: str) -> str:
    from urllib.parse import urlparse

    normalized = value.strip()
    parsed = urlparse(normalized)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(
            status_code=400,
            detail="Enter a valid URL that starts with http:// or https://",
        )

    return normalized


def extract_json_ld_blocks(html: str) -> tuple[str | None, list[JsonLdBlock]]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    blocks: list[JsonLdBlock] = []

    script_tags = soup.find_all(
        "script",
        attrs={
            "type": lambda value: isinstance(value, str)
            and value.split(";", 1)[0].strip().lower() == "application/ld+json"
        },
    )

    for index, tag in enumerate(script_tags, start=1):
        raw = tag.string if tag.string is not None else tag.get_text()
        content = raw.strip()

        if not content:
            blocks.append(
                JsonLdBlock(index=index, raw="", parsed=None, parse_error="Empty script block")
            )
            continue

        try:
            parsed = json.loads(content)
            blocks.append(
                JsonLdBlock(index=index, raw=content, parsed=parsed, parse_error=None)
            )
        except json.JSONDecodeError as error:
            blocks.append(
                JsonLdBlock(
                    index=index,
                    raw=content,
                    parsed=None,
                    parse_error=f"Invalid JSON: {error.msg} (line {error.lineno}, column {error.colno})",
                )
            )

    return title, blocks


async def extract_recipes_from_url(url: str) -> ExtractionResult:
    settings = get_settings()
    target_url = normalize_url(url)

    try:
        async with httpx.AsyncClient(
            headers={
                "User-Agent": settings.user_agent,
                "Accept": settings.accept_header,
                "Accept-Language": settings.accept_language_header,
            },
            follow_redirects=True,
            timeout=settings.request_timeout_seconds,
        ) as client:
            response = await client.get(target_url)
            response.raise_for_status()
    except httpx.TimeoutException as error:
        raise HTTPException(status_code=504, detail="Request to target URL timed out") from error
    except httpx.HTTPStatusError as error:
        status_code = error.response.status_code
        raise HTTPException(
            status_code=502,
            detail=f"Target site returned HTTP {status_code}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail="Unable to fetch the target URL",
        ) from error

    title, blocks = extract_json_ld_blocks(response.text)
    recipes: list[NormalizedRecipe] = []

    for block in blocks:
        if block.parsed is not None:
            for recipe in collect_recipe_nodes(block.parsed):
                normalized = normalize_recipe(recipe)
                if normalized is not None:
                    recipes.append(normalized)

    return ExtractionResult(
        source_url=target_url,
        final_url=str(response.url),
        title=title,
        recipes=recipes,
    )