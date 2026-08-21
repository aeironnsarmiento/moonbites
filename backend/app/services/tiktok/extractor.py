from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from ...core.config import Settings, get_settings
from ..blog.extractor import normalize_url
from ..extraction_types import ExtractionResult
from ..http_utils import build_request_headers, get_with_403_retry
from ..social.caption_recipe import CaptionPost, extract_recipe_from_caption


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


async def extract_recipe_from_tiktok_url(url: str) -> ExtractionResult:
    metadata = await fetch_tiktok_source_metadata(url)
    return await extract_recipe_from_caption(
        CaptionPost(
            source_url=metadata.source_url,
            final_url=metadata.final_url,
            title=_caption_title(metadata.caption, metadata.author_handle),
            caption=metadata.caption,
            image_url=metadata.image_url,
        ),
        not_recipe_reason="No recipe was found in the TikTok caption.",
        mirror_provider_thumbnail=True,
    )
