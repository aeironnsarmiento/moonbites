from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)


class NormalizedRecipe(BaseModel):
    name: str
    recipeYield: str | None
    cookTime: str | None
    recipeCuisine: list[str] | None
    nutrition: dict[str, str] | None
    ingredients: list[str]
    instructions: list[str]


class ExtractResponse(BaseModel):
    source_url: str
    final_url: str
    title: str | None
    recipe_count: int
    recipes: list[NormalizedRecipe]
    database_saved: bool
    database_message: str | None


class RecipeImportRecord(BaseModel):
    id: str
    submitted_url: str
    final_url: str
    page_title: str | None
    recipe_count: int
    recipes_json: list[NormalizedRecipe]
    created_at: datetime


class PaginatedRecipeImportsResponse(BaseModel):
    items: list[RecipeImportRecord]
    page: int
    page_size: int
    total_count: int
    total_pages: int


class JsonLdBlock(BaseModel):
    index: int
    raw: str
    parsed: Any | None
    parse_error: str | None