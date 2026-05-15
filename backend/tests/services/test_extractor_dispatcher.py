import asyncio
from unittest.mock import AsyncMock, patch

from app.schemas.extract import NormalizedRecipe
from app.services.extraction_types import ExtractionResult
from app.services.extractor import extract_recipes_from_url


def _result(source_url: str) -> ExtractionResult:
    return ExtractionResult(
        source_url=source_url,
        final_url=source_url,
        title="Recipe",
        image_url=None,
        recipe_node_count=1,
        recipes=[
            NormalizedRecipe(
                name="Recipe",
                ingredients=["1 cup rice"],
                instructions=["Cook rice."],
            )
        ],
    )


def test_extract_recipes_from_url_dispatches_youtube_urls():
    with (
        patch(
            "app.services.extractor.extract_recipe_from_youtube_url",
            new=AsyncMock(return_value=_result("https://youtu.be/abc123XYZ09")),
        ) as youtube,
        patch("app.services.extractor.extract_blog_recipes_from_url") as blog,
    ):
        result = asyncio.run(
            extract_recipes_from_url(
                "https://youtu.be/abc123XYZ09",
                gemini_rate_key="admin@example.com",
            )
        )

    youtube.assert_awaited_once_with(
        "https://youtu.be/abc123XYZ09",
        gemini_rate_key="admin@example.com",
    )
    blog.assert_not_called()
    assert result.source_url == "https://youtu.be/abc123XYZ09"


def test_extract_recipes_from_url_dispatches_non_youtube_urls():
    with (
        patch("app.services.extractor.extract_recipe_from_youtube_url") as youtube,
        patch(
            "app.services.extractor.extract_blog_recipes_from_url",
            new=AsyncMock(return_value=_result("https://example.com/recipe")),
        ) as blog,
    ):
        result = asyncio.run(
            extract_recipes_from_url(
                "https://example.com/recipe",
                gemini_rate_key="admin@example.com",
            )
        )

    blog.assert_awaited_once_with(
        "https://example.com/recipe",
        gemini_rate_key="admin@example.com",
    )
    youtube.assert_not_called()
    assert result.source_url == "https://example.com/recipe"
