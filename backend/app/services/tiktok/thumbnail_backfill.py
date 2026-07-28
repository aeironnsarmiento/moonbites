from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from ...clients.supabase_client import get_supabase_client
from ...core.config import get_settings
from .extractor import fetch_tiktok_source_metadata, is_tiktok_url
from .thumbnail_storage import (
    delete_tiktok_thumbnail,
    mirror_tiktok_thumbnail,
)


logger = logging.getLogger(__name__)
BACKFILL_BATCH_SIZE = 200
TIKTOK_IMAGE_HOST_SUFFIXES = (
    "byteoversea.com",
    "ibytedtos.com",
    "muscdn.com",
    "tiktokcdn.com",
    "tiktokcdn-eu.com",
    "tiktokcdn-us.com",
)


@dataclass(frozen=True)
class TikTokThumbnailBackfillRecord:
    id: str
    submitted_url: str
    final_url: str
    image_url: Optional[str]
    image_storage_path: Optional[str]


@dataclass(frozen=True)
class TikTokThumbnailBackfillResult:
    recipe_import_id: str
    status: str
    source_url: Optional[str] = None
    message: Optional[str] = None


@dataclass(frozen=True)
class TikTokThumbnailBackfillSummary:
    total: int = 0
    mirrored: int = 0
    would_mirror: int = 0
    skipped: int = 0
    failed: int = 0
    results: list[TikTokThumbnailBackfillResult] = field(default_factory=list)


def is_tiktok_hosted_image_url(value: str) -> bool:
    hostname = (urlparse(value.strip()).hostname or "").casefold()
    return any(
        hostname == suffix or hostname.endswith(f".{suffix}")
        for suffix in TIKTOK_IMAGE_HOST_SUFFIXES
    )


def _source_url(record: TikTokThumbnailBackfillRecord) -> Optional[str]:
    if is_tiktok_url(record.final_url):
        return record.final_url
    if is_tiktok_url(record.submitted_url):
        return record.submitted_url
    return None


def _record_from_raw(raw: dict) -> TikTokThumbnailBackfillRecord:
    return TikTokThumbnailBackfillRecord(
        id=str(raw.get("id") or ""),
        submitted_url=str(raw.get("submitted_url") or ""),
        final_url=str(raw.get("final_url") or ""),
        image_url=(
            raw.get("image_url") if isinstance(raw.get("image_url"), str) else None
        ),
        image_storage_path=(
            raw.get("image_storage_path")
            if isinstance(raw.get("image_storage_path"), str)
            else None
        ),
    )


def list_tiktok_thumbnail_backfill_records(
    *,
    recipe_import_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[TikTokThumbnailBackfillRecord]:
    settings = get_settings()
    client = get_supabase_client(settings)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to backfill thumbnails."
        )

    selected: list[TikTokThumbnailBackfillRecord] = []
    offset = 0
    while limit is None or len(selected) < limit:
        page_size = BACKFILL_BATCH_SIZE
        if limit is not None:
            page_size = min(page_size, limit - len(selected))
        query = client.table(settings.supabase_table_name).select(
            "id, submitted_url, final_url, image_url, image_storage_path"
        )
        if recipe_import_id is not None:
            query = query.eq("id", recipe_import_id).limit(1)
        else:
            query = query.order("created_at", desc=True).range(
                offset,
                offset + page_size - 1,
            )

        try:
            response = query.execute()
        except Exception as error:
            raise RuntimeError(f"Supabase thumbnail backfill read failed: {error}") from error

        raw_records = response.data or []
        for raw in raw_records:
            record = _record_from_raw(raw)
            if _source_url(record) is not None:
                selected.append(record)
                if limit is not None and len(selected) >= limit:
                    break

        if recipe_import_id is not None or len(raw_records) < page_size:
            break
        offset += page_size

    return selected


