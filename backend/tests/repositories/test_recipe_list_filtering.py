from __future__ import annotations

from datetime import datetime, timezone

from app.repositories.recipe_imports import (
    _build_cuisine_facets,
    _filter_recipe_import_records,
    _prepare_recipe_import_records,
    _sort_recipe_import_records,
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
        recipe_count=1,
        times_cooked=times_cooked,
        recipes_json=[_recipe(name, cuisines)],
        recipe_overrides_json={},
        is_favorite=is_favorite,
        created_at=datetime.fromisoformat(created_at).replace(tzinfo=timezone.utc),
    )


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
