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
                "ingredients": [
                    {"source": 1, "text": "edited ingredient"},
                    {"source": 0, "text": None},
                ],
                "instructions": [
                    {"source": 0, "text": "edited step"},
                    {"source": 1, "text": "stale step"},
                ],
            },
            "2": {
                "ingredients": [{"source": 0, "text": "stale recipe"}],
                "instructions": None,
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
    assert payload["recipes_json"][0]["name"] == "Fresh Recipe"
    assert payload["image_url"] == "https://fresh.test/image.jpg"
    assert payload["servings"] == 4
    assert payload["recipe_overrides_json"] == {
        "0": {
            "ingredients": [
                {"source": 1, "text": "edited ingredient"},
                {"source": 0, "text": None},
            ],
            "instructions": [{"source": 0, "text": "edited step"}],
        }
    }
