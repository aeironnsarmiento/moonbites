from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

from app.repositories.recipe_imports import save_recipe_import
from app.schemas.extract import NormalizedRecipe, RecipeImportRecord


class _Response:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, table):
        self._table = table
        self._in_column = None
        self._insert_payload = None

    def select(self, _cols):
        return self

    def in_(self, column, values):
        self._in_column = column
        self._in_values = values
        self._table.client.in_queries.append((column, values))
        return self

    def eq(self, _column, _value):
        return self

    def limit(self, _n):
        return self

    def insert(self, payload):
        self._insert_payload = payload
        return self

    def execute(self):
        return self._table._execute(self)


class _FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name

    def select(self, cols):
        return _FakeQuery(self).select(cols)

    def insert(self, payload):
        return _FakeQuery(self).insert(payload)

    def _execute(self, query):
        if query._insert_payload is not None:
            self.client.insert_calls.append(query._insert_payload)
            if self.client.insert_error is not None:
                raise self.client.insert_error
            return _Response([query._insert_payload])
        return _Response(list(self.client.existing_by_url))


class _FakeClient:
    def __init__(self):
        self.existing_by_url: list[dict] = []
        self.insert_error: Exception | None = None
        self.insert_calls: list[dict] = []
        self.in_queries: list[tuple[str, list[str]]] = []

    def table(self, name):
        return _FakeTable(self, name)


def _recipe() -> NormalizedRecipe:
    return NormalizedRecipe(
        name="Miso Salmon Rice",
        ingredients=["1 cup rice"],
        instructions=["Cook rice."],
    )


def _run(client, **kwargs):
    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch(
            "app.repositories.recipe_imports._get_write_client", return_value=client
        ),
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        return asyncio.run(
            save_recipe_import(
                submitted_url=kwargs.pop(
                    "submitted_url", "https://www.instagram.com/reel/abc123/"
                ),
                final_url=kwargs.pop(
                    "final_url", "https://www.instagram.com/reel/abc123/"
                ),
                title=kwargs.pop("title", "Miso Salmon Rice"),
                recipes=kwargs.pop("recipes", [_recipe()]),
                **kwargs,
            )
        )


def test_save_recipe_import_returns_generated_id_on_success():
    client = _FakeClient()

    result = _run(client)

    assert result.saved is True
    assert result.id is not None
    assert client.insert_calls[0]["id"] == result.id


def test_save_recipe_import_persists_linked_recipe_url():
    client = _FakeClient()

    _run(client, linked_recipe_url="https://tasty.co/recipe/miso-salmon-rice")

    assert (
        client.insert_calls[0]["linked_recipe_url"]
        == "https://tasty.co/recipe/miso-salmon-rice"
    )


def test_save_recipe_import_existing_duplicate_returns_existing_id():
    client = _FakeClient()
    client.existing_by_url = [{"id": "existing-recipe-1"}]

    result = _run(client)

    assert result.saved is True
    assert result.id == "existing-recipe-1"
    assert client.insert_calls == []


def test_save_recipe_import_checks_canonical_columns_not_raw_urls():
    # Regression guard: the duplicate check used to query Supabase on the raw
    # submitted/final URLs, so canonicalization ran only after the query
    # already missed a tracking-param variant of a stored row. It must query
    # the canonical columns instead.
    client = _FakeClient()

    _run(client)

    assert client.in_queries
    for column, _values in client.in_queries:
        assert column in ("submitted_url_canonical", "final_url_canonical")


def test_save_recipe_import_detects_duplicate_with_tracking_params_stripped():
    client = _FakeClient()
    client.existing_by_url = [{"id": "existing-recipe-1"}]

    result = _run(
        client,
        submitted_url="https://www.instagram.com/reel/abc123/?utm_source=ig",
        final_url="https://www.instagram.com/reel/abc123/?utm_source=ig",
    )

    assert result.saved is True
    assert result.id == "existing-recipe-1"
    assert client.insert_calls == []


def test_save_recipe_import_writes_canonical_columns_on_insert():
    client = _FakeClient()

    _run(
        client,
        submitted_url="https://www.instagram.com/reel/abc123/?utm_source=ig",
        final_url="https://www.instagram.com/reel/abc123/",
    )

    inserted = client.insert_calls[0]
    assert inserted["submitted_url_canonical"] == "https://www.instagram.com/reel/abc123"
    assert inserted["final_url_canonical"] == "https://www.instagram.com/reel/abc123"


def test_save_recipe_import_uses_managed_image_storage_path_without_mirroring_tiktok():
    client = _FakeClient()

    with patch(
        "app.repositories.recipe_imports.mirror_tiktok_thumbnail"
    ) as mirror:
        result = _run(
            client,
            image_url="https://cdn.example/instagram/recipe.jpg",
            managed_image_storage_path="instagram/recipe.jpg",
        )

    mirror.assert_not_called()
    assert result.image_url == "https://cdn.example/instagram/recipe.jpg"
    assert client.insert_calls[0]["image_storage_path"] == "instagram/recipe.jpg"


def test_save_recipe_import_deletes_provisional_thumbnail_on_duplicate_key_conflict():
    client = _FakeClient()
    client.insert_error = RuntimeError('duplicate key value violates unique constraint "x"')

    with patch(
        "app.repositories.recipe_imports.delete_tiktok_thumbnail"
    ) as delete_thumb:
        result = _run(
            client,
            image_url="https://cdn.example/instagram/recipe.jpg",
            managed_image_storage_path="instagram/recipe.jpg",
        )

    assert result.saved is True
    delete_thumb.assert_called_once_with("instagram/recipe.jpg")


def test_save_recipe_import_ambiguous_failure_with_committed_row_keeps_thumbnail():
    client = _FakeClient()
    client.insert_error = RuntimeError("connection reset by peer")
    committed = RecipeImportRecord(
        id="row-1",
        submitted_url="https://www.instagram.com/reel/abc123/",
        final_url="https://www.instagram.com/reel/abc123/",
        recipes_json=[_recipe()],
        image_url="https://cdn.example/instagram/recipe.jpg",
        created_at=datetime.now(timezone.utc),
    )

    with (
        patch(
            "app.repositories.recipe_imports.delete_tiktok_thumbnail"
        ) as delete_thumb,
        patch(
            "app.repositories.recipe_imports.get_recipe_import",
            return_value=committed,
        ),
    ):
        result = _run(
            client,
            image_url="https://cdn.example/instagram/recipe.jpg",
            managed_image_storage_path="instagram/recipe.jpg",
        )

    assert result.saved is True
    assert result.image_url == "https://cdn.example/instagram/recipe.jpg"
    delete_thumb.assert_not_called()


def test_save_recipe_import_ambiguous_failure_without_committed_row_deletes_thumbnail():
    client = _FakeClient()
    client.insert_error = RuntimeError("connection reset by peer")

    with (
        patch(
            "app.repositories.recipe_imports.delete_tiktok_thumbnail"
        ) as delete_thumb,
        patch(
            "app.repositories.recipe_imports.get_recipe_import",
            return_value=None,
        ),
    ):
        result = _run(
            client,
            image_url="https://cdn.example/instagram/recipe.jpg",
            managed_image_storage_path="instagram/recipe.jpg",
        )

    assert result.saved is False
    delete_thumb.assert_called_once_with("instagram/recipe.jpg")
