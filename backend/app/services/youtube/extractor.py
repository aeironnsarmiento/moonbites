from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import HTTPException

from ...core.config import get_settings
from ...schemas.extract import NormalizedRecipe
from ..blog.extractor import (
    extract_recipes_from_url as extract_blog_recipes_from_url,
    normalize_url,
)
from ..extraction_types import ExtractionResult, ParseStatus
from ..gemini.normalizer import GeminiNormalizationResult, normalize_with_gemini
from ..gemini.types import RawExtractionPayload
from ..normalizer import normalize_recipe
from .description_parser import (
    ParsedYouTubeDescription,
    extract_ranked_recipe_urls,
    parse_youtube_description,
)


YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
YOUTU_BE_HOSTS = {"youtu.be", "www.youtu.be"}


@dataclass(frozen=True)
class YouTubeSnippet:
    video_id: str
    title: str
    description: str
    thumbnail_url: Optional[str]
    channel_name: Optional[str]
    published_at: Optional[str]


def _hostname(url: str) -> str:
    return (urlparse(url.strip()).hostname or "").casefold()


def is_youtube_url(url: str) -> bool:
    hostname = _hostname(url)
    return hostname in YOUTUBE_HOSTS or hostname in YOUTU_BE_HOSTS


def _first_path_part(path: str, prefix: str) -> Optional[str]:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[0].casefold() == prefix:
        return parts[1]
    return None


def extract_youtube_video_id(url: str) -> Optional[str]:
    parsed = urlparse(url.strip())
    hostname = (parsed.hostname or "").casefold()

    if hostname in YOUTU_BE_HOSTS:
        return (parsed.path.strip("/").split("/", 1)[0] or None)

    if hostname not in YOUTUBE_HOSTS:
        return None

    query_video_id = parse_qs(parsed.query).get("v", [None])[0]
    if query_video_id:
        return query_video_id

    for prefix in ("shorts", "embed", "live"):
        if video_id := _first_path_part(parsed.path, prefix):
            return video_id

    return None


def _thumbnail_url(thumbnails: Any) -> Optional[str]:
    if not isinstance(thumbnails, dict):
        return None

    for key in ("maxres", "standard", "high", "medium", "default"):
        candidate = thumbnails.get(key)
        if isinstance(candidate, dict):
            url = candidate.get("url")
            if isinstance(url, str) and url.strip():
                return url.strip()

    return None


