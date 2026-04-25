from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app
from app.repositories.recipe_imports import _build_metadata_update_payload
from app.schemas.extract import (
    NormalizedRecipe,
    RecipeImportRecord,
    UpdateRecipeMetadataRequest,
)


client = TestClient(app)


def _record() -> RecipeImportRecord:
    return RecipeImportRecord(
        id="abc",
        submitted_url="https://old.test/source",
        final_url="https://old.test/source",
        page_title="Old Title",
        recipe_count=1,
        times_cooked=0,
        recipes_json=[
            NormalizedRecipe(
                name="Old Title",
                recipeYield="2 servings",
                ingredients=["1 cup rice"],
                instructions=["Cook."],
            )
        ],
        recipe_overrides_json={},
        image_url="https://old.test/image.jpg",
        is_favorite=False,
        servings=2,
        created_at=datetime.now(timezone.utc),
    )


def test_update_metadata_returns_updated_record():
    updated = _record().model_copy(
        update={
            "page_title": "New Title",
            "submitted_url": "https://new.test/source",
            "final_url": "https://new.test/source",
            "image_url": None,
            "servings": 6,
        }
    )
    updated.recipes_json[0] = updated.recipes_json[0].model_copy(
        update={"name": "New Title", "recipeYield": "6 servings"}
    )

    with patch(
        "backend.app.api.routes.recipes.update_recipe_metadata",
        return_value=updated,
    ) as update_recipe_metadata:
        response = client.patch(
            "/api/recipes/abc/metadata",
            json={
                "title": "New Title",
                "recipe_yield": "6 servings",
                "image_url": None,
                "source_url": "https://new.test/source",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["page_title"] == "New Title"
    assert body["submitted_url"] == "https://new.test/source"
    assert body["final_url"] == "https://new.test/source"
    assert body["recipes_json"][0]["name"] == "New Title"
    assert body["recipes_json"][0]["recipeYield"] == "6 servings"
    assert body["servings"] == 6
    update_recipe_metadata.assert_called_once()


def test_update_metadata_rejects_invalid_source_url():
    response = client.patch(
        "/api/recipes/abc/metadata",
        json={
            "title": "New Title",
            "recipe_yield": "6 servings",
            "image_url": None,
            "source_url": "manual://abc",
        },
    )

    assert response.status_code == 422


def test_update_metadata_returns_404_when_missing():
    with patch(
        "backend.app.api.routes.recipes.update_recipe_metadata",
        return_value=None,
    ):
        response = client.patch(
            "/api/recipes/missing/metadata",
            json={
                "title": "New Title",
                "recipe_yield": "6 servings",
                "image_url": None,
                "source_url": "https://new.test/source",
            },
        )

    assert response.status_code == 404


def test_build_metadata_update_payload_recalculates_servings_from_yield():
    payload = _build_metadata_update_payload(
        _record(),
        UpdateRecipeMetadataRequest(
            title="Party Rice",
            recipe_yield="Makes 12 bowls",
            image_url="",
            source_url="https://new.test/source",
        ),
    )

    assert payload["page_title"] == "Party Rice"
    assert payload["submitted_url"] == "https://new.test/source"
    assert payload["final_url"] == "https://new.test/source"
    assert payload["image_url"] is None
    assert payload["servings"] == 12
    assert payload["recipes_json"][0]["name"] == "Party Rice"
    assert payload["recipes_json"][0]["recipeYield"] == "Makes 12 bowls"
