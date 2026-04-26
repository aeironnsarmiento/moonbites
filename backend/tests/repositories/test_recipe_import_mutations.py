from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.repositories.recipe_imports import (
    RecipeWriteDeniedError,
    delete_recipe_import,
    toggle_favorite,
)
from app.schemas.extract import NormalizedRecipe, RecipeImportRecord


class _UpdateQuery:
    def __init__(self, response_data: list[dict]):
        self.response_data = response_data

    def update(self, _payload: dict):
        return self

    def eq(self, _column: str, _value: str):
        return self

    def execute(self):
        return type("Response", (), {"data": self.response_data})()


class _DeleteQuery:
    def __init__(self, response_data: list[dict], error: Exception | None = None):
        self.response_data = response_data
        self.error = error

    def delete(self):
        return self

    def eq(self, _column: str, _value: str):
        return self

    def execute(self):
        if self.error is not None:
            raise self.error
        return type("Response", (), {"data": self.response_data})()


class _Client:
    def __init__(self, response_data: list[dict]):
        self.response_data = response_data

    def table(self, _table_name: str):
        return _UpdateQuery(self.response_data)


class _DeleteClient:
    def __init__(self, response_data: list[dict], error: Exception | None = None):
        self.response_data = response_data
        self.error = error

    def table(self, _table_name: str):
        return _DeleteQuery(self.response_data, self.error)


def _recipe() -> NormalizedRecipe:
    return NormalizedRecipe(
        name="Miso Cookies",
        ingredients=["1 cup flour"],
        instructions=["Bake."],
    )


def _record_dict(*, is_favorite: bool) -> dict:
    return {
        "id": "recipe-1",
        "submitted_url": "https://example.com/miso-cookies",
        "final_url": "https://example.com/miso-cookies",
        "page_title": "Miso Cookies",
        "recipe_count": 1,
        "times_cooked": 0,
        "recipes_json": [_recipe().model_dump()],
        "recipe_overrides_json": {},
        "image_url": None,
        "is_favorite": is_favorite,
        "servings": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _record(*, is_favorite: bool) -> RecipeImportRecord:
    return RecipeImportRecord.model_validate(_record_dict(is_favorite=is_favorite))


def test_toggle_favorite_returns_record_from_update_response():
    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_write_client") as get_write_client,
        patch("app.repositories.recipe_imports.get_recipe_import") as get_recipe_import,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_write_client.return_value = _Client([_record_dict(is_favorite=True)])
        get_recipe_import.return_value = _record(is_favorite=False)

        record = toggle_favorite("recipe-1", access_token="admin-token")

    assert record is not None
    assert record.is_favorite is True


def test_toggle_favorite_raises_when_update_matches_no_rows_after_existing_record():
    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_write_client") as get_write_client,
        patch("app.repositories.recipe_imports.get_recipe_import") as get_recipe_import,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_write_client.return_value = _Client([])
        get_recipe_import.return_value = _record(is_favorite=False)

        with pytest.raises(RecipeWriteDeniedError, match="public.recipe_admins"):
            toggle_favorite("recipe-1", access_token="admin-token")


def test_delete_recipe_import_returns_true_when_delete_returns_deleted_row():
    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_write_client") as get_write_client,
        patch("app.repositories.recipe_imports.get_recipe_import") as get_recipe_import,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_write_client.return_value = _DeleteClient([_record_dict(is_favorite=False)])
        get_recipe_import.return_value = _record(is_favorite=False)

        deleted = delete_recipe_import("recipe-1", access_token="admin-token")

    assert deleted is True


def test_delete_recipe_import_returns_false_when_record_missing_before_delete():
    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_write_client") as get_write_client,
        patch("app.repositories.recipe_imports.get_recipe_import") as get_recipe_import,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_write_client.return_value = _DeleteClient([_record_dict(is_favorite=False)])
        get_recipe_import.return_value = None

        deleted = delete_recipe_import("recipe-1", access_token="admin-token")

    assert deleted is False


def test_delete_recipe_import_returns_false_when_delete_races_with_other_delete():
    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_write_client") as get_write_client,
        patch("app.repositories.recipe_imports.get_recipe_import") as get_recipe_import,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_write_client.return_value = _DeleteClient([])
        get_recipe_import.side_effect = [_record(is_favorite=False), None]

        deleted = delete_recipe_import("recipe-1", access_token="admin-token")

    assert deleted is False


def test_delete_recipe_import_raises_when_delete_matches_no_rows_but_record_remains():
    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_write_client") as get_write_client,
        patch("app.repositories.recipe_imports.get_recipe_import") as get_recipe_import,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_write_client.return_value = _DeleteClient([])
        get_recipe_import.side_effect = [
            _record(is_favorite=False),
            _record(is_favorite=False),
        ]

        with pytest.raises(RecipeWriteDeniedError, match="public.recipe_admins"):
            delete_recipe_import("recipe-1", access_token="admin-token")


def test_delete_recipe_import_wraps_supabase_delete_errors():
    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_write_client") as get_write_client,
        patch("app.repositories.recipe_imports.get_recipe_import") as get_recipe_import,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_write_client.return_value = _DeleteClient([], error=Exception("boom"))
        get_recipe_import.return_value = _record(is_favorite=False)

        with pytest.raises(RuntimeError, match="Supabase delete failed: boom"):
            delete_recipe_import("recipe-1", access_token="admin-token")
