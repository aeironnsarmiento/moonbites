from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from ...core.config import Settings, get_settings
from ..public_web import IMAGE_POLICY, PublicWebError, Resolver, safe_fetch
from ..social.thumbnail_storage import (
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


async def mirror_tiktok_thumbnail(
    recipe_import_id: str,
    source_url: str,
    *,
    settings: Optional[Settings] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
    resolver: Optional[Resolver] = None,
) -> MirroredTikTokThumbnail:
    resolved_settings = settings or get_settings()

    kwargs: dict = {"deadline_seconds": resolved_settings.request_timeout_seconds}
    if transport is not None:
        kwargs["transport"] = transport
    if resolver is not None:
        kwargs["resolver"] = resolver

    try:
        fetched = await safe_fetch(source_url, IMAGE_POLICY, **kwargs)
    except PublicWebError as error:
        raise TikTokThumbnailStorageError(str(error)) from error

    try:
        mirrored = store_social_thumbnail(
            "tiktok",
            recipe_import_id,
            fetched.body,
            fetched.content_type,
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
