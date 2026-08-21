from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from app.repositories.recipe_imports import update_recipe_metadata
from app.schemas.extract import (
    NormalizedRecipe,
    RecipeImportRecord,
    UpdateRecipeMetadataRequest,
)


class _Response:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table, kind):
        self.table = table
        self.kind = kind
        self.payload = None

    def select(self, _cols):
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def eq(self, _column, _value):
        return self

    def limit(self, _n):
        return self

    def execute(self):
        if self.kind == "select":
            return _Response(
                [
                    {
                        "image_url": self.table.stored_image_url,
                        "image_storage_path": self.table.stored_storage_path,
                    }
                ]
            )
        self.table.update_calls.append(self.payload)
        return _Response([{**self.table.updated_row, **(self.payload or {})}])


class _FakeTable:
    def __init__(self, stored_image_url, stored_storage_path, updated_row):
        self.stored_image_url = stored_image_url
        self.stored_storage_path = stored_storage_path
        self.updated_row = updated_row
        self.update_calls: list[dict] = []


class _FakeClient:
    def __init__(self, table):
        self._table = table

    def table(self, _name):
        return self

    def select(self, cols):
        return _FakeQuery(self._table, "select").select(cols)

    def update(self, payload):
        return _FakeQuery(self._table, "update").update(payload)


def _record(**overrides) -> RecipeImportRecord:
    fields = {
        "id": "abc",
        "submitted_url": "https://www.instagram.com/reel/DZuzc9PNedT/",
        "final_url": "https://www.instagram.com/reel/DZuzc9PNedT/",
        "page_title": "Miso Salmon Rice",
        "recipes_json": [
            NormalizedRecipe(
                name="Miso Salmon Rice",
                ingredients=["1 cup rice"],
                instructions=["Cook."],
            )
        ],
        "image_url": "https://cdn.example/instagram/abc.jpg",
        "linked_recipe_url": "https://tasty.co/recipe/miso-salmon-rice",
        "created_at": datetime.now(timezone.utc),
    }
    fields.update(overrides)
    return RecipeImportRecord(**fields)


def test_identity_change_clears_managed_thumbnail_even_when_image_url_field_unchanged():
    existing = _record()
    table = _FakeTable(
        stored_image_url=existing.image_url,
        stored_storage_path="instagram/abc/digest.jpg",
        updated_row=existing.model_dump(mode="json"),
    )
    client = _FakeClient(table)

    with (
        patch("app.repositories.recipe_imports.get_settings"),
        patch("app.repositories.recipe_imports._get_write_client", return_value=client),
        patch("app.repositories.recipe_imports.get_recipe_import", return_value=existing),
        patch(
            "app.repositories.recipe_imports.delete_tiktok_thumbnail"
        ) as delete_thumb,
    ):
        update_recipe_metadata(
            "abc",
            UpdateRecipeMetadataRequest(
                title="Miso Salmon Rice",
                recipe_yield=None,
                image_url=existing.image_url,
                source_url="https://www.instagram.com/reel/Daa0ZKGOuZb/",
            ),
        )

    assert table.update_calls[0]["image_storage_path"] is None
    assert table.update_calls[0]["linked_recipe_url"] is None
    delete_thumb.assert_called_once_with("instagram/abc/digest.jpg")


def test_equivalent_url_form_preserves_managed_thumbnail_and_linked_recipe_url():
    existing = _record()
    table = _FakeTable(
        stored_image_url=existing.image_url,
        stored_storage_path="instagram/abc/digest.jpg",
        updated_row=existing.model_dump(mode="json"),
    )
    client = _FakeClient(table)

    with (
        patch("app.repositories.recipe_imports.get_settings"),
        patch("app.repositories.recipe_imports._get_write_client", return_value=client),
        patch("app.repositories.recipe_imports.get_recipe_import", return_value=existing),
        patch(
            "app.repositories.recipe_imports.delete_tiktok_thumbnail"
        ) as delete_thumb,
    ):
        update_recipe_metadata(
            "abc",
            UpdateRecipeMetadataRequest(
                title="Miso Salmon Rice",
                recipe_yield=None,
                image_url=existing.image_url,
                source_url="https://instagram.com/reel/DZuzc9PNedT?igsh=abc",
            ),
        )

    assert "image_storage_path" not in table.update_calls[0]
    assert "linked_recipe_url" not in table.update_calls[0]
    delete_thumb.assert_not_called()
