from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..schemas.extract import NormalizedRecipe


class ParseStatus(str, Enum):
    RECIPE = "recipe"
    NOT_RECIPE = "not_recipe"


@dataclass
class ExtractionResult:
    source_url: str
    final_url: str
    title: Optional[str]
    image_url: Optional[str]
    recipe_node_count: int
    recipes: list[NormalizedRecipe]
    parse_status: ParseStatus = ParseStatus.RECIPE
    parse_reason: Optional[str] = None
