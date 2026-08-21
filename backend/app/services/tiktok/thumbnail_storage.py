from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx

from ...core.config import Settings, get_settings
from ..http_utils import build_request_headers
from ..social.thumbnail_storage import (
    MAX_THUMBNAIL_BYTES,
    MIME_EXTENSIONS,
    SocialThumbnailStorageError,
    delete_social_thumbnail,
    store_social_thumbnail,
)


class TikTokThumbnailStorageError(SocialThumbnailStorageError):
    pass


@dataclass(frozen=True)
class MirroredTikTokThumbnail:
    image_url: str
    storage_path: str


def _validate_source_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        raise TikTokThumbnailStorageError(
            "TikTok thumbnail URL must be a valid HTTPS URL"
        )
    return value.strip()


async def _download_thumbnail(
    source_url: str,
    settings: Settings,
) -> tuple[bytes, str, str]:
    url = _validate_source_url(source_url)

    try:
        async with httpx.AsyncClient(
            headers=build_request_headers(settings),
            follow_redirects=True,
            timeout=settings.request_timeout_seconds,
        ) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                mime_type = content_type.split(";", 1)[0].strip().casefold()
                extension = MIME_EXTENSIONS.get(mime_type)
                if extension is None:
                    raise TikTokThumbnailStorageError(
                        f"Unsupported TikTok thumbnail content type: {mime_type or 'missing'}"
                    )

                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        declared_size = int(content_length)
                    except ValueError:
                        declared_size = 0
                    if declared_size > MAX_THUMBNAIL_BYTES:
                        raise TikTokThumbnailStorageError(
                            "TikTok thumbnail exceeds the 5 MiB limit"
                        )

                chunks: list[bytes] = []
                total_size = 0
                async for chunk in response.aiter_bytes():
                    total_size += len(chunk)
                    if total_size > MAX_THUMBNAIL_BYTES:
                        raise TikTokThumbnailStorageError(
                            "TikTok thumbnail exceeds the 5 MiB limit"
                        )
                    chunks.append(chunk)
    except TikTokThumbnailStorageError:
        raise
    except httpx.HTTPError as error:
        raise TikTokThumbnailStorageError(
            f"Unable to download TikTok thumbnail: {error}"
        ) from error

    content = b"".join(chunks)
    if not content:
        raise TikTokThumbnailStorageError("TikTok thumbnail response was empty")

    return content, mime_type, extension


async def mirror_tiktok_thumbnail(
    recipe_import_id: str,
    source_url: str,
    *,
    settings: Optional[Settings] = None,
) -> MirroredTikTokThumbnail:
    resolved_settings = settings or get_settings()
    content, mime_type, _extension = await _download_thumbnail(
        source_url,
        resolved_settings,
    )

    try:
        mirrored = store_social_thumbnail(
            "tiktok",
            recipe_import_id,
            content,
            mime_type,
            settings=resolved_settings,
        )
    except SocialThumbnailStorageError as error:
        raise TikTokThumbnailStorageError(str(error)) from error

    return MirroredTikTokThumbnail(
        image_url=mirrored.image_url, storage_path=mirrored.storage_path
    )


def delete_tiktok_thumbnail(
    storage_path: str,
    *,
    settings: Optional[Settings] = None,
) -> None:
    try:
        delete_social_thumbnail(storage_path, settings=settings)
    except SocialThumbnailStorageError as error:
        raise TikTokThumbnailStorageError(str(error)) from error
