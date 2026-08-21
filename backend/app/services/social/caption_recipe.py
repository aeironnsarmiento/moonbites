"""Turning a social post's caption into a recipe.

One pipeline, shared by every caption-bearing platform: parse the caption, and
if it is not a **Caption-complete Post**, resolve a **Linked Recipe** from the
links it carries.

Link resolution follows one rule everywhere -- accept a linked page only when it
is the *single* candidate whose title names the dish the post named. Matching
needs that dish name, so a post whose caption names no dish cannot produce a
**Linked Recipe** at all: there is nothing to check a candidate against.

Instagram's importer runs the same acceptance rule through
``recipe_match.select_unique_match``, but keeps its own loop because it
checkpoints and carries a deadline across each fetch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from fastapi import HTTPException

from ..blog.extractor import extract_blog_recipes_from_safe_url
from ..extraction_types import ExtractionResult, ParseStatus
from ..gemini.recipe_parser import ParsedCaption, parse_caption_with_gemini
from ..normalizer import normalize_recipe
from ..recipe_match import RecipeCandidate, select_unique_match
from .recipe_links import extract_ranked_recipe_urls


MAX_CAPTION_LINKS = 3


@dataclass(frozen=True)
class CaptionPost:
    """A caption-bearing social post, stripped of everything platform-specific."""

    source_url: str
    final_url: str
    title: str
    caption: str
    image_url: Optional[str]


GeminiParse = Callable[..., Awaitable[ParsedCaption]]


async def _resolve_linked_recipe(
    post: CaptionPost, dish_name: str, *, mirror_provider_thumbnail: bool
) -> Optional[ExtractionResult]:
    links = extract_ranked_recipe_urls(post.caption)[:MAX_CAPTION_LINKS]
    if not links:
        return None

    candidates: list[RecipeCandidate] = []
    for link in links:
        try:
            page = await extract_blog_recipes_from_safe_url(link)
        except HTTPException:
            continue
        except Exception:  # pragma: no cover - defensive network fallback
            continue

        for recipe in page.recipes:
            candidates.append(
                RecipeCandidate(
                    canonical_url=page.final_url, title=recipe.name, result=page
                )
            )

    match = select_unique_match(candidates, dish_name)
    if match is None:
        return None

    page = match.result
    recipe = next(item for item in page.recipes if item.name == match.title)
    # The post's own thumbnail is mirrored only when the matched page brought no
    # image of its own -- otherwise the page's image is already the better one.
    borrows_post_thumbnail = page.image_url is None and post.image_url is not None
    return ExtractionResult(
        source_url=post.source_url,
        final_url=page.final_url,
        title=page.title or post.title,
        image_url=page.image_url or post.image_url,
        recipe_node_count=page.recipe_node_count,
        recipes=[recipe],
        provider_thumbnail_url=(
            post.image_url
            if mirror_provider_thumbnail and borrows_post_thumbnail
            else None
        ),
    )


async def extract_recipe_from_caption(
    post: CaptionPost,
    *,
    not_recipe_reason: str,
    mirror_provider_thumbnail: bool = False,
    gemini_parse: Optional[GeminiParse] = None,
) -> ExtractionResult:
    # Resolved at call time, not bound as a default, so the module-level name
    # stays the single seam both injection and patching go through.
    parse = gemini_parse or parse_caption_with_gemini

    parsed: Optional[ParsedCaption] = None
    gemini_error: Optional[HTTPException] = None
    try:
        parsed = await parse(
            title=post.title,
            caption=post.caption,
            source_url=post.source_url,
        )
    except HTTPException as error:
        gemini_error = error

    if parsed is not None and parsed.is_complete:
        recipe = normalize_recipe(parsed.raw_recipe)
        if recipe is not None:
            return ExtractionResult(
                source_url=post.source_url,
                final_url=post.final_url,
                title=post.title,
                image_url=post.image_url,
                recipe_node_count=1,
                recipes=[recipe],
                provider_thumbnail_url=(
                    post.image_url if mirror_provider_thumbnail else None
                ),
                parse_status=ParseStatus.RECIPE,
            )

    dish_name = (parsed.candidate_name or "").strip() if parsed is not None else ""
    if dish_name:
        linked = await _resolve_linked_recipe(
            post, dish_name, mirror_provider_thumbnail=mirror_provider_thumbnail
        )
        if linked is not None:
            return linked

    if gemini_error is not None:
        raise gemini_error

    parse_reason = parsed.parse_reason if parsed is not None else None
    return ExtractionResult(
        source_url=post.source_url,
        final_url=post.final_url,
        title=post.title,
        image_url=post.image_url,
        recipe_node_count=0,
        recipes=[],
        provider_thumbnail_url=None,
        parse_status=ParseStatus.NOT_RECIPE,
        parse_reason=parse_reason or not_recipe_reason,
    )
