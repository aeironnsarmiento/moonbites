from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.extract import NormalizedRecipe, RecipeImportRecord
from app.services.recipe_identity import (
    content_identity,
    dedupe_by_content,
    dedupe_by_source,
    source_identity,
)


def _recipe(**overrides) -> NormalizedRecipe:
    defaults = dict(
        name="Miso Salmon Brothy Rice",
        recipeYield="2 servings",
        cookTime="PT15M",
        recipeCuisine=["Japanese"],
        nutrition={"calories": "420"},
        ingredients=["1 cup rice", "1 salmon fillet"],
        instructions=["Cook rice.", "Sear salmon."],
    )
    defaults.update(overrides)
    return NormalizedRecipe.model_validate(defaults)


def _record(recipe_id: str, submitted_url: str, final_url: str) -> RecipeImportRecord:
    return RecipeImportRecord.model_validate(
        {
            "id": recipe_id,
            "submitted_url": submitted_url,
            "final_url": final_url,
            "recipes_json": [_recipe()],
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
    )


# --- content_identity --------------------------------------------------------


def test_content_identity_is_stable_for_identical_recipes():
    assert content_identity(_recipe()) == content_identity(_recipe())


def test_content_identity_ignores_name_case():
    assert content_identity(_recipe(name="Miso Salmon Brothy Rice")) == content_identity(
        _recipe(name="MISO SALMON BROTHY RICE")
    )


def test_content_identity_differs_on_ingredients():
    assert content_identity(_recipe()) != content_identity(
        _recipe(ingredients=["2 cups rice", "1 salmon fillet"])
    )


def test_content_identity_ignores_ingredient_sections():
    # ingredientSections is deliberately excluded from identity -- two
    # recipes differing only in how ingredients are grouped are the same dish.
    plain = _recipe()
    sectioned = _recipe(
        ingredientSections=[{"heading": "Main", "items": ["1 cup rice"]}]
    )
    assert content_identity(plain) == content_identity(sectioned)


def test_dedupe_by_content_keeps_first_occurrence():
    a = _recipe(name="Rice A")
    b = _recipe(name="Rice A")  # same identity as a
    c = _recipe(name="Rice B")

    result = dedupe_by_content([a, b, c])

    assert result == [a, c]


# --- source_identity ----------------------------------------------------------


def test_source_identity_strips_known_tracking_params():
    assert source_identity(
        "https://example.com/recipe?utm_source=ig&utm_medium=post"
    ) == source_identity("https://example.com/recipe")


def test_source_identity_preserves_non_tracking_params():
    # The YouTube case: ?v= IS the identity. Dropping unrecognized query
    # params would collapse every video into the same source.
    a = source_identity("https://www.youtube.com/watch?v=aaa111")
    b = source_identity("https://www.youtube.com/watch?v=bbb222")
    assert a != b


def test_source_identity_normalizes_trailing_slash():
    assert source_identity("https://example.com/recipe/") == source_identity(
        "https://example.com/recipe"
    )


def test_source_identity_normalizes_default_ports():
    assert source_identity("https://example.com:443/recipe") == source_identity(
        "https://example.com/recipe"
    )


def test_source_identity_normalizes_case_and_scheme():
    assert source_identity("HTTPS://Example.com/Recipe") != source_identity(
        "https://example.com/recipe"
    )
    # host is case-insensitive, path is not -- only the host is lowercased
    assert source_identity("https://EXAMPLE.com/recipe") == source_identity(
        "https://example.com/recipe"
    )


def test_source_identity_orders_query_params_independent_of_input_order():
    assert source_identity("https://example.com/r?a=1&b=2") == source_identity(
        "https://example.com/r?b=2&a=1"
    )


# --- dedupe_by_source ----------------------------------------------------------


def test_dedupe_by_source_collapses_tracking_param_variants():
    records = [
        _record("1", "https://example.com/r", "https://example.com/r"),
        _record(
            "2",
            "https://example.com/r?utm_source=ig",
            "https://example.com/r?utm_source=ig",
        ),
    ]

    result = dedupe_by_source(records)

    assert [r.id for r in result] == ["1"]


def test_dedupe_by_source_keeps_distinct_sources():
    records = [
        _record("1", "https://example.com/a", "https://example.com/a"),
        _record("2", "https://example.com/b", "https://example.com/b"),
    ]

    result = dedupe_by_source(records)

    assert [r.id for r in result] == ["1", "2"]


def test_dedupe_by_source_matches_across_submitted_and_final_url():
    # A submitted URL that canonically matches an earlier record's final URL
    # is still the same source (e.g. a redirect landed where another import
    # was submitted directly).
    records = [
        _record("1", "https://blog.example/short-link", "https://example.com/r"),
        _record("2", "https://example.com/r", "https://example.com/r"),
    ]

    result = dedupe_by_source(records)

    assert [r.id for r in result] == ["1"]
