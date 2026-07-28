from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from app.repositories.recipe_imports import (
    RECIPE_IMPORT_SELECT,
    _build_cuisine_facets,
    _filter_recipe_import_records,
    _prepare_recipe_import_records,
    _sort_recipe_import_records,
    list_cuisine_facets,
    list_recipe_imports,
)
from app.schemas.extract import (
    NormalizedRecipe,
    RecipeImportRecord,
    RecipeSortOption,
)


def _recipe(name: str, cuisines: list[str] | None = None) -> NormalizedRecipe:
    return NormalizedRecipe(
        name=name,
        recipeCuisine=cuisines,
        ingredients=["1 cup water"],
        instructions=["Stir."],
    )


def _record(
    recipe_id: str,
    name: str,
    created_at: str,
    times_cooked: int = 0,
    is_favorite: bool = False,
    cuisines: list[str] | None = None,
) -> RecipeImportRecord:
    return RecipeImportRecord(
        id=recipe_id,
        submitted_url=f"https://example.com/{recipe_id}",
        final_url=f"https://example.com/{recipe_id}",
        page_title=name,
        times_cooked=times_cooked,
        recipes_json=[_recipe(name, cuisines)],
        recipe_overrides_json={},
        is_favorite=is_favorite,
        created_at=datetime.fromisoformat(created_at).replace(tzinfo=timezone.utc),
    )


def _record_dict(recipe_id: str = "1", *, cuisines: list[str] | None = None) -> dict:
    return {
        "id": recipe_id,
        "submitted_url": f"https://example.com/{recipe_id}",
        "final_url": f"https://example.com/{recipe_id}",
        "page_title": "Pasta",
        "times_cooked": 2,
        "recipes_json": [_recipe("Pasta", cuisines or ["Italian"]).model_dump()],
        "recipe_overrides_json": {},
        "image_url": None,
        "is_favorite": False,
        "servings": None,
        "created_at": datetime(2026, 4, 1, tzinfo=timezone.utc).isoformat(),
    }


class _Response:
    def __init__(self, data: list[dict], count: int | None = None):
        self.data = data
        self.count = count


class _ListQuery:
    def __init__(self, response: _Response):
        self.response = response
        self.calls: list[tuple] = []

    def select(self, *args, **kwargs):
        self.calls.append(("select", args, kwargs))
        return self

    def eq(self, column: str, value):
        self.calls.append(("eq", column, value))
        return self

    def in_(self, column: str, value):
        self.calls.append(("in_", column, value))
        return self

    def contains(self, column: str, value):
        self.calls.append(("contains", column, value))
        return self

    def order(self, column: str, **kwargs):
        self.calls.append(("order", column, kwargs))
        return self

    def range(self, start: int, end: int):
        self.calls.append(("range", start, end))
        return self

    def execute(self):
        return self.response


class _ListClient:
    def __init__(self, query: _ListQuery):
        self.query = query

    def table(self, _table_name: str):
        return self.query


class _FacetClient:
    def __init__(self):
        self.rpc_calls: list[tuple[str, dict | None]] = []

    def rpc(self, fn_name: str, params: dict | None = None):
        self.rpc_calls.append((fn_name, params))
        return _ListQuery(
            _Response(
                [
                    {"label": "american", "count": 2},
                    {"label": "other", "count": 1},
                ]
            )
        )


class _FailingRpcQuery:
    def execute(self):
        raise Exception("rpc exploded")


class _SearchClient:
    def __init__(
        self,
        data: list[dict],
        fail: bool = False,
        responses: list[list[dict]] | None = None,
    ):
        self.data = data
        self.fail = fail
        self.responses = list(responses) if responses is not None else None
        self.rpc_calls: list[tuple[str, dict | None]] = []
        self.table_calls = 0

    def rpc(self, fn_name: str, params: dict | None = None):
        self.rpc_calls.append((fn_name, params))
        if self.fail:
            return _FailingRpcQuery()
        if self.responses is not None:
            return _ListQuery(_Response(self.responses.pop(0)))
        return _ListQuery(_Response(self.data))

    def table(self, _table_name: str):
        self.table_calls += 1
        raise AssertionError("search path must not use the table builder chain")


def _search_row(recipe_id: str = "1", total_count: int = 1) -> dict:
    return {**_record_dict(recipe_id), "total_count": total_count}


def test_sort_recipe_import_records_orders_a_to_z_case_insensitive():
    records = [
        _record("1", "ziti", "2026-04-01T00:00:00"),
        _record("2", "Apple Pie", "2026-04-03T00:00:00"),
        _record("3", "banana Bread", "2026-04-02T00:00:00"),
    ]

    sorted_records = _sort_recipe_import_records(records, RecipeSortOption.az)

    assert [record.id for record in sorted_records] == ["2", "3", "1"]


