from __future__ import annotations

from datetime import datetime, timezone

from app.repositories.recipe_imports import _build_refetched_recipe_update_payload
from app.schemas.extract import NormalizedRecipe, RecipeImportRecord


def _record() -> RecipeImportRecord:
    return RecipeImportRecord(
        id="abc",
        submitted_url="https://old.test/source",
        final_url="https://old.test/final",
        page_title="Old Title",
        recipe_count=1,
        times_cooked=9,
        recipes_json=[
            NormalizedRecipe(
                name="Old Recipe",
                recipeYield="2 servings",
                ingredients=["old ingredient 1", "old ingredient 2"],
                instructions=["old step 1", "old step 2"],
            )
        ],
        recipe_overrides_json={
            "0": {
                "ingredients": {"1": "edited ingredient", "3": "stale ingredient"},
                "instructions": {"0": "edited step", "2": "stale step"},
            },
            "2": {
                "ingredients": {"0": "stale recipe"},
                "instructions": {},
            },
        },
        image_url="https://old.test/image.jpg",
        is_favorite=True,
        servings=2,
        created_at=datetime.now(timezone.utc),
    )


def test_build_refetched_recipe_update_payload_replaces_raw_fields_and_prunes_overrides():
    fresh_recipe = NormalizedRecipe(
        name="Fresh Recipe",
        recipeYield="Makes 4 bowls",
        ingredients=["fresh ingredient 1", "fresh ingredient 2"],
        instructions=["fresh step 1"],
    )

    payload = _build_refetched_recipe_update_payload(
        _record(),
        title="Fresh Title",
        image_url="https://fresh.test/image.jpg",
        recipes=[fresh_recipe],
    )

    assert payload["page_title"] == "Fresh Title"
    assert payload["recipe_count"] == 1
    assert payload["recipes_json"][0]["name"] == "Fresh Recipe"
    assert payload["image_url"] == "https://fresh.test/image.jpg"
    assert payload["servings"] == 4
    assert payload["recipe_overrides_json"] == {
        "0": {
            "ingredients": {"1": "edited ingredient"},
            "instructions": {"0": "edited step"},
        }
    }
