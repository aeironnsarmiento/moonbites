from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from ...core.config import Settings, get_settings
from ..blog.extractor import (
    extract_recipes_from_url as extract_blog_recipes_from_url,
    normalize_url,
)
from ..extraction_types import ExtractionResult, ParseStatus
from ..gemini.recipe_parser import ParsedCaption, parse_caption_with_gemini
from ..http_utils import build_request_headers, get_with_403_retry
from ..normalizer import normalize_recipe
from ..social.recipe_links import extract_ranked_recipe_urls


TIKTOK_HOSTS = {
    "tiktok.com",
    "www.tiktok.com",
    "m.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
}
HYDRATION_SCRIPT_ID = "__UNIVERSAL_DATA_FOR_REHYDRATION__"
TIKTOK_OEMBED_URL = "https://www.tiktok.com/oembed"
NOT_FOUND_DETAIL = "TikTok post was not found"


@dataclass(frozen=True)
class TikTokPost:
    item_id: str
    author_handle: str
    caption: str
    image_url: Optional[str]
    is_photo_post: bool


def is_tiktok_url(url: str) -> bool:
    hostname = (urlparse(url.strip()).hostname or "").casefold()
    return hostname in TIKTOK_HOSTS


def _canonical_post_url(author_handle: str, item_id: str, *, is_photo_post: bool) -> str:
    kind = "photo" if is_photo_post else "video"
    return f"https://www.tiktok.com/@{author_handle}/{kind}/{item_id}"


def _first_image_url(image_post: dict[str, Any]) -> Optional[str]:
    images = image_post.get("images")
    if not isinstance(images, list) or not images:
        return None
    first = images[0]
    if not isinstance(first, dict):
        return None
    image_url = first.get("imageURL")
    url_list = image_url.get("urlList") if isinstance(image_url, dict) else None
    if isinstance(url_list, list) and url_list and isinstance(url_list[0], str):
        return url_list[0]
    return None


def parse_tiktok_page(html: str) -> Optional[TikTokPost]:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id=HYDRATION_SCRIPT_ID)
    if script is None or not script.string:
        return None

    try:
        data = json.loads(script.string)
    except ValueError:
        return None

    scope = data.get("__DEFAULT_SCOPE__") if isinstance(data, dict) else None
    if not isinstance(scope, dict):
        return None

    detail: Optional[dict[str, Any]] = None
    for key in ("webapp.video-detail", "webapp.photo-detail"):
        candidate = scope.get(key)
        if isinstance(candidate, dict):
            detail = candidate
            break
    if detail is None:
        return None

    status_code = detail.get("statusCode")
    if isinstance(status_code, int) and status_code != 0:
        return None

    item_info = detail.get("itemInfo")
    item = item_info.get("itemStruct") if isinstance(item_info, dict) else None
    if not isinstance(item, dict):
        return None

    item_id = str(item.get("id") or "").strip()
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    author_handle = str(author.get("uniqueId") or "").strip()
    if not item_id or not author_handle:
        return None

    caption = str(item.get("desc") or "")

    image_post = item.get("imagePost") if isinstance(item.get("imagePost"), dict) else {}
    is_photo_post = bool(image_post.get("images"))

    image_url: Optional[str] = None
    if is_photo_post:
        image_url = _first_image_url(image_post)
    if image_url is None:
        video = item.get("video") if isinstance(item.get("video"), dict) else {}
        for key in ("cover", "originCover", "dynamicCover"):
            candidate = video.get(key)
            if isinstance(candidate, str) and candidate.strip():
                image_url = candidate.strip()
                break

    return TikTokPost(
        item_id=item_id,
        author_handle=author_handle,
        caption=caption,
        image_url=image_url,
        is_photo_post=is_photo_post,
    )


async def _fetch_page_html(url: str, settings: Settings) -> Optional[str]:
    try:
        async with httpx.AsyncClient(
            headers=build_request_headers(settings),
            follow_redirects=True,
            timeout=settings.request_timeout_seconds,
        ) as client:
            response = await get_with_403_retry(client, url, settings)
            response.raise_for_status()
            return response.text
    except httpx.HTTPError:
        # Soft failure (bot wall, timeout, upstream error): the oEmbed
        # fallback decides whether the post is reachable at all.
        return None


@dataclass(frozen=True)
class TikTokOEmbed:
    caption: str
    thumbnail_url: Optional[str]
    author_handle: Optional[str]
    item_id: Optional[str]


@dataclass(frozen=True)
class TikTokSourceMetadata:
    source_url: str
    final_url: str
    caption: str
    image_url: Optional[str]
    author_handle: Optional[str]


def _author_handle_from_oembed(payload: dict[str, Any]) -> Optional[str]:
    unique_id = payload.get("author_unique_id")
    if isinstance(unique_id, str) and unique_id.strip():
        return unique_id.strip()
    author_url = payload.get("author_url")
    if isinstance(author_url, str) and "/@" in author_url:
        handle = author_url.rsplit("/@", 1)[-1].strip("/").strip()
        if handle:
            return handle
    return None


