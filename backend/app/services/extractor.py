from typing import Optional

from .blog.extractor import extract_recipes_from_url as extract_blog_recipes_from_url
from .extraction_types import ExtractionResult
from .youtube.extractor import extract_recipe_from_youtube_url, is_youtube_url


async def extract_recipes_from_url(
    url: str, *, gemini_rate_key: Optional[str] = None
) -> ExtractionResult:
    if is_youtube_url(url):
        return await extract_recipe_from_youtube_url(
            url, gemini_rate_key=gemini_rate_key
        )

    return await extract_blog_recipes_from_url(url, gemini_rate_key=gemini_rate_key)


__all__ = [
    "ExtractionResult",
    "extract_blog_recipes_from_url",
    "extract_recipe_from_youtube_url",
    "extract_recipes_from_url",
]
