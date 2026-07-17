from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.repositories.recipe_imports import (
    _primary_recipe_name,
    _sanitize_record,
    _sort_recipe_import_records,
    apply_display_titles,
    list_recipe_import_records_for_title_cleanup,
    save_manual_recipe,
)
from app.schemas.extract import (
    DisplayTitleSource,
    NormalizedRecipe,
    RecipeImportRecord,
    RecipeSortOption,
)


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
    page_title: str | None = "Old Title",
    recipe_name: str = "Garlic Noodles",
    created_at: datetime | None = None,
) -> RecipeImportRecord:
    return RecipeImportRecord(
        id=record_id,
        submitted_url="https://old.test/source",
        final_url="https://old.test/source",
        page_title=page_title,
        display_title=display_title,
        display_title_source=display_title_source,
        times_cooked=0,
        recipes_json=[_recipe(recipe_name)],
        recipe_overrides_json={},
        image_url=None,
        is_favorite=False,
        servings=None,
        created_at=created_at or datetime.now(timezone.utc),
    )


def _raw_record(**overrides) -> dict:
    base = {
        "id": "abc",
        "submitted_url": "https://old.test/source",
        "final_url": "https://old.test/source",
        "page_title": "Old Title",
        "times_cooked": 0,
        "recipes_json": [_recipe().model_dump()],
        "recipe_overrides_json": {},
        "image_url": None,
        "is_favorite": False,
        "servings": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


class _InsertQuery:
    def __init__(self, recorder: list[dict]):
        self._recorder = recorder

    def insert(self, payload: dict):
        self._recorder.append(payload)
        return self

    def execute(self):
        return type("Response", (), {"data": []})()


class _InsertClient:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def table(self, _table_name: str):
        return _InsertQuery(self.payloads)


class _UpdateQuery:
    def __init__(self, recorder: list[dict], response_data: list[dict]):
        self._recorder = recorder
        self._response_data = response_data

    def update(self, payload: dict):
        self._recorder.append(payload)
        return self

    def eq(self, _column: str, _value: str):
        return self

    def execute(self):
        return type("Response", (), {"data": self._response_data})()


class _UpdateClient:
    def __init__(self, response_data: list[dict] | None = None) -> None:
        self.payloads: list[dict] = []
        self._response_data = response_data if response_data is not None else [_raw_record()]

    def table(self, _table_name: str):
        return _UpdateQuery(self.payloads, self._response_data)


class _SelectQuery:
    def __init__(self, recorder: list[tuple], response_data: list[dict]):
        self._recorder = recorder
        self._response_data = response_data

    def select(self, columns: str):
        self._recorder.append(("select", columns))
        return self

    def order(self, column: str, **kwargs):
        self._recorder.append(("order", column, kwargs))
        return self

    def limit(self, value: int):
        self._recorder.append(("limit", value))
        return self

    def lt(self, column: str, value: str):
        self._recorder.append(("lt", column, value))
        return self

    def execute(self):
        return type("Response", (), {"data": self._response_data})()


class _SelectClient:
    def __init__(self, response_data: list[dict] | None = None) -> None:
        self.calls: list[tuple] = []
        self._response_data = response_data if response_data is not None else [_raw_record()]

    def table(self, _table_name: str):
        return _SelectQuery(self.calls, self._response_data)


# --- _sanitize_record -------------------------------------------------------


def test_sanitize_record_threads_the_display_columns_through():
    record = _sanitize_record(
        _raw_record(display_title="Creamy Garlic Pasta", display_title_source="ai")
    )

    assert record.display_title == "Creamy Garlic Pasta"
    assert record.display_title_source == DisplayTitleSource.ai


def test_sanitize_record_defaults_a_row_that_predates_the_columns():
    record = _sanitize_record(_raw_record())

    assert record.display_title is None
    assert record.display_title_source == DisplayTitleSource.fallback


@pytest.mark.parametrize("value", ["nonsense", "", "USER", 7])
def test_sanitize_record_coerces_an_unknown_source_to_fallback(value):
    # Never to 'user' -- that would silently make the row uneditable by cleanup.
    record = _sanitize_record(_raw_record(display_title_source=value))

    assert record.display_title_source == DisplayTitleSource.fallback


def test_sanitize_record_ignores_the_generated_sort_column():
    record = _sanitize_record(_raw_record(display_title_sort="garlic noodles"))

    assert record.id == "abc"


# --- sorting (R6) -----------------------------------------------------------


def test_primary_recipe_name_prefers_the_display_title():
    record = _record(display_title="Creamy Garlic Pasta", recipe_name="Pasta")

    assert _primary_recipe_name(record) == "creamy garlic pasta"


def test_primary_recipe_name_falls_back_to_the_recipe_name():
    assert _primary_recipe_name(_record(recipe_name="Chicken Adobo")) == "chicken adobo"


def test_primary_recipe_name_falls_back_to_the_page_title():
    record = _record(page_title="Page Title").model_copy(update={"recipes_json": []})

    assert _primary_recipe_name(record) == "page title"


def test_az_sort_orders_by_the_display_title_not_the_page_title():
    # The user sees "Apple Pie" and "Zesty Salad"; the raw page titles are the
    # reverse, so this proves which one drives the order.
    apple = _record(
        record_id="apple", display_title="Apple Pie", page_title="Zzz Raw Title"
    )
    zesty = _record(
        record_id="zesty", display_title="Zesty Salad", page_title="Aaa Raw Title"
    )

    ordered = _sort_recipe_import_records([zesty, apple], RecipeSortOption.az)

    assert [record.id for record in ordered] == ["apple", "zesty"]


# --- save_manual_recipe (R10) -----------------------------------------------


def _save_manual(title: str | None) -> dict:
    client = _InsertClient()

    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_write_client", return_value=client),
        patch(
            "app.repositories.recipe_imports.get_recipe_import",
            return_value=_record(),
        ),
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        save_manual_recipe(_recipe("Chicken Adobo"), title=title)

    return client.payloads[0]


def test_save_manual_recipe_titles_itself_from_the_recipe_name():
    payload = _save_manual(None)

    assert payload["display_title"] == "Chicken Adobo"
    assert payload["display_title_source"] == "user"


def test_save_manual_recipe_ignores_the_record_title_for_display():
    # The manual form defaults `title` to "Manual recipe: X", which is a record
    # label and not a dish name.
    payload = _save_manual("Manual recipe: Chicken Adobo")

    assert payload["page_title"] == "Manual recipe: Chicken Adobo"
    assert payload["display_title"] == "Chicken Adobo"


# --- apply_display_titles (R13, R14) ----------------------------------------


def _patch_apply(client, existing: RecipeImportRecord | None):
    return (
        patch("app.repositories.recipe_imports.get_settings"),
        patch("app.repositories.recipe_imports._get_write_client", return_value=client),
        patch("app.repositories.recipe_imports.get_recipe_import", return_value=existing),
    )


@pytest.mark.parametrize(
    "source",
    [DisplayTitleSource.ai, DisplayTitleSource.fallback],
)
def test_apply_display_titles_writes_a_non_user_row(source):
    client = _UpdateClient()
    settings_patch, _, get_record = _patch_apply(
        client, _record(display_title_source=source)
    )

    with settings_patch as get_settings, _, get_record:
        get_settings.return_value.supabase_table_name = "recipe_imports"
        results = apply_display_titles([("abc", "Creamy Garlic Pasta")])

    assert results[0].status == "applied"
    assert client.payloads[0]["display_title"] == "Creamy Garlic Pasta"
    assert client.payloads[0]["display_title_source"] == "user"


def test_apply_display_titles_skips_a_user_titled_row_even_when_asked():
    # Covers AE3 and R13: the database is the authority, not the client's claim.
    client = _UpdateClient()
    settings_patch, _, get_record = _patch_apply(
        client, _record(display_title="Mom's Adobo", display_title_source=DisplayTitleSource.user)
    )

    with settings_patch as get_settings, _, get_record:
        get_settings.return_value.supabase_table_name = "recipe_imports"
        results = apply_display_titles([("abc", "Chicken Adobo")])

    assert results[0].status == "skipped"
    assert client.payloads == []


def test_apply_display_titles_reports_a_missing_record():
    client = _UpdateClient()
    settings_patch, _, get_record = _patch_apply(client, None)

    with settings_patch as get_settings, _, get_record:
        get_settings.return_value.supabase_table_name = "recipe_imports"
        results = apply_display_titles([("missing", "Chicken Adobo")])

    assert results[0].status == "not_found"
    assert client.payloads == []


def test_apply_display_titles_never_writes_the_original_titles():
    # R14 is structural: only the two display columns may be written.
    client = _UpdateClient()
    settings_patch, _, get_record = _patch_apply(client, _record())

    with settings_patch as get_settings, _, get_record:
        get_settings.return_value.supabase_table_name = "recipe_imports"
        apply_display_titles([("abc", "Creamy Garlic Pasta")])

    assert set(client.payloads[0]) == {"display_title", "display_title_source"}


def test_apply_display_titles_processes_each_item():
    client = _UpdateClient()
    settings_patch, _, get_record = _patch_apply(client, _record())

    with settings_patch as get_settings, _, get_record:
        get_settings.return_value.supabase_table_name = "recipe_imports"
        results = apply_display_titles(
            [("a", "Creamy Garlic Pasta"), ("b", "Chicken Adobo")]
        )

    assert [result.status for result in results] == ["applied", "applied"]
    assert len(client.payloads) == 2


# --- cleanup candidate reader -----------------------------------------------


def test_title_cleanup_reader_pages_by_created_at_descending():
    client = _SelectClient()

    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_read_client", return_value=client),
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        list_recipe_import_records_for_title_cleanup(batch_size=5)

    assert ("order", "created_at", {"desc": True}) in client.calls
    assert ("limit", 5) in client.calls
    assert not any(call[0] == "lt" for call in client.calls)


def test_title_cleanup_reader_applies_a_cursor_when_given():
    client = _SelectClient()
    cursor = datetime.now(timezone.utc).isoformat()

    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_read_client", return_value=client),
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        list_recipe_import_records_for_title_cleanup(cursor=cursor, batch_size=5)

    assert ("lt", "created_at", cursor) in client.calls


def test_title_cleanup_reader_raises_when_supabase_is_unconfigured():
    with (
        patch("app.repositories.recipe_imports.get_settings"),
        patch("app.repositories.recipe_imports._get_read_client", return_value=None),
    ):
        with pytest.raises(RuntimeError, match="not configured"):
            list_recipe_import_records_for_title_cleanup()
