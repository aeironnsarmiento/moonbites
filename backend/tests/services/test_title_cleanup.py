from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.schemas.extract import (
    DisplayTitleSource,
    NormalizedRecipe,
    RecipeImportRecord,
)
from app.services.display_titles import DisplayTitle
from app.services.gemini.title_generator import BatchTitleResult
from app.services.title_cleanup import preview_title_cleanup


def _recipe(name: str = "Garlic Noodles") -> NormalizedRecipe:
    return NormalizedRecipe(
        name=name,
        ingredients=["1 cup rice"],
        instructions=["Cook."],
    )


def _record(
    record_id: str = "abc",
    display_title: str | None = None,
    display_title_source: DisplayTitleSource = DisplayTitleSource.fallback,
    submitted_url: str = "https://old.test/source",
    page_title: str | None = "The BEST Garlic Noodles!!",
    created_at: datetime | None = None,
) -> RecipeImportRecord:
    return RecipeImportRecord(
        id=record_id,
        submitted_url=submitted_url,
        final_url=submitted_url,
        page_title=page_title,
        display_title=display_title,
        display_title_source=display_title_source,
        times_cooked=0,
        recipes_json=[_recipe()],
        recipe_overrides_json={},
        image_url=None,
        is_favorite=False,
        servings=None,
        created_at=created_at or datetime.now(timezone.utc),
    )


class _FakeGenerator:
    """Records what the cleanup service actually sends to Gemini."""

    def __init__(self, batch: BatchTitleResult | None = None) -> None:
        self._batch = batch
        self.calls = 0
        self.items: list | None = None

    async def __call__(self, items):
        self.calls += 1
        self.items = items
        if self._batch is not None:
            return self._batch
        return BatchTitleResult(
            titles=[
                DisplayTitle(value="Garlic Noodles Supper", source="ai")
                for _ in items
            ]
        )


def _preview(records, batch=None, limit=10):
    generator = _FakeGenerator(batch)

    with (
        patch(
            "app.services.title_cleanup.list_recipe_import_records_for_title_cleanup",
            return_value=records,
        ) as reader,
        patch("app.services.title_cleanup.generate_display_titles", generator),
    ):
        result = asyncio.run(preview_title_cleanup(limit=limit))

    return result, reader, generator


def test_preview_suggests_a_title_for_each_eligible_record():
    records = [_record(record_id="a"), _record(record_id="b")]

    result, _, generator = _preview(records)

    # R11: one batched call, not one per recipe.
    assert generator.calls == 1
    assert len(result.suggestions) == 2
    assert result.suggestions[0].suggested_title == "Garlic Noodles Supper"
    assert result.suggestions[0].current_title == "Garlic Noodles"


def test_preview_skips_a_user_titled_record():
    # Covers AE3 and R13.
    records = [
        _record(
            record_id="edited",
            display_title="Mom's Adobo",
            display_title_source=DisplayTitleSource.user,
        ),
        _record(record_id="fresh"),
    ]

    result, _, generator = _preview(records)

    assert [item.recipe_import_id for item in result.skipped] == ["edited"]
    assert "titled this recipe" in result.skipped[0].reason
    assert [item.recipe_import_id for item in result.suggestions] == ["fresh"]
    # The skipped record is never sent to Gemini.
    assert len(generator.items) == 1


def test_preview_skips_a_manual_record():
    # R10: manual recipes keep the name the user gave them.
    records = [_record(record_id="manual", submitted_url="manual://abc-123")]

    result, _, generator = _preview(records)

    assert [item.recipe_import_id for item in result.skipped] == ["manual"]
    assert result.suggestions == []


def test_preview_makes_no_call_when_every_record_is_skipped():
    records = [
        _record(record_id="a", display_title_source=DisplayTitleSource.user),
        _record(record_id="b", submitted_url="manual://b"),
    ]

    result, _, generator = _preview(records)

    assert generator.calls == 0
    assert result.suggestions == []
    assert len(result.skipped) == 2


def test_preview_cursor_tracks_the_last_record_read_not_the_last_suggested():
    # Deriving the cursor from suggestions would re-read skipped rows forever.
    oldest = datetime.now(timezone.utc) - timedelta(days=5)
    records = [
        _record(record_id="a"),
        _record(
            record_id="skipped-last",
            display_title_source=DisplayTitleSource.user,
            created_at=oldest,
        ),
    ]

    result, _, _ = _preview(records, limit=2)

    assert result.next_cursor == oldest.isoformat()


def test_preview_has_no_next_cursor_on_a_short_page():
    result, _, _ = _preview([_record()], limit=10)

    assert result.next_cursor is None


def test_preview_surfaces_a_degraded_batch():
    records = [_record()]
    batch = BatchTitleResult(
        titles=[DisplayTitle(value="Garlic Noodles", source="fallback")],
        degraded_reason="The title generator is busy — try again shortly.",
    )

    result, _, _ = _preview(records, batch=batch)

    # The admin must not be shown cleaned source titles disguised as AI work.
    assert result.degraded_reason == "The title generator is busy — try again shortly."
    assert result.suggestions[0].source == DisplayTitleSource.fallback


def test_preview_forwards_the_limit_to_the_reader():
    with (
        patch(
            "app.services.title_cleanup.list_recipe_import_records_for_title_cleanup",
            return_value=[],
        ) as reader,
    ):
        asyncio.run(preview_title_cleanup(cursor="2026-01-01T00:00:00+00:00", limit=5))

    assert reader.call_args.kwargs["batch_size"] == 5
    assert reader.call_args.kwargs["cursor"] == "2026-01-01T00:00:00+00:00"


def test_preview_of_an_empty_page_returns_nothing():
    result, _, generator = _preview([])

    assert result.suggestions == []
    assert result.skipped == []
    assert result.next_cursor is None
    assert generator.calls == 0
