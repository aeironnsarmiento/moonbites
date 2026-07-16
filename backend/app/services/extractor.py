from .blog.extractor import extract_recipes_from_url as extract_blog_recipes_from_url
from .extraction_types import ExtractionResult
from .tiktok.extractor import extract_recipe_from_tiktok_url, is_tiktok_url
from .youtube.extractor import extract_recipe_from_youtube_url, is_youtube_url


async def extract_recipes_from_url(url: str) -> ExtractionResult:
    if is_youtube_url(url):
        return await extract_recipe_from_youtube_url(url)

    if is_tiktok_url(url):
        return await extract_recipe_from_tiktok_url(url)

    return await extract_blog_recipes_from_url(url)


__all__ = [
    "ExtractionResult",
    "extract_blog_recipes_from_url",
    "extract_recipe_from_tiktok_url",
    "extract_recipe_from_youtube_url",
    "extract_recipes_from_url",
]