async def fetch_youtube_snippet(url: str) -> YouTubeSnippet:
    settings = get_settings()
    target_url = normalize_url(url)
    video_id = extract_youtube_video_id(target_url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Enter a valid YouTube video URL")
    if not settings.youtube_api_key:
        raise HTTPException(
            status_code=503,
            detail="YouTube extraction is not configured",
        )

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.get(
                YOUTUBE_API_URL,
                params={
                    "part": "snippet",
                    "id": video_id,
                    "key": settings.youtube_api_key,
                },
            )
            response.raise_for_status()
    except httpx.TimeoutException as error:
        raise HTTPException(
            status_code=504,
            detail="Request to YouTube API timed out",
        ) from error
    except httpx.HTTPStatusError as error:
        status_code = error.response.status_code
        raise HTTPException(
            status_code=502,
            detail=f"YouTube API returned HTTP {status_code}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail="Unable to fetch YouTube video metadata",
        ) from error

    payload = response.json()
    items = payload.get("items") if isinstance(payload, dict) else None
    if not items:
        raise HTTPException(
            status_code=404,
            detail="YouTube video was not found",
        )

    item = items[0]
    snippet = item.get("snippet") if isinstance(item, dict) else {}
    if not isinstance(snippet, dict):
        snippet = {}

    return YouTubeSnippet(
        video_id=str(item.get("id") or video_id),
        title=str(snippet.get("title") or "").strip(),
        description=str(snippet.get("description") or ""),
        thumbnail_url=_thumbnail_url(snippet.get("thumbnails")),
        channel_name=(
            str(snippet.get("channelTitle")).strip()
            if snippet.get("channelTitle")
            else None
        ),
        published_at=(
            str(snippet.get("publishedAt")).strip()
            if snippet.get("publishedAt")
            else None
        ),
    )


def build_youtube_raw_payload(
    target_url: str, video: YouTubeSnippet
) -> RawExtractionPayload:
    metadata: dict[str, str] = {}
    if video.channel_name:
        metadata["channelName"] = video.channel_name
    if video.published_at:
        metadata["publishedAt"] = video.published_at
    if video.thumbnail_url:
        metadata["thumbnailUrl"] = video.thumbnail_url

    return RawExtractionPayload(
        source_type="youtube",
        source_url=target_url,
        final_url=target_url,
        title=video.title,
        description=video.description,
        metadata=metadata,
    )


async def _extract_first_recipe_link(
    description: str,
    *,
    youtube_url: str,
    youtube_title: str,
    youtube_thumbnail_url: Optional[str],
) -> Optional[ExtractionResult]:
    for recipe_url in extract_ranked_recipe_urls(description):
        try:
            result = await extract_blog_recipes_from_url(recipe_url)
        except HTTPException:
            continue
        except Exception:  # pragma: no cover - defensive network fallback
            continue

        if result.recipes:
            return ExtractionResult(
                source_url=youtube_url,
                final_url=result.final_url,
                title=result.title or youtube_title,
                image_url=result.image_url or youtube_thumbnail_url,
                recipe_node_count=result.recipe_node_count,
                recipes=result.recipes,
            )

    return None


def _description_mentions_recipe_link(description: str) -> bool:
    text = description.casefold()
    if "recipe" not in text:
        return False
    return bool(extract_ranked_recipe_urls(description))


def _parse_description(
    title: str,
    description: str,
    *,
    source_url: str,
) -> ParsedYouTubeDescription:
    return parse_youtube_description(
        title=title,
        description=description,
        source_url=source_url,
    )


async def _parse_youtube_with_legacy_logic(
    target_url: str, video: YouTubeSnippet
) -> ExtractionResult:
    parsed = _parse_description(
        video.title,
        video.description,
        source_url=target_url,
    )

    if parsed.is_complete:
        return ExtractionResult(
            source_url=target_url,
            final_url=target_url,
            title=video.title,
            image_url=video.thumbnail_url,
            recipe_node_count=1,
            recipes=[normalize_recipe(parsed.raw_recipe)],
            parse_status=ParseStatus.RECIPE,
        )

    if _description_mentions_recipe_link(video.description):
        fallback = await _extract_first_recipe_link(
            video.description,
            youtube_url=target_url,
            youtube_title=video.title,
            youtube_thumbnail_url=video.thumbnail_url,
        )
        if fallback is not None:
            return fallback

    if parsed.parse_status == "not_recipe":
        return ExtractionResult(
            source_url=target_url,
            final_url=target_url,
            title=video.title,
            image_url=video.thumbnail_url,
            recipe_node_count=0,
            recipes=[],
            parse_status=ParseStatus.NOT_RECIPE,
            parse_reason=parsed.parse_reason,
        )

    return ExtractionResult(
        source_url=target_url,
        final_url=target_url,
        title=video.title,
        image_url=video.thumbnail_url,
        recipe_node_count=0,
        recipes=[],
        parse_status=ParseStatus.RECIPE,
    )


def _build_gemini_extraction_result(
    target_url: str,
    video: YouTubeSnippet,
    gemini_result: GeminiNormalizationResult,
) -> ExtractionResult:
    recipes = [
        recipe.model_copy(update={"instructions": [target_url]})
        for recipe in gemini_result.recipes
    ]

    return ExtractionResult(
        source_url=target_url,
        final_url=target_url,
        title=video.title,
        image_url=video.thumbnail_url,
        recipe_node_count=len(recipes),
        recipes=recipes,
        extraction_method="gemini",
        normalization_model=gemini_result.normalization_model,
        warnings=list(gemini_result.warnings),
    )


def _apply_gemini_fallback_metadata(
    result: ExtractionResult, gemini_result: GeminiNormalizationResult
) -> ExtractionResult:
    result.extraction_method = "manual_fallback"
    result.fallback_reason = gemini_result.fallback_reason
    result.warnings = list(gemini_result.warnings)
    result.normalization_model = gemini_result.normalization_model
    return result


async def extract_recipe_from_youtube_url(
    url: str, *, gemini_rate_key: str | None = None
) -> ExtractionResult:
    target_url = normalize_url(url)
    video = await fetch_youtube_snippet(target_url)

    if not gemini_rate_key:
        return await _parse_youtube_with_legacy_logic(target_url, video)

    gemini_result = await normalize_with_gemini(
        build_youtube_raw_payload(target_url, video),
        settings=get_settings(),
        rate_key=gemini_rate_key,
    )
    if gemini_result.accepted:
        return _build_gemini_extraction_result(target_url, video, gemini_result)

    legacy_result = await _parse_youtube_with_legacy_logic(target_url, video)
    return _apply_gemini_fallback_metadata(legacy_result, gemini_result)
