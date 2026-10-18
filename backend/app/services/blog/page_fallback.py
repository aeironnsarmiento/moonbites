"""The Gemini fallback for a blog page with no saveable JSON-LD recipe.

Gemini reads the page's main text and the result is accepted only when it is a
complete recipe that passes the fabrication check. When Gemini is unconfigured,
rate-limited or failing, the caller gets ``GEMINI_UNAVAILABLE`` and ends exactly
as it would have without a fallback -- this module never raises.

Callers decide *whether* to spend the fallback: a pasted URL always does, while
a **Linked Recipe** flow spends it only on the single page it matched.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, Optional

from fastapi import HTTPException

from ...schemas.extract import NormalizedRecipe, ParseStatus
from ..extraction_types import ExtractionResult
from ..gemini.recipe_parser import ParsedCaption, parse_page_text_with_gemini
from ..normalizer import normalize_recipe
from ..recipe_match import hostname


logger = logging.getLogger(__name__)

NOT_RECIPE_REASON = "The page does not contain a recipe."

PageParse = Callable[..., Awaitable[ParsedCaption]]


class FallbackOutcome(str, Enum):
    # The recipe passed the quality bar and goes on to the normal save path.
    RECIPE = "recipe"
    NOT_RECIPE = "not_recipe"
    GEMINI_UNAVAILABLE = "gemini_unavailable"


@dataclass(frozen=True)
class PageFallbackResult:
    outcome: FallbackOutcome
    recipe: Optional[NormalizedRecipe] = None
    reason: Optional[str] = None


async def _parse(page: ExtractionResult, parse: PageParse) -> PageFallbackResult:
    page_text = page.page_text
    assert page_text is not None

    try:
        parsed = await parse(
            title=page_text.title or "",
            page_text=page_text.text,
            source_url=page.final_url,
        )
    except HTTPException:
        return PageFallbackResult(FallbackOutcome.GEMINI_UNAVAILABLE)
    except Exception:  # an unexpected parser failure must not become a new error
        logger.exception("Blog Gemini fallback failed unexpectedly for %s", page.final_url)
        return PageFallbackResult(FallbackOutcome.GEMINI_UNAVAILABLE)

    if parsed.is_complete:
        recipe = normalize_recipe(parsed.raw_recipe)
        if recipe is not None:
            return PageFallbackResult(FallbackOutcome.RECIPE, recipe=recipe)

    return PageFallbackResult(
        FallbackOutcome.NOT_RECIPE, reason=parsed.parse_reason or NOT_RECIPE_REASON
    )


async def recover_recipe_from_page(
    page: ExtractionResult, *, parse: Optional[PageParse] = None
) -> PageFallbackResult:
    """Run the fallback once on a page that carries ``page_text``, and log it."""
    if page.page_text is None:
        raise ValueError("Only a page without a saveable JSON-LD recipe can fall back")

    # Resolved at call time so patching the module-level name reaches it.
    result = await _parse(page, parse or parse_page_text_with_gemini)

    host = hostname(page.final_url) or ""
    trigger = page.page_text.trigger.value
    logger.info(
        "Blog Gemini fallback host=%s trigger=%s outcome=%s",
        host,
        trigger,
        result.outcome.value,
        extra={
            "fallback_host": host,
            "fallback_trigger": trigger,
            "fallback_outcome": result.outcome.value,
        },
    )
    return result


async def apply_page_fallback(
    page: ExtractionResult, *, parse: Optional[PageParse] = None
) -> ExtractionResult:
    """The pasted-URL use of the fallback: fold its outcome into the page result.

    A page that already yielded a recipe is returned untouched, as is one whose
    fallback found Gemini unavailable -- the import then ends exactly as today.
    """
    if page.recipes or page.page_text is None:
        return page

    result = await recover_recipe_from_page(page, parse=parse)

    if result.outcome is FallbackOutcome.RECIPE and result.recipe is not None:
        return dataclasses.replace(page, recipes=[result.recipe])
    if result.outcome is FallbackOutcome.NOT_RECIPE:
        return dataclasses.replace(
            page, parse_status=ParseStatus.NOT_RECIPE, parse_reason=result.reason
        )
    return page
