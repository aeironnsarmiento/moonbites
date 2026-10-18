from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..schemas.extract import NormalizedRecipe, ParseStatus


class FallbackTrigger(str, Enum):
    """Why a blog page needs the Gemini fallback."""

    MISSING_JSON_LD = "missing_json_ld"
    INCOMPLETE_JSON_LD = "incomplete_json_ld"


@dataclass(frozen=True)
class PageText:
    """What the Gemini fallback reads from a page with no saveable JSON-LD recipe.

    ``title`` doubles as the candidate dish name when the page competes to be a
    **Linked Recipe**.
    """

    title: Optional[str]
    text: str
    trigger: FallbackTrigger


@dataclass
class ExtractionResult:
    source_url: str
    final_url: str
    title: Optional[str]
    image_url: Optional[str]
    recipe_node_count: int
    recipes: list[NormalizedRecipe]
    provider_thumbnail_url: Optional[str] = None
    parse_status: ParseStatus = ParseStatus.RECIPE
    parse_reason: Optional[str] = None
    linked_recipe_url: Optional[str] = None
    # Set only by blog parsing, and only when the page yielded no saveable
    # recipe from JSON-LD.
    page_text: Optional[PageText] = None


__all__ = ["ExtractionResult", "FallbackTrigger", "PageText", "ParseStatus"]
