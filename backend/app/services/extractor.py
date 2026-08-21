from fastapi import HTTPException

from .blog.extractor import extract_recipes_from_url as extract_blog_recipes_from_url
from .extraction_types import ExtractionResult
from .instagram.urls import is_instagram_url
from .tiktok.extractor import extract_recipe_from_tiktok_url, is_tiktok_url
from .youtube.extractor import extract_recipe_from_youtube_url, is_youtube_url


async def extract_recipes_from_url(url: str) -> ExtractionResult:
    if is_youtube_url(url):
        return await extract_recipe_from_youtube_url(url)

    if is_tiktok_url(url):
        return await extract_recipe_from_tiktok_url(url)

    if is_instagram_url(url):
        # Instagram Reels use a separate durable-job import flow (see
        # api/routes/extract.py) and must never fall through to blog
        # extraction, which would misread the Instagram page.
        raise HTTPException(
            status_code=400,
            detail="Instagram URLs must be imported through the Reel import flow.",
        )

    return await extract_blog_recipes_from_url(url)


__all__ = [
    "ExtractionResult",
    "extract_blog_recipes_from_url",
    "extract_recipe_from_tiktok_url",
    "extract_recipe_from_youtube_url",
    "extract_recipes_from_url",
]
