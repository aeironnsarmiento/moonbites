from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Literal, Optional

import httpx
from storage3.exceptions import StorageApiError

from ...clients.supabase_client import get_supabase_client
from ...core.config import Settings, get_settings
from ..public_web import IMAGE_POLICY, PublicWebError, Resolver, safe_fetch


THUMBNAIL_BUCKET = "recipe-thumbnails"
THUMBNAIL_CACHE_SECONDS = 31_536_000
MAX_THUMBNAIL_BYTES = 5 * 1024 * 1024
MIME_EXTENSIONS = {
    "image/avif": "avif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
ThumbnailPlatform = Literal["tiktok", "instagram"]
ALLOWED_PLATFORMS: frozenset[str] = frozenset({"tiktok", "instagram"})

logger = logging.getLogger(__name__)


class SocialThumbnailStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class MirroredSocialThumbnail:
    image_url: str
    storage_path: str


def _is_existing_object_error(error: StorageApiError) -> bool:
    return str(error.status) == "409" or "already exists" in error.message.casefold()


def _require_platform(platform: str) -> None:
    if platform not in ALLOWED_PLATFORMS:
        raise SocialThumbnailStorageError(f"Unsupported thumbnail platform: {platform}")


def build_storage_path(
    platform: str, recipe_import_id: str, digest: str, extension: str
) -> str:
    _require_platform(platform)
    return f"{platform}/{recipe_import_id}/{digest}.{extension}"


def store_social_thumbnail(
    platform: str,
    recipe_import_id: str,
    content: bytes,
    mime_type: str,
    *,
    settings: Optional[Settings] = None,
) -> MirroredSocialThumbnail:
    _require_platform(platform)

    extension = MIME_EXTENSIONS.get(mime_type)
    if extension is None:
        raise SocialThumbnailStorageError(
            f"Unsupported thumbnail content type: {mime_type or 'missing'}"
        )
    if not content:
        raise SocialThumbnailStorageError("Thumbnail content was empty")
    if len(content) > MAX_THUMBNAIL_BYTES:
        raise SocialThumbnailStorageError("Thumbnail exceeds the 5 MiB limit")

    resolved_settings = settings or get_settings()
    client = get_supabase_client(resolved_settings)
    if client is None:
        raise SocialThumbnailStorageError(
            "Supabase service credentials are not configured for thumbnail storage"
        )

    digest = hashlib.sha256(content).hexdigest()
    storage_path = build_storage_path(platform, recipe_import_id, digest, extension)
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
            raise SocialThumbnailStorageError(
                f"Unable to upload thumbnail: {error.message}"
            ) from error
    except Exception as error:
        raise SocialThumbnailStorageError(f"Unable to upload thumbnail: {error}") from error

    return MirroredSocialThumbnail(
        image_url=bucket.get_public_url(storage_path),
        storage_path=storage_path,
    )


async def mirror_social_thumbnail(
    platform: str,
    recipe_import_id: str,
    source_url: str,
    *,
    deadline_seconds: float,
    settings: Optional[Settings] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
    resolver: Optional[Resolver] = None,
) -> MirroredSocialThumbnail:
    """Fetch a provider-hosted thumbnail through the SSRF-safe seam and store
    it under ``{platform}/{recipe_import_id}/``. Raises only
    SocialThumbnailStorageError; the caller decides whether that is fatal."""
    try:
        fetched = await safe_fetch(
            source_url,
            IMAGE_POLICY,
            deadline_seconds=deadline_seconds,
            transport=transport,
            resolver=resolver,
        )
    except PublicWebError as error:
        raise SocialThumbnailStorageError(str(error)) from error

    return store_social_thumbnail(
        platform,
        recipe_import_id,
        fetched.body,
        fetched.content_type,
        settings=settings,
    )


def delete_social_thumbnail(
    storage_path: str, *, settings: Optional[Settings] = None
) -> None:
    if not storage_path:
        return

    resolved_settings = settings or get_settings()
    client = get_supabase_client(resolved_settings)
    if client is None:
        raise SocialThumbnailStorageError(
            "Supabase service credentials are not configured for thumbnail storage"
        )

    try:
        client.storage.from_(THUMBNAIL_BUCKET).remove([storage_path])
    except Exception as error:
        raise SocialThumbnailStorageError(f"Unable to delete thumbnail: {error}") from error


def delete_social_thumbnail_best_effort(
    storage_path: Optional[str],
    *,
    context: str,
    settings: Optional[Settings] = None,
) -> None:
    """Delete a mirrored thumbnail whose row was never committed, or was just
    replaced. Failure here must never change the caller's own outcome, so it
    only logs; the periodic thumbnail audit is the backstop."""
    if not storage_path:
        return
    try:
        delete_social_thumbnail(storage_path, settings=settings)
    except Exception as error:
        logger.warning(
            "Managed thumbnail cleanup failed for %s (%s): %s",
            context,
            storage_path,
            error,
        )