def test_sort_recipe_import_records_orders_z_to_a_case_insensitive():
    records = [
        _record("1", "ziti", "2026-04-01T00:00:00"),
        _record("2", "Apple Pie", "2026-04-03T00:00:00"),
        _record("3", "banana Bread", "2026-04-02T00:00:00"),
    ]

    sorted_records = _sort_recipe_import_records(records, RecipeSortOption.za)

    assert [record.id for record in sorted_records] == ["1", "3", "2"]


def test_sort_recipe_import_records_orders_most_cooked_with_recent_tie_breaker():
    records = [
        _record("1", "One", "2026-04-01T00:00:00", times_cooked=3),
        _record("2", "Two", "2026-04-03T00:00:00", times_cooked=7),
        _record("3", "Three", "2026-04-02T00:00:00", times_cooked=7),
    ]

    sorted_records = _sort_recipe_import_records(records, RecipeSortOption.times_cooked)

    assert [record.id for record in sorted_records] == ["2", "3", "1"]


def test_sort_recipe_import_records_orders_recent_first():
    records = [
        _record("1", "One", "2026-04-01T00:00:00"),
        _record("2", "Two", "2026-04-03T00:00:00"),
        _record("3", "Three", "2026-04-02T00:00:00"),
    ]

    sorted_records = _sort_recipe_import_records(records, RecipeSortOption.recent)

    assert [record.id for record in sorted_records] == ["2", "3", "1"]


def test_sort_recipe_import_records_orders_favorites_first_with_recent_tie_breaker():
    records = [
        _record("1", "One", "2026-04-01T00:00:00", is_favorite=False),
        _record("2", "Two", "2026-04-03T00:00:00", is_favorite=True),
        _record("3", "Three", "2026-04-02T00:00:00", is_favorite=True),
    ]

    sorted_records = _sort_recipe_import_records(records, RecipeSortOption.favorites)

    assert [record.id for record in sorted_records] == ["2", "3", "1"]


def test_filter_recipe_import_records_matches_cuisine_aliases():
    records = [
        _record("1", "Burger", "2026-04-01T00:00:00", cuisines=["USA"]),
        _record("2", "Pasta", "2026-04-02T00:00:00", cuisines=["Italian"]),
        _record("3", "Pie", "2026-04-03T00:00:00", cuisines=["United States"]),
    ]

    filtered_records = _filter_recipe_import_records(records, "American")

    assert [record.id for record in filtered_records] == ["1", "3"]


def test_filter_recipe_import_records_filters_other_unknown_cuisine():
    records = [
        _record("1", "Mystery", "2026-04-01T00:00:00", cuisines=["Atlantis"]),
        _record("2", "Pasta", "2026-04-02T00:00:00", cuisines=["Italian"]),
        _record("3", "Toast", "2026-04-03T00:00:00", cuisines=None),
    ]

    filtered_records = _filter_recipe_import_records(records, "Other")

    assert [record.id for record in filtered_records] == ["1"]


def test_prepare_recipe_import_records_filters_before_pagination_callers_slice():
    records = [
        _record("1", "Zebra", "2026-04-01T00:00:00", cuisines=["Italian"]),
        _record("2", "Apple", "2026-04-02T00:00:00", cuisines=["USA"]),
        _record("3", "Beta", "2026-04-03T00:00:00", cuisines=["American"]),
    ]

    prepared_records = _prepare_recipe_import_records(
        records,
        RecipeSortOption.az,
        "American",
    )

    assert [record.id for record in prepared_records] == ["2", "3"]


def test_build_cuisine_facets_counts_each_record_once_per_canonical_cuisine():
    records = [
        _record("1", "Burger", "2026-04-01T00:00:00", cuisines=["USA", "American"]),
        _record("2", "Pasta", "2026-04-02T00:00:00", cuisines=["Italian"]),
        _record("3", "Mystery", "2026-04-03T00:00:00", cuisines=["Atlantis"]),
    ]

    facets = _build_cuisine_facets(records)

    assert [(facet.label, facet.count) for facet in facets] == [
        ("American", 1),
        ("Italian", 1),
        ("Other", 1),
    ]


def test_list_recipe_imports_applies_db_pagination_sort_and_count():
    query = _ListQuery(_Response([_record_dict("1")], count=12))

    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_read_client") as get_read_client,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_read_client.return_value = _ListClient(query)

        response = list_recipe_imports(
            page=2,
            page_size=10,
            sort=RecipeSortOption.times_cooked,
        )

    assert response.total_count == 12
    assert response.total_pages == 2
    assert ("select", (RECIPE_IMPORT_SELECT,), {"count": "exact"}) in query.calls
    assert ("order", "times_cooked", {"desc": True}) in query.calls
    assert ("order", "created_at", {"desc": True}) in query.calls
    assert ("range", 10, 19) in query.calls


def test_list_recipe_imports_filters_cuisine_with_cuisines_contains():
    query = _ListQuery(_Response([_record_dict("1", cuisines=["Italian"])], count=1))

    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_read_client") as get_read_client,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_read_client.return_value = _ListClient(query)

        list_recipe_imports(
            page=1,
            page_size=10,
            sort=RecipeSortOption.recent,
            cuisine="Italian",
        )

    assert ("contains", "cuisines", ["italian"]) in query.calls
    assert not any(call[0] == "in_" for call in query.calls)


