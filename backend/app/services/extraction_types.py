from dataclasses import dataclass
from typing import Optional

from ..schemas.extract import NormalizedRecipe, ParseStatus


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


__all__ = ["ExtractionResult", "ParseStatus"]
