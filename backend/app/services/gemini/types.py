from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from ...schemas.extract import NormalizedRecipe


class RawExtractionPayload(BaseModel):
    source_type: Literal["json_ld", "youtube"]
    source_url: str
    final_url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    canonical_url: Optional[str] = None
    json_ld_blocks: list[Any] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class GeminiRecipeResult(BaseModel):
    recipes: list[NormalizedRecipe]
    confidence: float = Field(..., ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
