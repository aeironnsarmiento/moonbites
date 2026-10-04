from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


def _strip_ingredient_markers(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    import re

    return re.sub(r"^[\s•◦▪▫●○■□▢▣▤▥▦▧▨▩☐☑✓✔✗✘*-]+", "", value).strip()


def _is_manual_recipe_url(value: str) -> bool:
    return value.strip().lower().startswith("manual://")


def _validate_http_url(value: str, *, field_name: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} must start with http:// or https://")

    return value


class ExtractRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)


class CreateManualRecipeRequest(BaseModel):
    recipe: "NormalizedRecipe"
    title: Optional[str] = None


class DeleteRecipeImportResponse(BaseModel):
    id: str


class UpdateTimesCookedRequest(BaseModel):
    delta: int = Field(...)


class RecipeRowEntry(BaseModel):
    """One displayed row: `source` is the parsed row index (None for an added
    row) and `text` replaces that row's text (None keeps the parsed text)."""

    source: Optional[int] = Field(default=None, ge=0)
    text: Optional[str] = None


class RecipeTextOverrides(BaseModel):
    """Full row layouts per section, in display order. Parsed rows missing from
    a layout are deleted. None means the section is shown as parsed."""

    ingredients: Optional[list[RecipeRowEntry]] = None
    instructions: Optional[list[RecipeRowEntry]] = None


class UpdateRecipeOverridesRequest(BaseModel):
    recipe_index: int = Field(..., ge=0)
    overrides: RecipeTextOverrides


class UpdateServingsRequest(BaseModel):
    servings: int = Field(..., ge=1)


class UpdateImageRequest(BaseModel):
    image_url: str = Field(..., min_length=1, max_length=2048)


class UpdateRecipeMetadataRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    recipe_yield: Optional[str] = Field(default=None, max_length=200)
    image_url: Optional[str] = Field(default=None, max_length=2048)
    source_url: str = Field(..., min_length=1, max_length=2048)
    fallback_video_url: Optional[str] = Field(default=None, max_length=2048)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        normalized = value.strip()
        if _is_manual_recipe_url(normalized):
            return normalized

        return _validate_http_url(normalized, field_name="source_url")

    @field_validator("fallback_video_url")
    @classmethod
    def validate_fallback_video_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        stripped = value.strip()
        if not stripped:
            return None

        return _validate_http_url(stripped, field_name="fallback_video_url")

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return value.strip()

    @field_validator("recipe_yield", "image_url")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        stripped = value.strip()
        return stripped or None


class RecipeSortOption(str, Enum):
    recent = "recent"
    az = "az"
    za = "za"
    times_cooked = "times_cooked"
    favorites = "favorites"


class CuisineFacet(BaseModel):
    label: str
    count: int


class CuisineFacetsResponse(BaseModel):
    facets: list[CuisineFacet]


class IngredientSection(BaseModel):
    title: Optional[str] = None
    items: list[str]

    @field_validator("items", mode="before")
    @classmethod
    def sanitize_items(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [_strip_ingredient_markers(item) for item in value]
        return value


class NormalizedRecipe(BaseModel):
    name: str
    recipeYield: Optional[str] = None
    cookTime: Optional[str] = None
    recipeCuisine: Optional[list[str]] = None
    nutrition: Optional[dict[str, str]] = None
    ingredients: list[str]
    ingredientSections: Optional[list[IngredientSection]] = None
    instructions: list[str]

    @field_validator("ingredients", mode="before")
    @classmethod
    def sanitize_ingredients(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [_strip_ingredient_markers(item) for item in value]
        return value


class ParseStatus(str, Enum):
    RECIPE = "recipe"
    NOT_RECIPE = "not_recipe"


# User-facing outcomes shared by the direct extract route, the Instagram job
# state machine, and the repository. One copy each so they cannot drift.
SAVE_SUCCESS_MESSAGE = "Recipe saved to your collection."
DUPLICATE_SAVE_MESSAGE = "Recipe import already exists, so the duplicate save was skipped."
NOT_RECIPE_SKIPPED_MESSAGE = "Skipped — not a recipe."


class ExtractResponse(BaseModel):
    source_url: str
    final_url: str
    title: Optional[str] = None
    image_url: Optional[str] = None
    recipes: list[NormalizedRecipe]
    database_saved: bool
    database_message: Optional[str] = None
    parse_status: ParseStatus = ParseStatus.RECIPE
    parse_reason: Optional[str] = None
    linked_recipe_url: Optional[str] = None


class RecipeImportRecord(BaseModel):
    id: str
    submitted_url: str
    final_url: str
    page_title: Optional[str] = None
    times_cooked: int = 0
    recipes_json: list[NormalizedRecipe]
    recipe_overrides_json: dict[str, RecipeTextOverrides] = Field(default_factory=dict)
    image_url: Optional[str] = None
    is_favorite: bool = False
    servings: Optional[int] = None
    fallback_video_url: Optional[str] = None
    linked_recipe_url: Optional[str] = None
    created_at: datetime


class PaginatedRecipeImportsResponse(BaseModel):
    items: list[RecipeImportRecord]
    page: int
    page_size: int
    total_count: int
    total_pages: int


class HighlightedRecipesResponse(BaseModel):
    recent: list[RecipeImportRecord]
    favorites: list[RecipeImportRecord]
    total_count: int
    favorite_count: int


class JsonLdBlock(BaseModel):
    index: int
    raw: str
    parsed: Optional[Any] = None
    parse_error: Optional[str] = None