def test_list_recipe_imports_search_calls_rpc_with_all_params():
    client = _SearchClient([_search_row("1", total_count=27)])

    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_read_client") as get_read_client,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_read_client.return_value = client

        response = list_recipe_imports(
            page=3,
            page_size=10,
            sort=RecipeSortOption.times_cooked,
            cuisine="Italian",
            favorite=True,
            search="curry",
        )

    assert client.rpc_calls == [
        (
            "search_recipe_imports",
            {
                "p_term": "curry",
                "p_cuisine": "italian",
                "p_favorite": True,
                "p_sort": "times_cooked",
                "p_limit": 10,
                "p_offset": 20,
            },
        )
    ]
    assert client.table_calls == 0
    assert response.total_count == 27
    assert response.total_pages == 3
    assert [item.id for item in response.items] == ["1"]


def test_list_recipe_imports_search_none_uses_builder_chain():
    query = _ListQuery(_Response([_record_dict("1")], count=1))

    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_read_client") as get_read_client,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_read_client.return_value = _ListClient(query)

        response = list_recipe_imports(
            page=1,
            page_size=10,
            sort=RecipeSortOption.recent,
            search=None,
        )

    assert response.total_count == 1
    assert ("range", 0, 9) in query.calls


def test_list_recipe_imports_search_blank_uses_builder_chain():
    query = _ListQuery(_Response([_record_dict("1")], count=1))

    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_read_client") as get_read_client,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_read_client.return_value = _ListClient(query)

        response = list_recipe_imports(
            page=1,
            page_size=10,
            sort=RecipeSortOption.recent,
            search="   ",
        )

    assert response.total_count == 1
    assert ("range", 0, 9) in query.calls


def test_list_recipe_imports_search_trims_term_before_rpc():
    client = _SearchClient([_search_row("1")])

    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_read_client") as get_read_client,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_read_client.return_value = client

        list_recipe_imports(
            page=1,
            page_size=10,
            sort=RecipeSortOption.recent,
            search="  curry  ",
        )

    assert client.rpc_calls[0][1]["p_term"] == "curry"


def test_list_recipe_imports_search_dedupes_rows_by_url():
    duplicate = {**_search_row("1", total_count=2), "id": "2"}
    duplicate["submitted_url"] = _search_row("1")["submitted_url"]
    duplicate["final_url"] = _search_row("1")["final_url"]
    client = _SearchClient([_search_row("1", total_count=2), duplicate])

    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_read_client") as get_read_client,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_read_client.return_value = client

        response = list_recipe_imports(
            page=1,
            page_size=10,
            sort=RecipeSortOption.recent,
            search="pasta",
        )

    assert [item.id for item in response.items] == ["1"]


def test_list_recipe_imports_search_beyond_end_page_keeps_real_total_count():
    client = _SearchClient(
        [],
        responses=[[], [_search_row("1", total_count=27)]],
    )

    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_read_client") as get_read_client,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_read_client.return_value = client

        response = list_recipe_imports(
            page=5,
            page_size=10,
            sort=RecipeSortOption.recent,
            search="curry",
        )

    assert response.items == []
    assert response.total_count == 27
    assert response.total_pages == 3
    assert len(client.rpc_calls) == 2
    assert client.rpc_calls[1][1]["p_limit"] == 1
    assert client.rpc_calls[1][1]["p_offset"] == 0


def test_list_recipe_imports_search_empty_page_reports_zero_count():
    client = _SearchClient([])

    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_read_client") as get_read_client,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_read_client.return_value = client

        response = list_recipe_imports(
            page=3,
            page_size=10,
            sort=RecipeSortOption.recent,
            search="nothing matches",
        )

    assert response.items == []
    assert response.total_count == 0
    assert response.total_pages == 1


def test_list_recipe_imports_search_rpc_error_raises_read_failed():
    client = _SearchClient([], fail=True)

    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_read_client") as get_read_client,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_read_client.return_value = client

        try:
            list_recipe_imports(
                page=1,
                page_size=10,
                sort=RecipeSortOption.recent,
                search="curry",
            )
        except RuntimeError as error:
            assert "Supabase read failed" in str(error)
        else:
            raise AssertionError("expected RuntimeError")


def test_list_cuisine_facets_uses_rpc_and_maps_display_labels():
    client = _FacetClient()

    with (
        patch("app.repositories.recipe_imports.get_settings") as get_settings,
        patch("app.repositories.recipe_imports._get_read_client") as get_read_client,
    ):
        get_settings.return_value.supabase_table_name = "recipe_imports"
        get_read_client.return_value = client

        response = list_cuisine_facets()

    assert client.rpc_calls == [("cuisine_facets", {})]
    assert [(facet.label, facet.count) for facet in response.facets] == [
        ("American", 2),
        ("Other", 1),
    ]