def _update_thumbnail_reference(
    record: TikTokThumbnailBackfillRecord,
    *,
    image_url: str,
    storage_path: str,
) -> None:
    settings = get_settings()
    client = get_supabase_client(settings)
    if client is None:
        raise RuntimeError(
            "Supabase is not configured yet. Add backend env vars to backfill thumbnails."
        )

    try:
        response = (
            client.table(settings.supabase_table_name)
            .update(
                {
                    "image_url": image_url,
                    "image_storage_path": storage_path,
                }
            )
            .eq("id", record.id)
            .execute()
        )
    except Exception as error:
        raise RuntimeError(f"Supabase thumbnail backfill update failed: {error}") from error

    if not response.data:
        raise RuntimeError("Recipe import disappeared before thumbnail update")


def _summary(
    results: list[TikTokThumbnailBackfillResult],
) -> TikTokThumbnailBackfillSummary:
    counts = {
        "mirrored": 0,
        "would_mirror": 0,
        "skipped": 0,
        "failed": 0,
    }
    for result in results:
        if result.status in counts:
            counts[result.status] += 1

    return TikTokThumbnailBackfillSummary(
        total=len(results),
        mirrored=counts["mirrored"],
        would_mirror=counts["would_mirror"],
        skipped=counts["skipped"],
        failed=counts["failed"],
        results=results,
    )


async def backfill_tiktok_thumbnails(
    *,
    dry_run: bool = False,
    limit: Optional[int] = None,
    recipe_import_id: Optional[str] = None,
) -> TikTokThumbnailBackfillSummary:
    records = list_tiktok_thumbnail_backfill_records(
        recipe_import_id=recipe_import_id,
        limit=limit,
    )
    results: list[TikTokThumbnailBackfillResult] = []

    if recipe_import_id is not None and not records:
        return _summary(
            [
                TikTokThumbnailBackfillResult(
                    recipe_import_id=recipe_import_id,
                    status="failed",
                    message="TikTok recipe import not found",
                )
            ]
        )

    for record in records:
        source_url = _source_url(record)
        if source_url is None:
            continue

        if record.image_storage_path:
            results.append(
                TikTokThumbnailBackfillResult(
                    recipe_import_id=record.id,
                    status="skipped",
                    source_url=source_url,
                    message="Thumbnail is already managed",
                )
            )
            continue

        if record.image_url and not is_tiktok_hosted_image_url(record.image_url):
            results.append(
                TikTokThumbnailBackfillResult(
                    recipe_import_id=record.id,
                    status="skipped",
                    source_url=source_url,
                    message="External image override was preserved",
                )
            )
            continue

        try:
            metadata = await fetch_tiktok_source_metadata(source_url)
        except Exception as error:
            results.append(
                TikTokThumbnailBackfillResult(
                    recipe_import_id=record.id,
                    status="failed",
                    source_url=source_url,
                    message=str(error),
                )
            )
            continue

        if not metadata.image_url:
            results.append(
                TikTokThumbnailBackfillResult(
                    recipe_import_id=record.id,
                    status="skipped",
                    source_url=source_url,
                    message="TikTok post has no thumbnail",
                )
            )
            continue

        if dry_run:
            results.append(
                TikTokThumbnailBackfillResult(
                    recipe_import_id=record.id,
                    status="would_mirror",
                    source_url=source_url,
                    message="Would mirror TikTok thumbnail",
                )
            )
            continue

        storage_path: Optional[str] = None
        try:
            mirrored = await mirror_tiktok_thumbnail(
                record.id,
                metadata.image_url,
            )
            storage_path = mirrored.storage_path
            _update_thumbnail_reference(
                record,
                image_url=mirrored.image_url,
                storage_path=mirrored.storage_path,
            )
        except Exception as error:
            if storage_path:
                try:
                    delete_tiktok_thumbnail(storage_path)
                except Exception as cleanup_error:
                    logger.warning(
                        "Backfill cleanup failed for recipe import %s (%s): %s",
                        record.id,
                        storage_path,
                        cleanup_error,
                    )
            results.append(
                TikTokThumbnailBackfillResult(
                    recipe_import_id=record.id,
                    status="failed",
                    source_url=source_url,
                    message=str(error),
                )
            )
            continue

        results.append(
            TikTokThumbnailBackfillResult(
                recipe_import_id=record.id,
                status="mirrored",
                source_url=source_url,
                message="Mirrored TikTok thumbnail",
            )
        )

    return _summary(results)
