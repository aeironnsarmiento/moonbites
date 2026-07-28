from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx
from storage3.exceptions import StorageApiError

from ...clients.supabase_client import get_supabase_client
from ...core.config import Settings, get_settings
from ..http_utils import build_request_headers


THUMBNAIL_BUCKET = "recipe-thumbnails"
MAX_THUMBNAIL_BYTES = 5 * 1024 * 1024
THUMBNAIL_CACHE_SECONDS = 31_536_000
MIME_EXTENSIONS = {
    "image/avif": "avif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class TikTokThumbnailStorageError(RuntimeError):
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


def _is_existing_object_error(error: StorageApiError) -> bool:
    return str(error.status) == "409" or "already exists" in error.message.casefold()


async def mirror_tiktok_thumbnail(
    recipe_import_id: str,
    source_url: str,
    *,
    settings: Optional[Settings] = None,
) -> MirroredTikTokThumbnail:
    resolved_settings = settings or get_settings()
    client = get_supabase_client(resolved_settings)
    if client is None:
        raise TikTokThumbnailStorageError(
            "Supabase service credentials are not configured for thumbnail storage"
        )

    content, mime_type, extension = await _download_thumbnail(
        source_url,
        resolved_settings,
    )
    digest = hashlib.sha256(content).hexdigest()
    storage_path = f"tiktok/{recipe_import_id}/{digest}.{extension}"
    bucket = client.storage.from_(THUMBNAIL_BUCKET)

    try:
        bucket.upload(
            path=storage_path,
            file=content,
            file_options={
                "cache-control": str(THUMBNAIL_CACHE_SECONDS),
                "content-type": mime_type,
                "upsert": "false",
            },
        )
    except StorageApiError as error:
        if not _is_existing_object_error(error):
            raise TikTokThumbnailStorageError(
                f"Unable to upload TikTok thumbnail: {error.message}"
            ) from error
    except Exception as error:
        raise TikTokThumbnailStorageError(
            f"Unable to upload TikTok thumbnail: {error}"
        ) from error

    return MirroredTikTokThumbnail(
        image_url=bucket.get_public_url(storage_path),
        storage_path=storage_path,
    )


def delete_tiktok_thumbnail(
    storage_path: str,
    *,
    settings: Optional[Settings] = None,
) -> None:
    if not storage_path:
        return

    resolved_settings = settings or get_settings()
    client = get_supabase_client(resolved_settings)
    if client is None:
        raise TikTokThumbnailStorageError(
            "Supabase service credentials are not configured for thumbnail storage"
        )

    try:
        client.storage.from_(THUMBNAIL_BUCKET).remove([storage_path])
    except Exception as error:
        raise TikTokThumbnailStorageError(
            f"Unable to delete TikTok thumbnail: {error}"
        ) from error
