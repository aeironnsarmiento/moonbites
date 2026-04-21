import json
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from ..core.config import Settings, get_settings
from ..schemas.extract import IngredientSection, JsonLdBlock, NormalizedRecipe
from ..utils.text import clean_text
from .normalizer import (
    collect_recipe_nodes,
    dedupe_normalized_recipes,
    normalize_recipe,
)


@dataclass
class ExtractionResult:
    source_url: str
    final_url: str
    title: Optional[str]
    recipes: list[NormalizedRecipe]


INGREDIENT_HEADING_KEYWORDS = {"ingredient", "ingredients"}
INGREDIENT_STOP_KEYWORDS = {
    "direction",
    "directions",
    "instruction",
    "instructions",
    "method",
    "methods",
    "note",
    "notes",
    "prep",
    "preparation",
    "step",
    "steps",
}
CONTAINER_SELECTORS = (
    "article",
    "main",
    ".entry-content",
    ".post-content",
    ".the-content",
    ".content",
    "[class*='recipe']",
    "[id*='recipe']",
)


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


def extract_json_ld_blocks(html: str) -> tuple[Optional[str], list[JsonLdBlock]]:
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
                JsonLdBlock(
                    index=index, raw="", parsed=None, parse_error="Empty script block"
                )
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


def _normalize_heading(text: str) -> Optional[str]:
    cleaned = clean_text(text)
    if not cleaned:
        return None

    return cleaned.casefold().rstrip(":")


def _is_ingredient_start_heading(text: str) -> bool:
    normalized = _normalize_heading(text)
    if not normalized:
        return False

    return normalized in INGREDIENT_HEADING_KEYWORDS


def _is_stop_heading(text: str) -> bool:
    normalized = _normalize_heading(text)
    if not normalized:
        return False

    words = {part for part in normalized.replace("&", " ").split() if part}
    return bool(words.intersection(INGREDIENT_STOP_KEYWORDS))


def _extract_list_items(node) -> list[str]:
    return [
        cleaned
        for item in node.find_all("li")
        if (cleaned := clean_text(item.get_text(" ", strip=True)))
    ]


def _score_container_sections(
    sections: list[IngredientSection], found_stop: bool
) -> int:
    item_count = sum(len(section.items) for section in sections)
    titled_sections = sum(1 for section in sections if section.title)
    return item_count + titled_sections * 2 + (5 if found_stop else 0)


def _extract_ingredient_sections_from_container(
    container,
) -> tuple[list[IngredientSection], bool]:
    sections: list[IngredientSection] = []
    current_title: Optional[str] = None
    current_items: list[str] = []
    in_ingredients = False
    found_stop_heading = False

    def flush_section() -> None:
        nonlocal current_items, current_title

        items = [item for item in current_items if item]
        if items:
            sections.append(IngredientSection(title=current_title, items=items))

        current_title = None
        current_items = []

    for node in container.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol"]):
        if node.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            heading_text = node.get_text(" ", strip=True)

            if _is_ingredient_start_heading(heading_text):
                flush_section()
                in_ingredients = True
                current_title = None
                continue

            if not in_ingredients:
                continue

            if _is_stop_heading(heading_text):
                found_stop_heading = True
                flush_section()
                break

            flush_section()
            current_title = clean_text(heading_text.rstrip(":"))
            continue

        if not in_ingredients:
            continue

        items = _extract_list_items(node)
        if items:
            current_items.extend(items)

    flush_section()
    return sections, found_stop_heading


def extract_html_ingredient_sections(html: str) -> list[IngredientSection]:
    soup = BeautifulSoup(html, "html.parser")
    containers = []

    for selector in CONTAINER_SELECTORS:
        containers.extend(soup.select(selector))

    if not containers:
        containers = [soup.body or soup]

    best_sections: list[IngredientSection] = []
    best_score = 0

    for container in containers:
        sections, found_stop_heading = _extract_ingredient_sections_from_container(
            container
        )
        if not sections:
            continue

        score = _score_container_sections(sections, found_stop_heading)
        if score > best_score:
            best_score = score
            best_sections = sections

    return best_sections


def _build_request_headers(settings: Settings) -> dict[str, str]:
    return {
        "User-Agent": settings.user_agent,
        "Accept": settings.accept_header,
        "Accept-Language": settings.accept_language_header,
    }


def _build_403_retry_headers(settings: Settings) -> dict[str, str]:
    return {
        **_build_request_headers(settings),
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }


def _should_retry_403(response: httpx.Response, *, retried: bool) -> bool:
    return not retried and response.status_code == 403


async def _get_with_403_retry(
    client: httpx.AsyncClient, url: str, settings: Settings
) -> httpx.Response:
    response = await client.get(url)

    if _should_retry_403(response, retried=False):
        response = await client.get(url, headers=_build_403_retry_headers(settings))

    return response


async def extract_recipes_from_url(url: str) -> ExtractionResult:
    settings = get_settings()
    target_url = normalize_url(url)

    try:
        async with httpx.AsyncClient(
            headers=_build_request_headers(settings),
            follow_redirects=True,
            timeout=settings.request_timeout_seconds,
        ) as client:
            response = await _get_with_403_retry(client, target_url, settings)
            response.raise_for_status()
    except httpx.TimeoutException as error:
        raise HTTPException(
            status_code=504, detail="Request to target URL timed out"
        ) from error
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
    html_ingredient_sections = extract_html_ingredient_sections(response.text)
    recipes: list[NormalizedRecipe] = []
    recipe_nodes: list[dict] = []

    for block in blocks:
        if block.parsed is not None:
            recipe_nodes.extend(collect_recipe_nodes(block.parsed))

    fallback_sections = html_ingredient_sections if len(recipe_nodes) == 1 else None

    for recipe in recipe_nodes:
        normalized = normalize_recipe(
            recipe,
            fallback_ingredient_sections=fallback_sections,
        )
        if normalized is not None:
            recipes.append(normalized)

    recipes = dedupe_normalized_recipes(recipes)

    return ExtractionResult(
        source_url=target_url,
        final_url=str(response.url),
        title=title,
        recipes=recipes,
    )
