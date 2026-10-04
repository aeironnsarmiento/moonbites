"""Server-rendered <head> metadata for recipe pages.

The frontend is a client-rendered SPA, so crawlers and link-preview bots that
don't run JavaScript see an empty shell. This module takes the built
index.html shell and injects per-recipe title, description, canonical link,
Open Graph tags, schema.org/Recipe JSON-LD, and a <noscript> copy of the
recipe. Every visitor gets the same HTML; React mounts over it as usual.
"""

import json
import re
import time
from html import escape
from typing import Optional

import httpx

from ..core.config import Settings
from ..schemas.extract import NormalizedRecipe, RecipeImportRecord, RecipeRowEntry


SITE_NAME = "moonbites"
SHELL_CACHE_SECONDS = 300
DESCRIPTION_MAX_CHARS = 160
ISO_DURATION_PATTERN = re.compile(r"^P(?!$)(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+S)?)?$")
TITLE_PATTERN = re.compile(r"<title>.*?</title>", re.IGNORECASE | re.DOTALL)
ROOT_PATTERN = re.compile(r'<div id="root"></div>', re.IGNORECASE)

_shell_cache: dict[str, tuple[float, str]] = {}


async def load_shell(settings: Settings) -> str:
    """Fetch the deployed index.html, caching it and serving stale on error."""
    shell_url = f"{settings.public_site_url}/index.html"
    cached = _shell_cache.get(shell_url)
    if cached and time.monotonic() - cached[0] < SHELL_CACHE_SECONDS:
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(shell_url)
            response.raise_for_status()
    except httpx.HTTPError as error:
        if cached:
            return cached[1]
        raise RuntimeError(f"Could not load page shell: {error}") from error

    _shell_cache[shell_url] = (time.monotonic(), response.text)
    return response.text


def _resolve_rows(
    rows: list[str], layout: Optional[list[RecipeRowEntry]]
) -> list[str]:
    if layout is None:
        return list(rows)

    resolved = []
    for entry in layout:
        if entry.text is not None:
            resolved.append(entry.text)
        elif entry.source is not None and entry.source < len(rows):
            resolved.append(rows[entry.source])
    return resolved


def _displayed_recipes(
    record: RecipeImportRecord,
) -> list[tuple[NormalizedRecipe, list[str], list[str]]]:
    displayed = []
    for index, recipe in enumerate(record.recipes_json):
        overrides = record.recipe_overrides_json.get(str(index))
        ingredients = _resolve_rows(
            recipe.ingredients, overrides.ingredients if overrides else None
        )
        instructions = _resolve_rows(
            recipe.instructions, overrides.instructions if overrides else None
        )
        displayed.append((recipe, ingredients, instructions))
    return displayed


def _source_url(record: RecipeImportRecord) -> Optional[str]:
    if record.submitted_url.strip().lower().startswith("manual://"):
        return None
    return record.final_url or record.submitted_url


def _truncate(text: str, limit: int = DESCRIPTION_MAX_CHARS) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip(" ,;") + "…"


def _description(title: str, ingredients: list[str]) -> str:
    if ingredients:
        return _truncate(f"{title} recipe with {', '.join(ingredients)}")
    return _truncate(f"{title} recipe saved on {SITE_NAME}")


def _recipe_json_ld(
    recipe: NormalizedRecipe,
    ingredients: list[str],
    instructions: list[str],
    *,
    page_url: str,
    image_url: Optional[str],
    source_url: Optional[str],
    description: str,
    created_at: str,
) -> dict:
    data: dict = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": recipe.name,
        "url": page_url,
        "description": description,
        "datePublished": created_at,
        "recipeIngredient": ingredients,
        "recipeInstructions": [
            {"@type": "HowToStep", "position": position, "text": text}
            for position, text in enumerate(instructions, start=1)
        ],
    }
    if image_url:
        data["image"] = [image_url]
    if recipe.recipeYield:
        data["recipeYield"] = recipe.recipeYield
    if recipe.cookTime and ISO_DURATION_PATTERN.match(recipe.cookTime):
        data["cookTime"] = recipe.cookTime
    if recipe.recipeCuisine:
        data["recipeCuisine"] = recipe.recipeCuisine
    if source_url:
        data["isBasedOn"] = source_url
    return data


def _script_safe_json(data: object) -> str:
    # Escape characters that could close the <script> element or start an
    # HTML comment; recipe text comes from scraped third-party pages.
    return (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _meta(attribute: str, key: str, content: str) -> str:
    return f'<meta {attribute}="{escape(key)}" content="{escape(content)}" />'


def _noscript_body(
    displayed: list[tuple[NormalizedRecipe, list[str], list[str]]],
    source_url: Optional[str],
) -> str:
    parts = ["<noscript><article>"]
    for recipe, ingredients, instructions in displayed:
        parts.append(f"<h1>{escape(recipe.name)}</h1>")
        if recipe.recipeYield:
            parts.append(f"<p>Yield: {escape(recipe.recipeYield)}</p>")
        if ingredients:
            parts.append("<h2>Ingredients</h2><ul>")
            parts.extend(f"<li>{escape(item)}</li>" for item in ingredients)
            parts.append("</ul>")
        if instructions:
            parts.append("<h2>Instructions</h2><ol>")
            parts.extend(f"<li>{escape(step)}</li>" for step in instructions)
            parts.append("</ol>")
    if source_url:
        safe_url = escape(source_url)
        parts.append(f'<p>Source: <a href="{safe_url}">{safe_url}</a></p>')
    parts.append("</article></noscript>")
    return "".join(parts)


def render_recipe_page(
    shell: str, record: RecipeImportRecord, settings: Settings
) -> str:
    displayed = _displayed_recipes(record)
    primary = displayed[0] if displayed else None
    title = (
        primary[0].name if primary else record.page_title
    ) or "Untitled recipe"
    page_url = f"{settings.public_site_url}/recipes/{record.id}"
    source_url = _source_url(record)
    # Imported recipes point search engines at the original creator's page;
    # manual recipes are original content and canonicalize to themselves.
    canonical_url = source_url or page_url
    description = _description(title, primary[1] if primary else [])
    created_at = record.created_at.isoformat()

    head = [
        f'<meta name="description" content="{escape(description)}" />',
        f'<link rel="canonical" href="{escape(canonical_url)}" />',
        _meta("property", "og:site_name", SITE_NAME),
        _meta("property", "og:type", "article"),
        _meta("property", "og:title", title),
        _meta("property", "og:description", description),
        _meta("property", "og:url", page_url),
        _meta(
            "name",
            "twitter:card",
            "summary_large_image" if record.image_url else "summary",
        ),
    ]
    if record.image_url:
        head.append(_meta("property", "og:image", record.image_url))

    json_ld = [
        _recipe_json_ld(
            recipe,
            ingredients,
            instructions,
            page_url=page_url,
            image_url=record.image_url,
            source_url=source_url,
            description=description,
            created_at=created_at,
        )
        for recipe, ingredients, instructions in displayed
    ]
    if json_ld:
        payload = json_ld[0] if len(json_ld) == 1 else json_ld
        head.append(
            '<script type="application/ld+json">'
            f"{_script_safe_json(payload)}</script>"
        )

    html = TITLE_PATTERN.sub(
        lambda _: f"<title>{escape(title)} · {SITE_NAME}</title>", shell, count=1
    )
    html = html.replace("</head>", "\n    ".join(["", *head]) + "\n  </head>", 1)
    return ROOT_PATTERN.sub(
        lambda match: _noscript_body(displayed, source_url) + match.group(0),
        html,
        count=1,
    )
