from __future__ import annotations

from datetime import datetime, timezone

from app.repositories.recipe_imports import (
    _build_refetched_recipe_update_payload,
    _normalize_row_layout,
    _reconcile_row_layout,
    _sanitize_record,
)
from app.schemas.extract import NormalizedRecipe, RecipeImportRecord

ROWS = ["a", "b", "c"]


def _entry(source: int | None, text: str | None = None) -> dict:
    return {"source": source, "text": text}


def test_normalize_converts_legacy_index_edits_to_layout():
    assert _normalize_row_layout({"1": "B"}, ROWS) == [
        _entry(0),
        _entry(1, "B"),
        _entry(2),
    ]


def test_normalize_appends_legacy_edits_past_the_original_rows():
    assert _normalize_row_layout({"3": "d"}, ROWS) == [
        _entry(0),
        _entry(1),
        _entry(2),
        _entry(None, "d"),
    ]


def test_normalize_returns_none_for_identity_layouts():
    assert _normalize_row_layout(None, ROWS) is None
    assert _normalize_row_layout({}, ROWS) is None
    assert _normalize_row_layout([_entry(0), _entry(1, "b"), _entry(2)], ROWS) is None


def test_normalize_keeps_deletes_reorders_and_additions():
    layout = [_entry(2), _entry(None, "new"), _entry(0, "A")]

    assert _normalize_row_layout(layout, ROWS) == layout


def test_normalize_drops_invalid_duplicate_and_blank_entries():
    layout = [
        _entry(0),
        _entry(0, "dupe"),
        _entry(7),
        _entry(None, "  "),
        _entry(None),
        _entry(1, ""),
        "junk",
        _entry(2),
    ]

    assert _normalize_row_layout(layout, ROWS) == [_entry(0), _entry(2)]


def test_reconcile_keeps_added_rows_and_drops_rows_removed_upstream():
    layout = [_entry(1, "B"), _entry(None, "added"), _entry(2)]

    assert _reconcile_row_layout(layout, ["x", "y"]) == [
        _entry(1, "B"),
        _entry(None, "added"),
    ]


def test_reconcile_inserts_new_upstream_rows_after_last_original_row():
    layout = [_entry(1), _entry(0), _entry(None, "added")]

    assert _reconcile_row_layout(layout, ["a", "b", "c", "d"], old_row_count=2) == [
        _entry(1),
        _entry(0),
        _entry(2),
        _entry(3),
        _entry(None, "added"),
    ]


def test_sanitize_record_converts_legacy_overrides():
    record = _sanitize_record(
        {
            "id": "abc",
            "submitted_url": "https://old.test",
            "final_url": "https://old.test",
            "recipes_json": [
                NormalizedRecipe(
                    name="Soup", ingredients=["a", "b"], instructions=["s1"]
                ).model_dump()
            ],
            "recipe_overrides_json": {
                "0": {"ingredients": {"0": "A"}, "instructions": {}},
                "5": {"ingredients": {"0": "stale"}, "instructions": {}},
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    assert record.model_dump()["recipe_overrides_json"] == {
        "0": {
            "ingredients": [_entry(0, "A"), _entry(1)],
            "instructions": None,
        }
    }


def test_refetch_payload_keeps_added_rows():
    record = RecipeImportRecord(
        id="abc",
        submitted_url="https://old.test",
        final_url="https://old.test",
        recipes_json=[
            NormalizedRecipe(name="Soup", ingredients=["a", "b"], instructions=["s1"])
        ],
        recipe_overrides_json={
            "0": {
                "ingredients": [_entry(1), _entry(None, "added")],
                "instructions": None,
            }
        },
        created_at=datetime.now(timezone.utc),
    )

    payload = _build_refetched_recipe_update_payload(
        record,
        title="Soup",
        image_url=None,
        recipes=[
            NormalizedRecipe(
                name="Soup", ingredients=["a", "b", "c"], instructions=["s1"]
            )
        ],
    )

    assert payload["recipe_overrides_json"] == {
        "0": {
            "ingredients": [_entry(1), _entry(2), _entry(None, "added")],
            "instructions": None,
        }
    }
