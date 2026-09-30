from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.social.thumbnail_storage import MirroredSocialThumbnail
from app.services.tiktok.thumbnail_backfill import (
    TikTokThumbnailBackfillRecord,
    backfill_tiktok_thumbnails,
)


RECORD = TikTokThumbnailBackfillRecord(
    id="recipe-1",
    submitted_url="https://www.tiktok.com/@cook/video/123",
    final_url="https://www.tiktok.com/@cook/video/123",
    image_url="https://p16.tiktokcdn.com/old.jpg",
    image_storage_path=None,
)
MIRRORED = MirroredSocialThumbnail(
    image_url="https://cdn.example/tiktok/recipe-1/digest.jpg",
    storage_path="tiktok/recipe-1/digest.jpg",
)
MODULE = "app.services.tiktok.thumbnail_backfill"


def _run_backfill(*, update_error: Exception | None = None):
    metadata = SimpleNamespace(image_url="https://p16.tiktokcdn.com/new.jpg")
    with (
        patch(f"{MODULE}.get_settings") as get_settings,
        patch(
            f"{MODULE}.list_tiktok_thumbnail_backfill_records",
            return_value=[RECORD],
        ),
        patch(
            f"{MODULE}.fetch_tiktok_source_metadata",
            new=AsyncMock(return_value=metadata),
        ),
        patch(
            f"{MODULE}.mirror_social_thumbnail",
            new=AsyncMock(return_value=MIRRORED),
        ) as mirror,
        patch(
            f"{MODULE}._update_thumbnail_reference", side_effect=update_error
        ) as update,
        patch(f"{MODULE}.delete_social_thumbnail_best_effort") as delete,
    ):
        get_settings.return_value.request_timeout_seconds = 15.0
        summary = asyncio.run(backfill_tiktok_thumbnails())
    return summary, mirror, update, delete


def test_backfill_mirrors_a_tiktok_hosted_image_and_updates_the_row():
    summary, mirror, update, delete = _run_backfill()

    assert summary.mirrored == 1
    assert mirror.call_args.args == (
        "tiktok",
        "recipe-1",
        "https://p16.tiktokcdn.com/new.jpg",
    )
    assert mirror.call_args.kwargs["deadline_seconds"] == 15.0
    update.assert_called_once_with(
        RECORD, image_url=MIRRORED.image_url, storage_path=MIRRORED.storage_path
    )
    delete.assert_not_called()


def test_backfill_deletes_the_mirrored_object_when_the_update_fails():
    summary, _mirror, _update, delete = _run_backfill(
        update_error=RuntimeError("Recipe import disappeared before thumbnail update")
    )

    assert summary.failed == 1
    assert summary.results[0].message == (
        "Recipe import disappeared before thumbnail update"
    )
    delete.assert_called_once()
    assert delete.call_args.args[0] == "tiktok/recipe-1/digest.jpg"
