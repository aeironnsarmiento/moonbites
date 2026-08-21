from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import HTTPException

from ...core.config import get_settings
from ..blog.extractor import normalize_url
from ..extraction_types import ExtractionResult
from ..social.caption_recipe import CaptionPost, extract_recipe_from_caption


YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
YOUTU_BE_HOSTS = {"youtu.be", "www.youtu.be"}


@dataclass(frozen=True)
class YouTubeSnippet:
    video_id: str
    title: str
    description: str
    thumbnail_url: Optional[str]


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
    )


async def extract_recipe_from_youtube_url(url: str) -> ExtractionResult:
    target_url = normalize_url(url)
    video = await fetch_youtube_snippet(target_url)
    return await extract_recipe_from_caption(
        CaptionPost(
            source_url=target_url,
            final_url=target_url,
            title=video.title,
            caption=video.description,
            image_url=video.thumbnail_url,
        ),
        not_recipe_reason="No recipe was found in the video description.",
    )