async def _fetch_oembed(url: str, settings: Settings) -> TikTokOEmbed:
    try:
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds
        ) as client:
            response = await client.get(TIKTOK_OEMBED_URL, params={"url": url})
            response.raise_for_status()
    except httpx.TimeoutException as error:
        raise HTTPException(
            status_code=504,
            detail="Request to TikTok timed out",
        ) from error
    except httpx.HTTPStatusError as error:
        status_code = error.response.status_code
        if status_code in (400, 404):
            raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL) from error
        raise HTTPException(
            status_code=502,
            detail=f"TikTok returned HTTP {status_code}",
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail="Unable to fetch the TikTok post",
        ) from error

    try:
        payload = response.json()
    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail="TikTok returned an unreadable response",
        ) from error
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=502,
            detail="TikTok returned an unreadable response",
        )

    item_id = payload.get("embed_product_id")
    return TikTokOEmbed(
        caption=str(payload.get("title") or ""),
        thumbnail_url=(
            str(payload["thumbnail_url"])
            if isinstance(payload.get("thumbnail_url"), str)
            else None
        ),
        author_handle=_author_handle_from_oembed(payload),
        item_id=str(item_id).strip() if item_id else None,
    )


async def fetch_tiktok_source_metadata(url: str) -> TikTokSourceMetadata:
    """Fetch post metadata without parsing or replacing saved recipe content."""
    settings = get_settings()
    target_url = normalize_url(url)
    html = await _fetch_page_html(target_url, settings)
    post = parse_tiktok_page(html) if html else None

    if post is not None:
        return TikTokSourceMetadata(
            source_url=target_url,
            final_url=_canonical_post_url(
                post.author_handle,
                post.item_id,
                is_photo_post=post.is_photo_post,
            ),
            caption=post.caption,
            image_url=post.image_url,
            author_handle=post.author_handle,
        )

    oembed = await _fetch_oembed(target_url, settings)
    final_url = target_url
    if oembed.author_handle and oembed.item_id:
        final_url = _canonical_post_url(
            oembed.author_handle,
            oembed.item_id,
            is_photo_post=False,
        )

    return TikTokSourceMetadata(
        source_url=target_url,
        final_url=final_url,
        caption=oembed.caption,
        image_url=oembed.thumbnail_url,
        author_handle=oembed.author_handle,
    )


def _caption_title(caption: str, author_handle: Optional[str]) -> str:
    for line in caption.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned[:80]
    if author_handle:
        return f"@{author_handle} on TikTok"
    return "TikTok post"


def _mentions_recipe_link(caption: str) -> bool:
    if "recipe" not in caption.casefold():
        return False
    return bool(extract_ranked_recipe_urls(caption))


async def _extract_first_recipe_link(
    caption: str,
    *,
    source_url: str,
    fallback_title: str,
    fallback_image: Optional[str],
) -> Optional[ExtractionResult]:
    for recipe_url in extract_ranked_recipe_urls(caption):
        try:
            result = await extract_blog_recipes_from_url(recipe_url)
        except HTTPException:
            continue
        except Exception:  # pragma: no cover - defensive network fallback
            continue

        if result.recipes:
            uses_tiktok_thumbnail = result.image_url is None and fallback_image is not None
            return ExtractionResult(
                source_url=source_url,
                final_url=result.final_url,
                title=result.title or fallback_title,
                image_url=result.image_url or fallback_image,
                recipe_node_count=result.recipe_node_count,
                recipes=result.recipes,
                tiktok_thumbnail_url=(
                    fallback_image if uses_tiktok_thumbnail else None
                ),
            )

    return None


async def extract_recipe_from_tiktok_url(url: str) -> ExtractionResult:
    metadata = await fetch_tiktok_source_metadata(url)
    target_url = metadata.source_url
    caption = metadata.caption
    image_url = metadata.image_url
    author_handle = metadata.author_handle
    final_url = metadata.final_url

    title = _caption_title(caption, author_handle)

    parsed: Optional[ParsedCaption] = None
    gemini_error: Optional[HTTPException] = None
    try:
        parsed = await parse_caption_with_gemini(
            title=title,
            caption=caption,
            source_url=target_url,
        )
    except HTTPException as error:
        gemini_error = error

    if parsed is not None and parsed.is_complete:
        recipe = normalize_recipe(parsed.raw_recipe)
        if recipe is not None:
            return ExtractionResult(
                source_url=target_url,
                final_url=final_url,
                title=title,
                image_url=image_url,
                recipe_node_count=1,
                recipes=[recipe],
                tiktok_thumbnail_url=image_url,
                parse_status=ParseStatus.RECIPE,
            )

    if _mentions_recipe_link(caption):
        fallback = await _extract_first_recipe_link(
            caption,
            source_url=target_url,
            fallback_title=title,
            fallback_image=image_url,
        )
        if fallback is not None:
            return fallback

    if gemini_error is not None:
        raise gemini_error

    parse_reason = parsed.parse_reason if parsed is not None else None
    return ExtractionResult(
        source_url=target_url,
        final_url=final_url,
        title=title,
        image_url=image_url,
        recipe_node_count=0,
        recipes=[],
        parse_status=ParseStatus.NOT_RECIPE,
        parse_reason=parse_reason or "No recipe was found in the TikTok caption.",
    )
